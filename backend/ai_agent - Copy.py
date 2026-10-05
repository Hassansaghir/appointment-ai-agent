import os
import json
from datetime import date, datetime, timedelta

from datetime import date

from collections import defaultdict

from dotenv import load_dotenv
from google import genai

from database import SessionLocal
from models import Doctor, Patient, Appointment,Conversation,Message


load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

MODEL = "gemini-3.7-flash"


# ============================================================
# APPOINTMENT TOOLS
# ============================================================

def check_availability(appointment_date: str):
    """
    Return all available appointment slots for the doctor
    on the requested date.
    """

    db = SessionLocal()

    try:
        doctor = db.query(Doctor).first()

        if not doctor:
            return {
                "success": False,
                "error": "Doctor not found."
            }

        requested_date = date.fromisoformat(appointment_date)

        # Monday = 0
        # Friday = 4
        if requested_date.weekday() not in [0, 1, 2, 3, 4]:
            return {
                "success": True,
                "date": appointment_date,
                "slots": []
            }

        slots = []

        current_datetime = datetime.combine(
            requested_date,
            doctor.start_time
        )

        end_datetime = datetime.combine(
            requested_date,
            doctor.end_time
        )

        duration = timedelta(
            minutes=doctor.appointment_duration
        )

        while current_datetime + duration <= end_datetime:

            current_time = current_datetime.time()

            existing_appointment = db.query(Appointment).filter(
                Appointment.doctor_id == doctor.id,
                Appointment.appointment_date == requested_date,
                Appointment.appointment_time == current_time,
                Appointment.status == "confirmed"
            ).first()

            if not existing_appointment:
                slots.append(
                    current_time.strftime("%H:%M")
                )

            current_datetime += duration

        return {
            "success": True,
            "date": appointment_date,
            "slots": slots
        }

    finally:
        db.close()


def book_appointment(
    patient_name: str,
    phone: str,
    appointment_date: str,
    appointment_time: str
):
    """
    Book an appointment for a patient.
    """

    db = SessionLocal()

    try:
        doctor = db.query(Doctor).first()

        if not doctor:
            return {
                "success": False,
                "error": "Doctor not found."
            }

        requested_date = date.fromisoformat(
            appointment_date
        )

        requested_time = datetime.strptime(
            appointment_time,
            "%H:%M"
        ).time()

        # ----------------------------------------------------
        # Check working day
        # ----------------------------------------------------

        if requested_date.weekday() not in [0, 1, 2, 3, 4]:
            return {
                "success": False,
                "error": "The doctor does not work on this day."
            }

        # ----------------------------------------------------
        # Check working hours
        # ----------------------------------------------------

        if requested_time < doctor.start_time:
            return {
                "success": False,
                "error": "The requested time is before working hours."
            }

        if requested_time >= doctor.end_time:
            return {
                "success": False,
                "error": "The requested time is after working hours."
            }

        # ----------------------------------------------------
        # Check that time matches appointment duration
        # ----------------------------------------------------

        requested_datetime = datetime.combine(
            requested_date,
            requested_time
        )

        start_datetime = datetime.combine(
            requested_date,
            doctor.start_time
        )

        minutes_from_start = int(
            (requested_datetime - start_datetime).total_seconds() / 60
        )

        if minutes_from_start % doctor.appointment_duration != 0:
            return {
                "success": False,
                "error": "The requested time is not a valid appointment slot."
            }

        # ----------------------------------------------------
        # Check if slot already exists
        # ----------------------------------------------------

        existing = db.query(Appointment).filter(
            Appointment.doctor_id == doctor.id,
            Appointment.appointment_date == requested_date,
            Appointment.appointment_time == requested_time,
            Appointment.status == "confirmed"
        ).first()

        if existing:
            return {
                "success": False,
                "error": "This appointment time is already booked."
            }

        # ----------------------------------------------------
        # Find existing patient
        # ----------------------------------------------------

        patient = db.query(Patient).filter(
            Patient.phone == phone
        ).first()

        if not patient:

            patient = Patient(
                name=patient_name,
                phone=phone
            )

            db.add(patient)
            db.commit()
            db.refresh(patient)

        else:

            patient.name = patient_name

            db.commit()

        # ----------------------------------------------------
        # Create appointment
        # ----------------------------------------------------

        appointment = Appointment(
            patient_id=patient.id,
            doctor_id=doctor.id,
            appointment_date=requested_date,
            appointment_time=requested_time,
            status="confirmed"
        )

        db.add(appointment)

        db.commit()

        db.refresh(appointment)

        return {
            "success": True,
            "appointment_id": appointment.id,
            "doctor": doctor.name,
            "patient": patient.name,
            "date": appointment_date,
            "time": appointment_time,
            "status": "confirmed"
        }

    finally:
        db.close()

