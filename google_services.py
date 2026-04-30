"""
Google Calendar (Service Account) & Gmail (SMTP) services.

LOGIQUE:
- Le medecin cree des evenements "DISPO" dans Google Calendar = creneaux disponibles
- Le frontend lit ces evenements et affiche uniquement les creneaux DISPO
- Quand un patient reserve, le DISPO est SUPPRIME et remplace par "RDV - Patient"
- Les creneaux sans DISPO ne sont PAS affiches

DANS GOOGLE CALENDAR, LE MEDECIN CREE:
  Titre: DISPO    Heure: 10:00 - 11:00
  Titre: DISPO    Heure: 11:00 - 12:00
  Titre: DISPO    Heure: 14:00 - 15:00
  etc.
"""

import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import get_settings

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
]

DISPO_PREFIX = "dispo"


def _get_credentials() -> Credentials:
    s = get_settings()
    return Credentials.from_service_account_file(
        s.google_service_account_file, scopes=SCOPES,
    )

def get_calendar_service():
    return build("calendar", "v3", credentials=_get_credentials())


def _is_dispo(event: dict) -> bool:
    return (event.get("summary") or "").strip().lower().startswith(DISPO_PREFIX)


# -- READ DISPO SLOTS -----------------------------------------

def _parse_time(dt_str: str) -> str:
    """Extract HH:MM from a dateTime string like '2025-02-16T11:30:00+01:00'."""
    time_part = dt_str.split("T")[1]  # "11:30:00+01:00"
    return time_part[:5]  # "11:30"


def get_available_slots(date: str) -> list[dict]:
    """
    Lire les creneaux DISPO pour un jour.
    Returns [{"start":"11:30","end":"12:30","event_id":"abc"}, ...]
    """
    service = get_calendar_service()
    s = get_settings()
    try:
        result = service.events().list(
            calendarId=s.google_calendar_id,
            timeMin=f"{date}T00:00:00+01:00",
            timeMax=f"{date}T23:59:59+01:00",
            singleEvents=True, orderBy="startTime",
        ).execute()
        slots = []
        for ev in result.get("items", []):
            if _is_dispo(ev):
                start_dt = ev["start"].get("dateTime", "")
                end_dt = ev["end"].get("dateTime", "")
                if start_dt and end_dt:
                    slots.append({
                        "start": _parse_time(start_dt),
                        "end": _parse_time(end_dt),
                        "event_id": ev["id"],
                    })
        return slots
    except HttpError as e:
        print(f"Erreur get_available_slots: {e}")
        return []
    except (TimeoutError, ConnectionError, OSError) as e:
        print(f"Erreur reseau get_available_slots: {e}")
        raise ConnectionError(f"Impossible de joindre Google Calendar: {e}")


def get_available_slots_range(start_date: str, end_date: str) -> dict[str, int]:
    """
    Compter les DISPO par jour sur une plage (vue calendrier mensuel).
    Returns {"2025-02-16": 3, "2025-02-17": 2, ...}
    """
    service = get_calendar_service()
    s = get_settings()
    try:
        result = service.events().list(
            calendarId=s.google_calendar_id,
            timeMin=f"{start_date}T00:00:00+01:00",
            timeMax=f"{end_date}T23:59:59+01:00",
            singleEvents=True, orderBy="startTime",
        ).execute()
        counts: dict[str, int] = {}
        for ev in result.get("items", []):
            if _is_dispo(ev):
                start_dt = ev["start"].get("dateTime", "")
                if start_dt:
                    d = start_dt.split("T")[0]
                    counts[d] = counts.get(d, 0) + 1
        return counts
    except HttpError as e:
        print(f"Erreur get_available_slots_range: {e}")
        return {}
    except (TimeoutError, ConnectionError, OSError) as e:
        print(f"Erreur reseau get_available_slots_range: {e}")
        raise ConnectionError(f"Impossible de joindre Google Calendar: {e}")


# -- BOOK A SLOT -----------------------------------------------

def book_slot(date, start_time, end_time, dispo_event_id, patient_name, patient_phone, patient_email, reason=""):
    """Creer le RDV PUIS supprimer le DISPO (ordre securise)."""
    service = get_calendar_service()
    s = get_settings()

    # 1. D'abord creer le RDV (pas d'attendees - les emails sont envoyes par SMTP)
    event_body = {
        "summary": f"RDV - {patient_name}",
        "description": (
            f"Patient: {patient_name}\nTel: {patient_phone}\n"
            f"Email: {patient_email}\nMotif: {reason or 'Consultation'}\n\n"
            f"Cabinet du Dr Bassem Khiri\n74, Avenue Hedi NOUIRA - Ennasr II"
        ),
        "location": "Cabinet du Dr Bassem Khiri",
        "start": {"dateTime": f"{date}T{start_time}:00", "timeZone": "Africa/Tunis"},
        "end": {"dateTime": f"{date}T{end_time}:00", "timeZone": "Africa/Tunis"},
        "reminders": {"useDefault": False, "overrides": [
            {"method": "popup", "minutes": 60}, {"method": "email", "minutes": 120},
        ]},
        "colorId": "11",
    }
    try:
        ev = service.events().insert(
            calendarId=s.google_calendar_id, body=event_body, sendUpdates="none",
        ).execute()
    except HttpError as e:
        return {"success": False, "error": f"Erreur creation RDV: {e}"}

    # 2. Ensuite supprimer le DISPO (le RDV est deja cree, donc pas de perte)
    try:
        service.events().delete(
            calendarId=s.google_calendar_id, eventId=dispo_event_id, sendUpdates="none",
        ).execute()
    except HttpError as e:
        print(f"Warning: DISPO non supprime ({dispo_event_id}): {e}")

    return {"success": True, "event_id": ev.get("id"), "html_link": ev.get("htmlLink")}


