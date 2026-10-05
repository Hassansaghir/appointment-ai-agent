import os
from datetime import time
from dotenv import load_dotenv

load_dotenv()


def _get_time(name: str, default: str) -> time:
    raw = os.getenv(name, default)
    hour, minute = map(int, raw.split(":"))
    return time(hour, minute)


# Clinic identity
CLINIC_NAME = os.getenv("CLINIC_NAME", "Dental Clinic")
DOCTOR_NAME = os.getenv("DOCTOR_NAME", "Dr. Ahmad")
DOCTOR_SPECIALTY = os.getenv("DOCTOR_SPECIALTY", "Dentist")

# Schedule
WORKING_DAYS = [
    int(d.strip())
    for d in os.getenv("WORKING_DAYS", "0,1,2,3,4").split(",")
    if d.strip().isdigit()
]
START_TIME = _get_time("START_TIME", "09:00")
END_TIME = _get_time("END_TIME", "17:00")
APPOINTMENT_DURATION = int(os.getenv("APPOINTMENT_DURATION", "30"))
CLINIC_TIMEZONE = os.getenv("CLINIC_TIMEZONE", "Asia/Beirut")

# Multi-clinic: which clinic this deployment serves
CLINIC_ID = int(os.getenv("CLINIC_ID", "1"))

# WhatsApp daily summary
WHATSAPP_DOCTOR_PHONE = os.getenv("WHATSAPP_DOCTOR_PHONE", "")