def cancel_appointment(
        
    phone: str,
    appointment_date: str,
    appointment_time: str
):
    """
    Cancel a patient's confirmed appointment.
    """

    db = SessionLocal()

    try:
        requested_date = date.fromisoformat(
            appointment_date
        )

        requested_time = datetime.strptime(
            appointment_time,
            "%H:%M"
        ).time()

        # Find the patient
        patient = db.query(Patient).filter(
            Patient.phone == phone
        ).first()

        if not patient:
            return {
                "success": False,
                "error": "No patient was found with this phone number."
            }

        # Find the appointment
        appointment = db.query(Appointment).filter(
            Appointment.patient_id == patient.id,
            Appointment.appointment_date == requested_date,
            Appointment.appointment_time == requested_time,
            Appointment.status == "confirmed"
        ).first()

        if not appointment:
            return {
                "success": False,
                "error": "No confirmed appointment was found at this date and time."
            }

        # Cancel appointment
        appointment.status = "cancelled"

        db.commit()

        return {
            "success": True,
            "message": "Appointment cancelled successfully.",
            "appointment_id": appointment.id,
            "patient": patient.name,
            "date": appointment_date,
            "time": appointment_time,
            "status": "cancelled"
        }

    finally:
        db.close()
def reschedule_appointment(
    phone: str,
    old_appointment_date: str,
    old_appointment_time: str,
    new_appointment_date: str,
    new_appointment_time: str
):
    """
    Reschedule an existing confirmed appointment.
    """

    db = SessionLocal()

    try:
        old_date = date.fromisoformat(
            old_appointment_date
        )

        old_time = datetime.strptime(
            old_appointment_time,
            "%H:%M"
        ).time()

        new_date = date.fromisoformat(
            new_appointment_date
        )

        new_time = datetime.strptime(
            new_appointment_time,
            "%H:%M"
        ).time()

        # ----------------------------------------------------
        # Find patient
        # ----------------------------------------------------

        patient = db.query(Patient).filter(
            Patient.phone == phone
        ).first()

        if not patient:
            return {
                "success": False,
                "error": "No patient was found with this phone number."
            }

        # ----------------------------------------------------
        # Find existing appointment
        # ----------------------------------------------------

        appointment = db.query(Appointment).filter(
            Appointment.patient_id == patient.id,
            Appointment.appointment_date == old_date,
            Appointment.appointment_time == old_time,
            Appointment.status == "confirmed"
        ).first()

        if not appointment:
            return {
                "success": False,
                "error": "No confirmed appointment was found at the old date and time."
            }

        # ----------------------------------------------------
        # Find doctor
        # ----------------------------------------------------

        doctor = db.query(Doctor).filter(
            Doctor.id == appointment.doctor_id
        ).first()

        if not doctor:
            return {
                "success": False,
                "error": "Doctor not found."
            }

        # ----------------------------------------------------
        # Check working day
        # ----------------------------------------------------

        if new_date.weekday() not in [0, 1, 2, 3, 4]:
            return {
                "success": False,
                "error": "The doctor does not work on the new date."
            }

        # ----------------------------------------------------
        # Check working hours
        # ----------------------------------------------------

        if new_time < doctor.start_time:
            return {
                "success": False,
                "error": "The new appointment time is before working hours."
            }

        if new_time >= doctor.end_time:
            return {
                "success": False,
                "error": "The new appointment time is after working hours."
            }

        # ----------------------------------------------------
        # Check valid appointment slot
        # ----------------------------------------------------

        new_datetime = datetime.combine(
            new_date,
            new_time
        )

        start_datetime = datetime.combine(
            new_date,
            doctor.start_time
        )

        minutes_from_start = int(
            (
                new_datetime - start_datetime
            ).total_seconds() / 60
        )

        if minutes_from_start % doctor.appointment_duration != 0:
            return {
                "success": False,
                "error": "The new time is not a valid appointment slot."
            }

        # ----------------------------------------------------
        # Check new slot availability
        # ----------------------------------------------------

        existing_appointment = db.query(Appointment).filter(
            Appointment.doctor_id == doctor.id,
            Appointment.appointment_date == new_date,
            Appointment.appointment_time == new_time,
            Appointment.status == "confirmed",
            Appointment.id != appointment.id
        ).first()

        if existing_appointment:
            return {
                "success": False,
                "error": "The new appointment time is already booked."
            }

        # ----------------------------------------------------
        # Update appointment
        # ----------------------------------------------------

        appointment.appointment_date = new_date
        appointment.appointment_time = new_time

        db.commit()
        db.refresh(appointment)

        return {
            "success": True,
            "message": "Appointment rescheduled successfully.",
            "appointment_id": appointment.id,
            "patient": patient.name,
            "doctor": doctor.name,
            "old_date": old_appointment_date,
            "old_time": old_appointment_time,
            "new_date": new_appointment_date,
            "new_time": new_appointment_time,
            "status": appointment.status
        }

    finally:
        db.close()