# -- SMTP EMAIL -------------------------------------------------

def _email_template(title, content):
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head>
    <body style="margin:0;padding:0;background:#f0f5f3;font-family:'Segoe UI',Arial,sans-serif">
    <div style="max-width:600px;margin:24px auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08)">
    <div style="background:linear-gradient(135deg,#1a4d3e,#2d6a4f);padding:28px 32px;text-align:center">
      <h1 style="color:#fff;font-size:22px;margin:0">Cabinet du Dr Bassem Khiri</h1>
      <p style="color:rgba(255,255,255,0.7);font-size:13px;margin:6px 0 0">Medecine Generale - Ennasr II, Ariana</p>
    </div>
    <div style="padding:28px 32px"><h2 style="color:#1a4d3e;font-size:18px;margin:0 0 16px">{title}</h2>{content}</div>
    <div style="background:#f8faf9;padding:16px 32px;border-top:1px solid #e8f0ed;text-align:center">
      <p style="color:#6b7c74;font-size:12px;margin:0">74, Avenue Hedi NOUIRA - Ennasr II | 98 33 19 25</p>
    </div></div></body></html>"""

def _send_email(to, subject, html_body):
    s = get_settings()
    msg = MIMEMultipart("alternative")
    msg["To"] = to
    msg["From"] = f"Cabinet Dr Khiri <{s.smtp_email}>"
    msg["Subject"] = subject
    plain = re.sub(r"<[^>]+>", "", html_body.replace("<br>","\n").replace("</p>","\n"))
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(s.smtp_email, s.smtp_app_password)
            server.send_message(msg)
        return {"success": True}
    except Exception as e:
        print(f"Erreur envoi email: {e}")
        return {"success": False, "error": str(e)}

def send_confirmation_to_doctor(date_str, time_str, patient_name, patient_phone, patient_email, reason=""):
    s = get_settings()
    content = f"""<div style="background:#f0f5f3;border-radius:12px;padding:18px"><table style="width:100%;border-collapse:collapse">
    <tr><td style="padding:6px 0;color:#6b7c74">Date</td><td style="color:#1a3a2e;font-weight:600">{date_str}</td></tr>
    <tr><td style="padding:6px 0;color:#6b7c74">Heure</td><td style="color:#1a3a2e;font-weight:600">{time_str}</td></tr>
    <tr><td style="padding:6px 0;color:#6b7c74">Patient</td><td style="color:#1a3a2e;font-weight:600">{patient_name}</td></tr>
    <tr><td style="padding:6px 0;color:#6b7c74">Tel</td><td style="color:#1a3a2e;font-weight:600">{patient_phone}</td></tr>
    <tr><td style="padding:6px 0;color:#6b7c74">Email</td><td style="color:#1a3a2e;font-weight:600">{patient_email or 'Non fourni'}</td></tr>
    <tr><td style="padding:6px 0;color:#6b7c74">Motif</td><td style="color:#1a3a2e;font-weight:600">{reason or 'Consultation'}</td></tr>
    </table></div>"""
    return _send_email(s.doctor_email, f"Nouveau RDV - {patient_name} - {date_str}", _email_template("Nouveau Rendez-vous", content))

def send_confirmation_to_patient(patient_email, patient_name, date_str, time_str):
    if not patient_email: return {"success": False, "error": "Pas d'email"}
    content = f"""<p style="color:#2c3e35">Bonjour <strong>{patient_name}</strong>,</p>
    <p style="color:#2c3e35">Votre rendez-vous est confirme :</p>
    <div style="background:#f0f5f3;border-radius:12px;padding:18px;margin:16px 0"><table style="width:100%;border-collapse:collapse">
    <tr><td style="padding:8px 0;color:#6b7c74">Date</td><td style="color:#1a3a2e;font-weight:600">{date_str}</td></tr>
    <tr><td style="padding:8px 0;color:#6b7c74">Heure</td><td style="color:#1a3a2e;font-weight:600">{time_str}</td></tr>
    <tr><td style="padding:8px 0;color:#6b7c74">Adresse</td><td style="color:#1a3a2e;font-weight:600">74, Avenue Hedi NOUIRA - Ennasr II</td></tr>
    </table></div>
    <div style="background:#fef9f0;border:1px solid #f0e0c8;border-radius:12px;padding:14px;margin:16px 0">
    <p style="color:#7a6540;font-size:13px;margin:0">En cas d'annulation, appelez le <strong>98 33 19 25</strong>.</p></div>"""
    return _send_email(patient_email, f"Confirmation RDV - {date_str} - Cabinet Dr Khiri", _email_template("Confirmation de votre RDV", content))
