from sqlalchemy.orm import Session

from models import Patient


def create_patient(
    db: Session,
    name: str,
    phone: str
):
    existing_patient = (
        db.query(Patient)
        .filter(Patient.phone == phone)
        .first()
    )

    if existing_patient:
        return existing_patient

    patient = Patient(
        name=name,
        phone=phone
    )

    db.add(patient)
    db.commit()
    db.refresh(patient)

    return patient


def get_patient_by_id(
    db: Session,
    patient_id: int
):
    return (
        db.query(Patient)
        .filter(Patient.id == patient_id)
        .first()
    )


def get_patient_by_phone(
    db: Session,
    phone: str
):
    return (
        db.query(Patient)
        .filter(Patient.phone == phone)
        .first()
    )