def get_patient_appointments(phone: str):
    """
    Return upcoming confirmed appointments for a patient.
    """

    db = SessionLocal()

    try:
        # Find patient
        patient = db.query(Patient).filter(
            Patient.phone == phone
        ).first()

        if not patient:
            return {
                "success": False,
                "error": "No patient was found with this phone number."
            }

        today = date.today()

        # Find upcoming confirmed appointments
        appointments = (
            db.query(Appointment)
            .filter(
                Appointment.patient_id == patient.id,
                Appointment.appointment_date >= today,
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
                "patient": patient.name,
                "appointments": [],
                "message": "The patient has no upcoming appointments."
            }

        results = []

        for appointment in appointments:

            doctor = db.query(Doctor).filter(
                Doctor.id == appointment.doctor_id
            ).first()

            results.append({
                "appointment_id": appointment.id,
                "doctor": doctor.name if doctor else "Unknown",
                "date": appointment.appointment_date.isoformat(),
                "time": appointment.appointment_time.strftime("%H:%M"),
                "status": appointment.status
            })

        return {
            "success": True,
            "patient": patient.name,
            "appointments": results
        }

    finally:
        db.close()
# ============================================================
# GEMINI TOOLS
# ============================================================

check_availability_tool = {
    "type": "function",
    "name": "check_availability",
    "description": (
        "Check which appointment times are available "
        "for Dr. Ahmad on a specific date."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "appointment_date": {
                "type": "string",
                "description": "Date in YYYY-MM-DD format."
            }
        },
        "required": ["appointment_date"]
    }
}


book_appointment_tool = {
    "type": "function",
    "name": "book_appointment",
    "description": (
        "Book an appointment for a patient. "
        "Only call this after the patient has clearly "
        "selected a specific available appointment time."
    ),
    "parameters": {
        "type": "object",
        "properties": {

            "patient_name": {
                "type": "string",
                "description": "Full name of the patient."
            },

            "phone": {
                "type": "string",
                "description": "Patient phone number."
            },

            "appointment_date": {
                "type": "string",
                "description": "Date in YYYY-MM-DD format."
            },

            "appointment_time": {
                "type": "string",
                "description": "Time in HH:MM format."
            }

        },
        "required": [
            "patient_name",
            "phone",
            "appointment_date",
            "appointment_time"
        ]
    }
}
cancel_appointment_tool = {
    "type": "function",
    "name": "cancel_appointment",
    "description": (
        "Cancel a patient's confirmed appointment. "
        "Only call this when the patient clearly wants "
        "to cancel an existing appointment."
    ),
    "parameters": {
        "type": "object",
        "properties": {

            "phone": {
                "type": "string",
                "description": "Patient phone number."
            },

            "appointment_date": {
                "type": "string",
                "description": "Appointment date in YYYY-MM-DD format."
            },

            "appointment_time": {
                "type": "string",
                "description": "Appointment time in HH:MM format."
            }

        },
        "required": [
            "phone",
            "appointment_date",
            "appointment_time"
        ]
    }
}
reschedule_appointment_tool = {
    "type": "function",
    "name": "reschedule_appointment",
    "description": (
        "Move an existing confirmed appointment to a new date "
        "and time. Only call this after the patient clearly "
        "requests a reschedule and the new time has been checked "
        "for availability."
    ),
    "parameters": {
        "type": "object",
        "properties": {

            "phone": {
                "type": "string",
                "description": "Patient phone number."
            },

            "old_appointment_date": {
                "type": "string",
                "description": "Current appointment date in YYYY-MM-DD format."
            },

            "old_appointment_time": {
                "type": "string",
                "description": "Current appointment time in HH:MM format."
            },

            "new_appointment_date": {
                "type": "string",
                "description": "New appointment date in YYYY-MM-DD format."
            },

            "new_appointment_time": {
                "type": "string",
                "description": "New appointment time in HH:MM format."
            }

        },
        "required": [
            "phone",
            "old_appointment_date",
            "old_appointment_time",
            "new_appointment_date",
            "new_appointment_time"
        ]
    }
}
get_patient_appointments_tool = {
    "type": "function",
    "name": "get_patient_appointments",
    "description": (
        "Find all upcoming confirmed appointments for a patient "
        "using their phone number."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "phone": {
                "type": "string",
                "description": "Patient phone number."
            }
        },
        "required": [
            "phone"
        ]
    }
}
TOOLS = [
    check_availability_tool,
    book_appointment_tool,
    cancel_appointment_tool,
    reschedule_appointment_tool,
    get_patient_appointments_tool
]

