"""
Cabinet Dr. Khiri - Prise de Rendez-vous
Lancer: uvicorn main:app --reload
Ouvrir: http://localhost:8006
"""

from datetime import datetime, date, timedelta
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from config import get_settings
from models import BookingRequest, BookingResponse, DaySlotsResponse, MonthSlotsResponse, SlotInfo
from google_services import (
    get_available_slots, get_available_slots_range,
    book_slot, send_confirmation_to_doctor, send_confirmation_to_patient,
)
import blocklist

DAYS_FR = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]
MONTHS_FR = ["","Janvier","Fevrier","Mars","Avril","Mai","Juin",
             "Juillet","Aout","Septembre","Octobre","Novembre","Decembre"]

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    print(f"\n{'='*50}")
    print(f"  Cabinet Dr. Khiri - Backend RDV")
    print(f"  http://localhost:{s.port}")
    print(f"{'='*50}\n")
    yield


app = FastAPI(title="RDV Dr. Khiri", version="2.0.0", lifespan=lifespan)


# ── API ───────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/slots/{date_str}", response_model=DaySlotsResponse)
async def get_day_slots(date_str: str):
    """Retourne les creneaux DISPO du medecin pour un jour."""
    try:
        target = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(400, "Format: YYYY-MM-DD")

    if target < date.today():
        raise HTTPException(400, "Date dans le passe")

    # Lire les DISPO depuis Google Calendar
    try:
        dispo_slots = get_available_slots(date_str)
    except ConnectionError as e:
        raise HTTPException(503, f"Service Google Calendar temporairement indisponible. Reessayez dans quelques instants.")

    # Filtrer les heures passees si c'est aujourd'hui
    now_str = datetime.now().strftime("%H:%M") if target == date.today() else "00:00"

    slots = []
    for s in dispo_slots:
        if s["start"] > now_str:
            slots.append(SlotInfo(
                start=s["start"],
                end=s["end"],
                label=f"{s['start']} - {s['end']}",
                event_id=s["event_id"],
            ))

    return DaySlotsResponse(date=date_str, slots=slots)


@app.get("/api/slots/month/{year}/{month}", response_model=MonthSlotsResponse)
async def get_month_slots(year: int, month: int):
    """Retourne les dates qui ont des DISPO pour le mois (vue calendrier)."""
    if not (1 <= month <= 12):
        raise HTTPException(400, "Mois invalide")

    start = f"{year}-{month:02d}-01"
    end_dt = datetime(year + (1 if month == 12 else 0), (month % 12) + 1, 1) - timedelta(days=1)
    end = end_dt.strftime("%Y-%m-%d")

    try:
        available = get_available_slots_range(start, end)
    except ConnectionError:
        raise HTTPException(503, "Service Google Calendar temporairement indisponible. Reessayez dans quelques instants.")
    return MonthSlotsResponse(available_dates=available)


@app.post("/api/book", response_model=BookingResponse)
async def book_appointment(req: BookingRequest):
    """Reserver: supprime le DISPO + cree le RDV + emails."""
    try:
        target = datetime.strptime(req.date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(400, "Format invalide")

    if target < date.today():
        raise HTTPException(400, "Date dans le passe")

    # Bloque les patients qui ont deja manque un RDV
    blocked, reason = blocklist.is_blocked(req.patient_email, req.patient_phone)
    if blocked:
        if reason == "email":
            raise HTTPException(
                403,
                "Cette adresse email est bloquee suite a un rendez-vous non honore. "
                "Merci d'appeler le 98 33 19 25. "
                "هذا البريد الإلكتروني محظور بسبب موعد لم يتم احترامه. الرجاء الاتصال بالرقم 98 33 19 25.",
            )
        raise HTTPException(
            403,
            "Ce numero de telephone est bloque suite a un rendez-vous non honore. "
            "Merci d'appeler le 98 33 19 25. "
            "هذا الرقم محظور بسبب موعد لم يتم احترامه. الرجاء الاتصال بالرقم 98 33 19 25.",
        )

    # Verifier que le DISPO existe encore
    try:
        dispo_slots = get_available_slots(req.date)
    except ConnectionError:
        raise HTTPException(503, "Service Google Calendar temporairement indisponible. Reessayez dans quelques instants.")
    found = None
    for s in dispo_slots:
        if s["event_id"] == req.event_id:
            found = s
            break

    if not found:
        raise HTTPException(409, "Ce creneau n'est plus disponible. Quelqu'un l'a peut-etre reserve avant vous.")

    # Book: supprimer DISPO + creer RDV
    result = book_slot(
        date=req.date, start_time=req.start_time, end_time=req.end_time,
        dispo_event_id=req.event_id,
        patient_name=req.patient_name, patient_phone=req.patient_phone,
        patient_email=req.patient_email or "", reason=req.reason or "",
    )

    if not result["success"]:
        raise HTTPException(500, f"Erreur: {result.get('error')}")

    # Emails
    dow = target.weekday()
    date_display = f"{DAYS_FR[dow]} {target.day} {MONTHS_FR[target.month]} {target.year}"
    time_display = f"{req.start_time} - {req.end_time}"

    email_doc = send_confirmation_to_doctor(
        date_display, time_display, req.patient_name,
        req.patient_phone, req.patient_email or "", req.reason or "",
    )
    email_pat = {"success": False, "error": "Pas d'email"}
    if req.patient_email:
        email_pat = send_confirmation_to_patient(
            req.patient_email, req.patient_name, date_display, time_display,
        )

    return BookingResponse(
        success=True, message="Rendez-vous confirme!",
        event_id=result.get("event_id"), calendar_link=result.get("html_link"),
        email_doctor=email_doc, email_patient=email_pat,
    )


# ── ADMIN: BLOCKLIST ──────────────────────────────


class BlockRequest(BaseModel):
    email: str | None = None
    phone: str | None = None


def _check_admin(token: str | None) -> None:
    secret = get_settings().api_secret_key
    if not secret or secret == "change-me":
        raise HTTPException(503, "Admin desactive: definissez API_SECRET_KEY.")
    if token != secret:
        raise HTTPException(401, "Token admin invalide.")


@app.get("/api/admin/blocked")
async def admin_list_blocked(x_admin_token: str | None = Header(default=None)):
    _check_admin(x_admin_token)
    return blocklist.list_all()


@app.post("/api/admin/block")
async def admin_block(req: BlockRequest, x_admin_token: str | None = Header(default=None)):
    _check_admin(x_admin_token)
    if not req.email and not req.phone:
        raise HTTPException(400, "Fournissez au moins un email ou un telephone.")
    return blocklist.block(email=req.email, phone=req.phone)


@app.post("/api/admin/unblock")
async def admin_unblock(req: BlockRequest, x_admin_token: str | None = Header(default=None)):
    _check_admin(x_admin_token)
    if not req.email and not req.phone:
        raise HTTPException(400, "Fournissez au moins un email ou un telephone.")
    return blocklist.unblock(email=req.email, phone=req.phone)


# ── FRONTEND ──────────────────────────────────────

@app.get("/")
async def serve_index():
    return FileResponse(STATIC_DIR / "index.html")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=get_settings().port, reload=True)
