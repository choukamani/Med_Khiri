from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
import os


class Settings(BaseSettings):
    # Google Service Account (Calendar - never expires)
    google_service_account_file: str = Field(
        default="meidcal-platform-80f8ef4be549.json",
        description="Path to Google Service Account JSON key file",
    )

    # SMTP for emails (App Password - never expires)
    smtp_email: str = Field(..., description="Gmail address to send from")
    smtp_app_password: str = Field(..., description="Gmail App Password (16 chars)")

    # Doctor configuration
    doctor_email: str = Field(..., description="Doctor's email address")
    google_calendar_id: str = Field(..., description="Google Calendar ID")

    # Application settings
    frontend_url: str = Field(default="http://localhost:8006")
    api_secret_key: str = Field(default="change-me")
    port: int = Field(default=int(os.getenv("PORT", "8080")))
    debug: bool = Field(default=False)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
