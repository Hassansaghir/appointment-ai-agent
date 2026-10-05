from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import and_, text

from whatsapp_routes import router as whatsapp_router

from fastapi.middleware.cors import CORSMiddleware

from google.genai import errors

from groq import APIError as GroqAPIError, RateLimitError as GroqRateLimitError

from services.scheduler import (
    start_daily_summary_scheduler,
    stop_daily_summary_scheduler,
)

from pydantic import BaseModel

from datetime import date, time, datetime, timedelta

import logging

from database import Base, engine, get_db
from models import Doctor, Patient, Appointment,Message, Clinic

from config import (
    APPOINTMENT_DURATION,
    CLINIC_ID,
    CLINIC_NAME,
    DOCTOR_NAME,
    DOCTOR_SPECIALTY,
    END_TIME,
    START_TIME,
    WORKING_DAYS,
)

from database import SessionLocal

from ai_agent import run_agent

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="AI Appointment Agent",
    version="1.0.0"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(whatsapp_router)

# =========================================================
# CREATE DATABASE TABLES
# =========================================================

Base.metadata.create_all(bind=engine)

class ChatRequest(BaseModel):
    session_id: str
    message: str


# =========================================================
# WHATSAPP QR BRIDGE (Baileys)
# =========================================================

class BridgeMessageRequest(BaseModel):
    phone: str
    text: str


@app.post("/bridge/message")
def bridge_message(request: BridgeMessageRequest):
    session_id = f"whatsapp_{request.phone}"
    response = run_agent(session_id, request.text, request.phone)
    return {"response": response}

# =========================================================
# REQUEST MODELS
# =========================================================

class AppointmentRequest(BaseModel):

    patient_name: str
    phone: str
    appointment_date: date
    appointment_time: time


# =========================================================
# ROOT
# =========================================================

@app.get("/")
def root():

    return {
        "message": "AI Appointment Agent API is running"
    }


@app.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "up"}
    except Exception:
        return {"status": "degraded", "database": "down"}

@app.on_event("startup")
def start_background_jobs():
    start_daily_summary_scheduler()


@app.on_event("shutdown")
def stop_background_jobs():
    stop_daily_summary_scheduler()
# =========================================================
# CREATE DEFAULT DOCTOR
# =========================================================

@app.post("/setup")
def setup_database(
    db: Session = Depends(get_db)
):

    existing_doctor = db.query(Doctor).filter(Doctor.clinic_id == CLINIC_ID).first()

    if existing_doctor:

        return {
            "message": "Doctor already exists."
        }

    clinic = db.query(Clinic).filter(Clinic.id == CLINIC_ID).first()
    if not clinic:
        clinic = Clinic(id=CLINIC_ID, name=CLINIC_NAME)
        db.add(clinic)
        db.commit()
        db.refresh(clinic)

    doctor = Doctor(
        clinic_id=CLINIC_ID,
        name=DOCTOR_NAME,
        specialty=DOCTOR_SPECIALTY,
        start_time=START_TIME,
        end_time=END_TIME,
        appointment_duration=APPOINTMENT_DURATION
    )


    db.add(doctor)
    db.commit()
    db.refresh(doctor)


    return {
        "message": "Doctor created successfully.",
        "doctor_id": doctor.id
    }


# =========================================================
# GET DOCTOR
# =========================================================

@app.get("/doctor")
def get_doctor(
    db: Session = Depends(get_db)
):

    doctor = db.query(Doctor).filter(Doctor.clinic_id == CLINIC_ID).first()

    if not doctor:

        raise HTTPException(
            status_code=404,
            detail="Doctor not found. Run /setup first."
        )


    return {
        "id": doctor.id,
        "name": doctor.name,
        "specialty": doctor.specialty,
        "start_time": doctor.start_time,
        "end_time": doctor.end_time,
        "appointment_duration": doctor.appointment_duration
    }


# =========================================================
# AVAILABILITY
# =========================================================

@app.get("/availability")
def get_availability(
    appointment_date: date,
    db: Session = Depends(get_db)
):

    doctor = db.query(Doctor).filter(Doctor.clinic_id == CLINIC_ID).first()

    if not doctor:

        raise HTTPException(
            status_code=404,
            detail="Doctor not found. Run /setup first."
        )


    # Monday-Friday
    working_days = WORKING_DAYS


    if appointment_date.weekday() not in working_days:

        return {
            "date": appointment_date,
            "available": False,
            "message": "Doctor does not work on this day.",
            "slots": []
        }


    slots = []


    current_datetime = datetime.combine(
        appointment_date,
        doctor.start_time
    )


    end_datetime = datetime.combine(
        appointment_date,
        doctor.end_time
    )


    duration = timedelta(
        minutes=doctor.appointment_duration
    )


    while current_datetime + duration <= end_datetime:

        current_time = current_datetime.time()


        appointment = db.query(Appointment).filter(
            and_(
                Appointment.doctor_id == doctor.id,
                Appointment.clinic_id == CLINIC_ID,
                Appointment.appointment_date == appointment_date,
                Appointment.appointment_time == current_time,
                Appointment.status == "confirmed"
            )
        ).first()


        if not appointment:

            slots.append(
                current_time.strftime("%H:%M")
            )


        current_datetime += duration


    return {
        "date": appointment_date,
        "available": len(slots) > 0,
        "slots": slots
    }

