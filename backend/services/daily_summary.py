
import logging
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from database import SessionLocal
from models import Appointment, Patient, Doctor
from services.whatsapp_service import send_daily_summary_template
from config import CLINIC_ID, CLINIC_TIMEZONE, WHATSAPP_DOCTOR_PHONE

logger = logging.getLogger(__name__)


def format_time(value) -> str:
    """Format either a Python time value or a string."""
    if hasattr(value, "strftime"):
        return value.strftime("%I:%M %p").lstrip("0")

    return str(value)


def build_daily_summary(db, target_date) -> str:
    """
    Read appointments for the requested date.

    Uses the existing model IDs rather than requiring
    new SQLAlchemy relationships.
    """

    rows = (
        db.query(Appointment, Patient, Doctor)
        .join(
            Patient,
            Appointment.patient_id == Patient.id,
        )
        .join(
            Doctor,
            Appointment.doctor_id == Doctor.id,
        )
        .filter(
            Appointment.clinic_id == CLINIC_ID,
            Appointment.appointment_date == target_date,
        )
        .order_by(Appointment.appointment_time)
        .all()
    )

    # Exclude cancelled appointments from the schedule.
    rows = [
        (appointment, patient, doctor)
        for appointment, patient, doctor in rows
        if str(appointment.status).lower() != "cancelled"
    ]

    if not rows:
        return "There are no scheduled appointments."

    lines = []

    for index, (appointment, patient, doctor) in enumerate(
        rows,
        start=1,
    ):
        lines.append(
            f"{index}. {format_time(appointment.appointment_time)}"
            f" - {patient.name}"
            f" - Dr. {doctor.name}"
            f" - {appointment.status}"
        )

    return "\n".join(lines)


def send_tomorrow_summary() -> None:
    """
    Send tomorrow's appointment list to the configured doctor.
    """

    clinic_timezone = ZoneInfo(CLINIC_TIMEZONE)

    now = datetime.now(clinic_timezone)
    tomorrow = now.date() + timedelta(days=1)

    recipient = WHATSAPP_DOCTOR_PHONE

    if not recipient:
        logger.error(
            "Daily summary skipped: "
            "WHATSAPP_DOCTOR_PHONE is not configured."
        )
        return

    db = SessionLocal()

    try:
        summary = build_daily_summary(db, tomorrow)

        result = send_daily_summary_template(
            recipient=recipient,
            appointment_date=tomorrow.strftime("%d %B %Y"),
            summary=summary,
        )

        logger.info(
            "WhatsApp daily summary accepted by the API "
            "for %s. Message ID: %s",
            tomorrow,
            (
                result.get("messages", [{}])[0].get("id")
                if result.get("messages")
                else "not returned"
            ),
        )

    except Exception:
        logger.exception(
            "Failed to send the daily appointment summary."
        )

    finally:
        db.close()