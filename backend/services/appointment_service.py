from datetime import date

from database import SessionLocal
from models import Appointment, Conversation, Doctor, Patient


def get_patient_appointments(patient_id: int):
    """
    Return upcoming confirmed appointments
    for the authenticated patient.
    """

    db = SessionLocal()

    try:
        appointments = (
            db.query(Appointment)
            .filter(
                Appointment.patient_id == patient_id,
                Appointment.appointment_date >= date.today(),
                Appointment.status == "confirmed"
            )
            .order_by(
                Appointment.appointment_date.asc(),
                Appointment.appointment_time.asc()
            )
            .all()
        )

        if not appointments:
            return {
                "success": True,
                "appointments": [],
                "message": "You have no upcoming appointments."
            }

        results = []

        for appointment in appointments:

            doctor = (
                db.query(Doctor)
                .filter(
                    Doctor.id == appointment.doctor_id
                )
                .first()
            )

            results.append({
                "appointment_id": appointment.id,
                "doctor": doctor.name if doctor else "Unknown",
                "date": appointment.appointment_date.isoformat(),
                "time": appointment.appointment_time.strftime("%H:%M"),
                "status": appointment.status
            })

        return {
            "success": True,
            "appointments": results
        }

    finally:
        db.close()


def get_patient_by_phone(phone: str):
    """
    Find a patient by phone number.
    """

    db = SessionLocal()

    try:
        patient = (
            db.query(Patient)
            .filter(Patient.phone == phone)
            .first()
        )

        return patient

    finally:
        db.close()

def get_or_create_patient_conversation(
    session_id: str,
    patient_id: int,
    interaction_id: str
):
    """
    Get the conversation for a session.
    If it does not exist, create it and associate it
    with the authenticated patient.
    """

    db = SessionLocal()

    try:
        conversation = (
            db.query(Conversation)
            .filter(
                Conversation.session_id == session_id
            )
            .first()
        )

        if conversation:

            # Security check:
            # A session cannot be reassigned to another patient.
            if conversation.patient_id != patient_id:
                return {
                    "success": False,
                    "error": "This session belongs to another patient."
                }

            return {
                "success": True,
                "conversation": conversation
            }

        conversation = Conversation(
            session_id=session_id,
            patient_id=patient_id,
            interaction_id=interaction_id
        )

        db.add(conversation)
        db.commit()
        db.refresh(conversation)

        return {
            "success": True,
            "conversation": conversation
        }

    finally:
        db.close()