import re
from pydantic import BaseModel, Field, field_validator
from typing import Optional


class BookingRequest(BaseModel):
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    start_time: str = Field(..., pattern=r"^\d{2}:\d{2}$", description="Heure debut HH:MM")
    end_time: str = Field(..., pattern=r"^\d{2}:\d{2}$", description="Heure fin HH:MM")
    event_id: str = Field(..., min_length=1, description="ID de l'evenement DISPO")
    patient_name: str = Field(..., min_length=2, max_length=100)
    patient_phone: str = Field(..., max_length=30, description="Numéro de téléphone international")
    patient_email: Optional[str] = None
    reason: Optional[str] = Field(None, max_length=500)

    @field_validator("patient_phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        digits = re.sub(r"\D", "", v)
        if len(digits) < 8:
            raise ValueError("Le numéro de téléphone doit contenir au moins 8 chiffres.")
        if len(digits) > 15:
            raise ValueError("Le numéro de téléphone ne doit pas dépasser 15 chiffres.")
        return v.strip()


class BookingResponse(BaseModel):
    success: bool
    message: str
    event_id: Optional[str] = None
    calendar_link: Optional[str] = None
    email_doctor: Optional[dict] = None
    email_patient: Optional[dict] = None


class SlotInfo(BaseModel):
    start: str
    end: str
    label: str
    event_id: Optional[str] = None


class DaySlotsResponse(BaseModel):
    date: str
    slots: list[SlotInfo]


class MonthSlotsResponse(BaseModel):
    available_dates: dict[str, int]
