
import logging
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from database import SessionLocal
from models import Appointment, Patient, Doctor
from services.whatsapp_service import send_whatsapp_text_message
from config import CLINIC_ID, CLINIC_NAME, CLINIC_TIMEZONE

logger = logging.getLogger(__name__)


def _format_time(value) -> str:
    if hasattr(value, "strftime"):
        return value.strftime("%I:%M %p").lstrip("0")
    return str(value)


def build_reminder_text(patient_name: str, appointment_date, appointment_time, doctor_name: str) -> str:
    date_str = appointment_date.strftime("%A, %d %B %Y")
    time_str = _format_time(appointment_time)
    return (
        f"Hi {patient_name}, this is a reminder from {CLINIC_NAME}.\n"
        f"Your appointment with Dr. {doctor_name} is on {date_str} at {time_str}.\n"
        f"مرحباً {patient_name}، هذا تذكير من {CLINIC_NAME}.\n"
        f"موعدك مع د. {doctor_name} يوم {date_str} الساعة {time_str}.\n"
        "Please reply here if you need to cancel or reschedule."
    )


def send_tomorrow_reminders() -> None:
    """Send a WhatsApp reminder to every patient with a confirmed appointment tomorrow."""

    clinic_timezone = ZoneInfo(CLINIC_TIMEZONE)
    tomorrow = (datetime.now(clinic_timezone).date() + timedelta(days=1))

    db = SessionLocal()

    try:
        rows = (
            db.query(Appointment, Patient, Doctor)
            .join(Patient, Appointment.patient_id == Patient.id)
            .join(Doctor, Appointment.doctor_id == Doctor.id)
            .filter(
                Appointment.clinic_id == CLINIC_ID,
                Appointment.appointment_date == tomorrow,
                Appointment.status == "confirmed",
            )
            .order_by(Appointment.appointment_time)
            .all()
        )

        if not rows:
            logger.info("No appointments tomorrow; no reminders sent.")
            return

        for appointment, patient, doctor in rows:
            try:
                text = build_reminder_text(
                    patient.name,
                    appointment.appointment_date,
                    appointment.appointment_time,
                    doctor.name,
                )
                send_whatsapp_text_message(recipient=patient.phone, text=text)
                logger.info("Reminder sent to %s for %s.", patient.phone, tomorrow)
            except Exception:
                logger.exception("Failed to send reminder to patient %s.", patient.id)

    finally:
        db.close()