# =========================================================
# Chat with AI Agent 
# =========================================================
@app.post("/chat")
def chat(request: ChatRequest):
    try:
        response = run_agent(
            request.session_id,
            request.message
        )

        return {"response": response}

    except errors.APIError as e:
        print(f"Gemini API error: {e}")

        if getattr(e, "code", None) == 429:
            raise HTTPException(
                status_code=503,
                detail=(
                    "The AI service has reached its usage limit. "
                    "Please try again after the quota resets."
                )
            )

        raise HTTPException(
            status_code=502,
            detail="The AI service is temporarily unavailable."
        )

    except GroqRateLimitError:
        raise HTTPException(
            status_code=503,
            detail=(
                "The AI service has reached its usage limit. "
                "Please try again after the quota resets."
            )
        )

    except GroqAPIError:
        raise HTTPException(
            status_code=502,
            detail="The AI service is temporarily unavailable."
        )


# =========================================================
# BOOK APPOINTMENT
# =========================================================

@app.post("/appointments")
def book_appointment(
    request: AppointmentRequest,
    db: Session = Depends(get_db)
):

    doctor = db.query(Doctor).filter(Doctor.clinic_id == CLINIC_ID).first()


    if not doctor:

        raise HTTPException(
            status_code=404,
            detail="Doctor not found. Run /setup first."
        )


    # -----------------------------------------------------
    # Check working day
    # -----------------------------------------------------

    working_days = WORKING_DAYS


    if request.appointment_date.weekday() not in working_days:

        raise HTTPException(
            status_code=400,
            detail="Doctor does not work on this day."
        )


    # -----------------------------------------------------
    # Check working hours
    # -----------------------------------------------------

    if request.appointment_time < doctor.start_time:

        raise HTTPException(
            status_code=400,
            detail="Appointment is before working hours."
        )


    if request.appointment_time >= doctor.end_time:

        raise HTTPException(
            status_code=400,
            detail="Appointment is after working hours."
        )


    # -----------------------------------------------------
    # Check existing appointment
    # -----------------------------------------------------

    existing_appointment = db.query(Appointment).filter(
        and_(
            Appointment.doctor_id == doctor.id,
            Appointment.clinic_id == CLINIC_ID,
            Appointment.appointment_date == request.appointment_date,
            Appointment.appointment_time == request.appointment_time,
            Appointment.status == "confirmed"
        )
    ).first()


    if existing_appointment:

        raise HTTPException(
            status_code=409,
            detail="This appointment slot is already booked."
        )


    # -----------------------------------------------------
    # Find or create patient
    # -----------------------------------------------------

    patient = db.query(Patient).filter(
        Patient.phone == request.phone,
        Patient.clinic_id == CLINIC_ID
    ).first()


    if not patient:

        patient = Patient(
            name=request.patient_name,
            phone=request.phone
        )

        db.add(patient)
        db.commit()
        db.refresh(patient)

    else:

        patient.name = request.patient_name

        db.commit()


    # -----------------------------------------------------
    # Create appointment
    # -----------------------------------------------------

    appointment = Appointment(

        clinic_id=CLINIC_ID,

        patient_id=patient.id,

        doctor_id=doctor.id,

        appointment_date=request.appointment_date,

        appointment_time=request.appointment_time,

        status="confirmed"
    )


    db.add(appointment)

    db.commit()

    db.refresh(appointment)


    return {

        "success": True,

        "message": "Appointment booked successfully.",

        "appointment": {

            "id": appointment.id,

            "doctor": doctor.name,

            "patient": patient.name,

            "phone": patient.phone,

            "date": appointment.appointment_date,

            "time": appointment.appointment_time,

            "status": appointment.status
        }
    }

@app.get("/conversations/{session_id}")
def get_conversation(session_id: str):
    db = SessionLocal()

    try:
        messages = (
            db.query(Message)
            .filter(
                Message.session_id == session_id
            )
            .order_by(Message.created_at.asc())
            .all()
        )

        return {
            "session_id": session_id,
            "messages": [
                {
                    "id": message.id,
                    "role": message.role,
                    "content": message.content,
                    "created_at": message.created_at
                }
                for message in messages
            ]
        }

    finally:
        db.close()