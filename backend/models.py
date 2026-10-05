from datetime import datetime

from sqlalchemy import Column, Integer, String, Date, Time, DateTime, ForeignKey

from database import Base


class Clinic(Base):
    __tablename__ = "clinics"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    whatsapp_phone_number_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    clinic_id = Column(
        Integer,
        ForeignKey("clinics.id"),
        nullable=False,
        index=True,
    )

    name = Column(
        String(150),
        nullable=False
    )

    specialty = Column(
        String(150),
        nullable=False
    )

    start_time = Column(
        Time,
        nullable=False
    )

    end_time = Column(
        Time,
        nullable=False
    )

    appointment_duration = Column(
        Integer,
        nullable=False
    )


class Patient(Base):
    __tablename__ = "patients"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    clinic_id = Column(
        Integer,
        ForeignKey("clinics.id"),
        nullable=False,
        index=True,
    )

    name = Column(
        String(150),
        nullable=False
    )

    phone = Column(
        String(30),
        nullable=False,
        unique=True
    )


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    clinic_id = Column(
        Integer,
        ForeignKey("clinics.id"),
        nullable=False,
        index=True,
    )

    patient_id = Column(
        Integer,
        nullable=False
    )

    doctor_id = Column(
        Integer,
        nullable=False
    )

    appointment_date = Column(
        Date,
        nullable=False
    )

    appointment_time = Column(
        Time,
        nullable=False
    )

    status = Column(
        String(30),
        nullable=False,
        default="confirmed"
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    session_id = Column(
        String(255),
        unique=True,
        index=True,
        nullable=False
    )

    patient_id = Column(
        Integer,
        nullable=True,
        index=True
    )

    interaction_id = Column(
        String(255),
        nullable=False
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    session_id = Column(
        String(255),
        index=True,
        nullable=False
    )

    clinic_id = Column(
        Integer,
        ForeignKey("clinics.id"),
        nullable=True,
        index=True,
    )

    role = Column(
        String(30),
        nullable=False
    )

    content = Column(
        String(4000),
        nullable=False
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )