import os
import json
from datetime import date, datetime, timedelta



from dotenv import load_dotenv
from groq import Groq

from config import (
    APPOINTMENT_DURATION,
    CLINIC_ID,
    CLINIC_NAME,
    CLINIC_TIMEZONE,
    DOCTOR_NAME,
    DOCTOR_SPECIALTY,
    END_TIME,
    START_TIME,
    WORKING_DAYS,
)
from database import SessionLocal
from models import Doctor, Patient, Appointment,Conversation,Message


load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise ValueError("GROQ_API_KEY not found in .env")

client = Groq(api_key=api_key)

MODEL="openai/gpt-oss-120b"


def build_google_calendar_link(appointment_date: str, appointment_time: str, duration_minutes: int = 30) -> str:
    """
    Build a Google Calendar 'Add Event' link for an appointment.
    """
    start = datetime.strptime(f"{appointment_date} {appointment_time}", "%Y-%m-%d %H:%M")
    end = start + timedelta(minutes=duration_minutes)
    fmt = "%Y%m%dT%H%M%S"
    dates = f"{start.strftime(fmt)}/{end.strftime(fmt)}"
    from urllib.parse import quote
    return (
        "https://calendar.google.com/calendar/render?action=TEMPLATE"
        f"&text={quote(f'Appointment with {DOCTOR_NAME}')}"
        f"&dates={dates}"
        f"&details={quote(f'{DOCTOR_SPECIALTY} appointment booked via WhatsApp')}"
        f"&ctz={CLINIC_TIMEZONE}"
    )



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
        doctor = db.query(Doctor).filter(Doctor.clinic_id == CLINIC_ID).first()

        if not doctor:
            return {
                "success": False,
                "error": "Doctor not found."
            }

        requested_date = date.fromisoformat(appointment_date)

        # Monday = 0
        # Friday = 4
        if requested_date.weekday() not in WORKING_DAYS:
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
                Appointment.clinic_id == CLINIC_ID,
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
        doctor = db.query(Doctor).filter(Doctor.clinic_id == CLINIC_ID).first()

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

        if requested_date.weekday() not in WORKING_DAYS:
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
            Appointment.clinic_id == CLINIC_ID,
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
            Patient.phone == phone,
            Patient.clinic_id == CLINIC_ID
        ).first()

        if not patient:

            patient = Patient(
                clinic_id=CLINIC_ID,
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
            clinic_id=CLINIC_ID,
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
            "status": "confirmed",
            "google_calendar_link": build_google_calendar_link(
                appointment_date, appointment_time
            ),
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
            Patient.phone == phone,
            Patient.clinic_id == CLINIC_ID
        ).first()

        if not patient:
            return {
                "success": False,
                "error": "No patient was found with this phone number."
            }

        # Find the appointment
        appointment = db.query(Appointment).filter(
            Appointment.patient_id == patient.id,
            Appointment.clinic_id == CLINIC_ID,
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
            Patient.phone == phone,
            Patient.clinic_id == CLINIC_ID
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
            Appointment.clinic_id == CLINIC_ID,
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

        if new_date.weekday() not in WORKING_DAYS:
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
            Appointment.clinic_id == CLINIC_ID,
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
            "status": appointment.status,
            "google_calendar_link": build_google_calendar_link(
                new_appointment_date, new_appointment_time
            ),
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
            Patient.phone == phone,
            Patient.clinic_id == CLINIC_ID
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
                Appointment.clinic_id == CLINIC_ID,
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
        f"Check which appointment times are available "
        f"for {DOCTOR_NAME} on a specific date."
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
# Groq uses the OpenAI-compatible tool schema.
def _to_groq_tool(tool_definition):
    return {
        "type": "function",
        "function": {
            "name": tool_definition["name"],
            "description": tool_definition["description"],
            "parameters": tool_definition["parameters"],
        },
    }


TOOLS = [
    _to_groq_tool(check_availability_tool),
    _to_groq_tool(book_appointment_tool),
    _to_groq_tool(cancel_appointment_tool),
    _to_groq_tool(reschedule_appointment_tool),
    _to_groq_tool(get_patient_appointments_tool),
]

# ============================================================
# SYSTEM INSTRUCTIONS
# ============================================================
SYSTEM_INSTRUCTION = f"""
You are an AI appointment receptionist for {CLINIC_NAME}.

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
- You fully support both English and Arabic. Understand patient
  messages in either language and always reply in the language
  the patient uses. Arabic patients commonly say things like
  "بدي موعد بكرة" (I want an appointment tomorrow), "إلغاء"
  (cancel), "تأجيل" (reschedule), "شو الأوقات المتاحة؟"
  (what times are available), and "شكرًا" (thanks). Treat
  these as normal booking, cancellation, rescheduling, and
  availability requests. Never ask the patient to switch
  languages.
- When a booking or reschedule tool result contains a
  "google_calendar_link", your reply MUST include that
  full link on its own line so the patient can add the
  appointment to Google Calendar. Introduce it with
  a short sentence like "Add it to your Google Calendar:".
- Do not provide medical advice.
- Only handle appointment-related requests.
- When a patient asks about their existing or upcoming appointments,
  use get_patient_appointments.
- You must have the patient's phone number before looking up
  their appointments.
- Never invent or assume an appointment.

DOCTOR:

Name:
{DOCTOR_NAME}

Specialty:
{DOCTOR_SPECIALTY}

WORKING DAYS:

{"Monday-Friday" if WORKING_DAYS == [0,1,2,3,4] else ", ".join(str(d) for d in WORKING_DAYS)}

WORKING HOURS:

{START_TIME.strftime("%H:%M")}-{END_TIME.strftime("%H:%M")}

APPOINTMENT DURATION:

{APPOINTMENT_DURATION} minutes.
"""
# ============================================================
# AGENT
# ============================================================



def run_agent(
    session_id: str,
    message: str,
    sender_phone: str = None
):
    """
    Run the appointment agent with Groq function calling.
    Conversation history is stored in the Message database table.
    """
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

Use these exact dates for relative date expressions. Do not ask for an
exact date when the patient clearly says today, tomorrow, or the day
after tomorrow.
"""

        phone_context = ""
        if sender_phone:
            phone_context = f"""
WHATSAPP SENDER PHONE: {sender_phone}
For viewing, booking, cancelling, or rescheduling, use this phone number.
Do not ask the patient to repeat it, and do not use another phone number
for database operations.
"""

        # Load previous messages before saving the current user message.
        previous_messages = (
            db.query(Message)
            .filter(Message.session_id == session_id)
            .order_by(Message.id.asc())
            .all()
        )

        messages = [{"role": "system", "content": SYSTEM_INSTRUCTION}]
        messages.append({
            "role": "system",
            "content": date_context + phone_context
        })

        # Only include valid conversational roles and recent history.
        for item in previous_messages[-20:]:
            if item.role in ("user", "assistant") and item.content:
                messages.append({
                    "role": item.role,
                    "content": item.content
                })

        messages.append({"role": "user", "content": message})

        # Store the current patient message.
        db.add(Message(
            clinic_id=CLINIC_ID,
            session_id=session_id,
            role="user",
            content=message
        ))
        db.commit()

        # Run Groq and process tool calls until a final text response arrives.
        max_tool_rounds = 8
        assistant_message = ""

        for _ in range(max_tool_rounds):
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.2,
                max_tokens=1200,
            )

            assistant_turn = response.choices[0].message
            tool_calls = assistant_turn.tool_calls

            if not tool_calls:
                assistant_message = assistant_turn.content or (
                    "I'm sorry, I couldn't generate a response. Please try again."
                )
                break

            # Preserve the assistant tool-call message in the next request.
            messages.append({
                "role": "assistant",
                "content": assistant_turn.content,
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.function.name,
                            "arguments": call.function.arguments,
                        },
                    }
                    for call in tool_calls
                ],
            })

            for call in tool_calls:
                tool_name = call.function.name
                try:
                    args = json.loads(call.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}

                print(f"AI TOOL CALL: {tool_name}")
                print(f"ARGUMENTS: {args}")

                if tool_name == "check_availability":
                    result = check_availability(args["appointment_date"])

                elif tool_name == "book_appointment":
                    phone = sender_phone or args.get("phone")
                    if not phone:
                        result = {
                            "success": False,
                            "error": "A patient phone number is required."
                        }
                    else:
                        result = book_appointment(
                            args["patient_name"],
                            phone,
                            args["appointment_date"],
                            args["appointment_time"],
                        )

                elif tool_name == "cancel_appointment":
                    phone = sender_phone or args.get("phone")
                    if not phone:
                        result = {
                            "success": False,
                            "error": "A patient phone number is required."
                        }
                    else:
                        result = cancel_appointment(
                            phone,
                            args["appointment_date"],
                            args["appointment_time"],
                        )

                elif tool_name == "reschedule_appointment":
                    phone = sender_phone or args.get("phone")
                    if not phone:
                        result = {
                            "success": False,
                            "error": "A patient phone number is required."
                        }
                    else:
                        # Always verify the new slot before rescheduling.
                        availability_result = check_availability(
                            args["new_appointment_date"]
                        )
                        requested_new_time = args["new_appointment_time"]

                        if (
                            availability_result.get("success")
                            and requested_new_time in availability_result.get("slots", [])
                        ):
                            result = reschedule_appointment(
                                phone,
                                args["old_appointment_date"],
                                args["old_appointment_time"],
                                args["new_appointment_date"],
                                requested_new_time,
                            )
                        else:
                            result = {
                                "success": False,
                                "error": (
                                    "The requested new appointment time is not available."
                                ),
                                "available_slots": availability_result.get("slots", []),
                            }

                elif tool_name == "get_patient_appointments":
                    phone = sender_phone or args.get("phone")
                    if not phone:
                        result = {
                            "success": False,
                            "error": "A patient phone number is required."
                        }
                    else:
                        result = get_patient_appointments(phone)

                else:
                    result = {
                        "success": False,
                        "error": f"Unknown tool: {tool_name}"
                    }

                print(f"TOOL RESULT: {result}")

                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                })

        else:
            assistant_message = (
                "I'm sorry, I couldn't complete that request. Please try again."
            )

        # Store the assistant reply for future conversation memory.
        db.add(Message(
            clinic_id=CLINIC_ID,
            session_id=session_id,
            role="assistant",
            content=assistant_message
        ))
        db.commit()

        return assistant_message

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()
