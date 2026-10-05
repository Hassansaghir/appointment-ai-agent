from database import SessionLocal
from models import Patient


def authenticate_patient(phone: str):
    """
    Find a patient using their phone number.

    This is the first step of patient authentication.
    Later this will be protected with OTP verification.
    """

    db = SessionLocal()

    try:
        patient = (
            db.query(Patient)
            .filter(Patient.phone == phone)
            .first()
        )

        if not patient:
            return {
                "success": False,
                "error": "Patient not found."
            }

        return {
            "success": True,
            "patient_id": patient.id,
            "patient_name": patient.name
        }

    finally:
        db.close()