# ============================================================
# SYSTEM INSTRUCTIONS
# ============================================================
SYSTEM_INSTRUCTION = f"""
You are an AI appointment receptionist for Dr. Ahmad's dental clinic.

CURRENT DATE:
{date.today().isoformat()}

CURRENT DATE RULE:
The current date is exactly {date.today().isoformat()}.

DATE CONVERSION RULES:
You MUST convert relative dates yourself.

- "today" = {date.today().isoformat()}
- "tomorrow" = {(date.today() + timedelta(days=1)).isoformat()}
- "the day after tomorrow" = {(date.today() + timedelta(days=2)).isoformat()}

NEVER ask the patient to provide an exact date when the patient
has already clearly said "today", "tomorrow", or "the day after tomorrow".

Examples:

If the current date is 2026-10-01:
- today = 2026-10-01
- tomorrow = 2026-10-02
- the day after tomorrow = 2026-10-03

If the patient says:
"tomorrow at 11 AM"

You MUST interpret it as:
date = {(date.today() + timedelta(days=1)).isoformat()}
time = 11:00

Then use the appropriate tool.

YOUR RESPONSIBILITIES:

1. Help patients find available appointments.
2. Book appointments.
3. Cancel appointments.
4. Reschedule appointments.
5. Look up a patient's upcoming appointments.
6. Answer simple appointment-related questions.

APPOINTMENT RULES:

- Never invent appointment availability.
- Always use check_availability before telling the patient
  that a time is available.
- Never book an appointment unless the patient has clearly
  selected a specific available time.
- Never cancel an appointment based on an assumption.
- Never reschedule an appointment based on an assumption.
- Before booking, you must know:
    - patient name
    - phone number
    - date
    - time

- Before cancelling, you must know:
    - patient phone number
    - appointment date
    - appointment time

- Before rescheduling, you must know:
    - patient phone number
    - current appointment date
    - current appointment time
    - new appointment date
    - new appointment time

- For relative dates such as "tomorrow", "today", and
  "the day after tomorrow", calculate the date yourself.

- When rescheduling, ALWAYS check the NEW date and time
  using check_availability before calling reschedule_appointment.

- If the requested new time is unavailable, offer available times.

- If required information is genuinely missing, ask the patient
  for that specific information.

- Be friendly and concise.
- Respond in the same language as the patient.
- Do not provide medical advice.
- Only handle appointment-related requests.
- When a patient asks about their existing or upcoming appointments,
  use get_patient_appointments.
- You must have the patient's phone number before looking up
  their appointments.
- Never invent or assume an appointment.

DOCTOR:

Name:
Dr. Ahmad

Specialty:
Dentist

WORKING DAYS:

Monday-Friday

WORKING HOURS:

09:00-17:00

APPOINTMENT DURATION:

30 minutes.
"""
# ============================================================
# AGENT
# ============================================================



def run_agent(
    session_id: str,
    message: str,
    sender_phone: str = None
):
    db = SessionLocal()

    try:
        today = date.today()
        tomorrow = today + timedelta(days=1)
        day_after_tomorrow = today + timedelta(days=2)

        date_context = f"""
DATE CONTEXT:
Today is {today.isoformat()}.
Tomorrow is {tomorrow.isoformat()}.
The day after tomorrow is {day_after_tomorrow.isoformat()}.

IMPORTANT:
- If the patient says "tomorrow", use {tomorrow.isoformat()}.
- If the patient says "today", use {today.isoformat()}.
- If the patient says "the day after tomorrow",
  use {day_after_tomorrow.isoformat()}.
- Do not ask for an exact date when a relative date is clear.
"""

        # Use the WhatsApp sender's phone for appointment operations.
        phone_context = ""

        if sender_phone:
            phone_context = f"""
WHATSAPP SENDER:
The incoming WhatsApp sender phone number is {sender_phone}.

IMPORTANT PHONE RULES:
- Use this sender phone number for booking, viewing,
  cancelling, and rescheduling appointments.
- Do not ask the patient to repeat their phone number.
- Do not use a different phone number supplied in the
  message or generated by the AI for these operations.
"""

        agent_message = (
            date_context
            + phone_context
            + "\nPATIENT MESSAGE:\n"
            + message
        )

        # Save the patient's message.
        db.add(
            Message(
                session_id=session_id,
                role="user",
                content=message
            )
        )
        db.commit()

        # Find the existing conversation.
        conversation = (
            db.query(Conversation)
            .filter(
                Conversation.session_id == session_id
            )
            .first()
        )

        # Continue the existing Gemini conversation.
        if conversation:
            interaction = client.interactions.create(
                model=MODEL,
                previous_interaction_id=conversation.interaction_id,
                input=agent_message,
                tools=TOOLS
            )
        else:
            # Start a new Gemini conversation.
            interaction = client.interactions.create(
                model=MODEL,
                input=agent_message,
                system_instruction=SYSTEM_INSTRUCTION,
                tools=TOOLS
            )

        # Process tool calls until Gemini returns its final answer.
        while True:
            function_calls = [
                step
                for step in interaction.steps
                if step.type == "function_call"
            ]

            if not function_calls:
                break

            function_results = []

            for step in function_calls:
                print(f"AI TOOL CALL: {step.name}")
                print(f"ARGUMENTS: {step.arguments}")

                args = step.arguments

                if step.name == "check_availability":
                    result = check_availability(
                        args["appointment_date"]
                    )

                elif step.name == "book_appointment":
                    phone = sender_phone or args["phone"]

                    result = book_appointment(
                        args["patient_name"],
                        phone,
                        args["appointment_date"],
                        args["appointment_time"]
                    )

                elif step.name == "cancel_appointment":
                    phone = sender_phone or args["phone"]

                    result = cancel_appointment(
                        phone,
                        args["appointment_date"],
                        args["appointment_time"]
                    )

                elif step.name == "reschedule_appointment":
                    phone = sender_phone or args["phone"]

                    # Check the requested new time first.
                    availability_result = check_availability(
                        args["new_appointment_date"]
                    )

                    if (
                        availability_result["success"]
                        and args["new_appointment_time"]
                        in availability_result["slots"]
                    ):
                        result = reschedule_appointment(
                            phone,
                            args["old_appointment_date"],
                            args["old_appointment_time"],
                            args["new_appointment_date"],
                            args["new_appointment_time"]
                        )
                    else:
                        result = {
                            "success": False,
                            "error": (
                                "The requested new appointment "
                                "time is not available."
                            )
                        }

                elif step.name == "get_patient_appointments":
                    phone = sender_phone or args["phone"]

                    result = get_patient_appointments(phone)

                else:
                    result = {
                        "success": False,
                        "error": "Unknown tool."
                    }

                print(f"TOOL RESULT: {result}")

                function_results.append({
                    "type": "function_result",
                    "name": step.name,
                    "call_id": step.id,
                    "result": [
                        {
                            "type": "text",
                            "text": json.dumps(result)
                        }
                    ]
                })

            # Send the tool results back to Gemini.
            interaction = client.interactions.create(
                model=MODEL,
                previous_interaction_id=interaction.id,
                input=function_results,
                tools=TOOLS
            )

        # Save the latest Gemini interaction ID.
        if conversation:
            conversation.interaction_id = interaction.id
        else:
            conversation = Conversation(
                session_id=session_id,
                interaction_id=interaction.id
            )
            db.add(conversation)

        assistant_message = interaction.output_text

        # Save the assistant's response.
        db.add(
            Message(
                session_id=session_id,
                role="assistant",
                content=assistant_message
            )
        )

        db.commit()

        return assistant_message

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()

