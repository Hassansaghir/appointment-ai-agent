# AI Appointment Agent

FastAPI backend + AI agent for booking, rescheduling, and cancelling appointments over WhatsApp. Uses Groq for the AI brain and stores conversations/appointments in a SQL database.

## Architecture

- `backend/main.py` — FastAPI app, REST endpoints, WhatsApp webhook wiring, daily-summary scheduler lifecycle
- `backend/ai_agent.py` — `run_agent()` conversation loop with Groq tool calling
- `backend/config.py` — all clinic/schedule settings loaded from env vars
- `backend/models.py` — SQLAlchemy models (`Clinic`, `Doctor`, `Patient`, `Appointment`, `Conversation`, `Message`)
- `backend/whatsapp_routes.py` — Meta WhatsApp Cloud API webhook (`/whatsapp/webhook`)
- `backend/services/` — WhatsApp sender, daily summary, patient reminders, scheduler, appointment/patient helpers
- `backend/whatsapp-bridge/` — optional local Baileys bridge (dev/testing) that POSTs to `/bridge/message`

## Setup

1. Create a venv and install deps:
   ```
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Copy `.env.example` to `.env` and fill in your keys (`GROQ_API_KEY`, `DATABASE_URL`, WhatsApp vars, clinic branding).
3. Initialize the database:
   ```
   cd backend
   python init_db.py
   ```
4. Run the API:
   ```
   uvicorn main:app --reload
   ```
5. (Optional) Run the local WhatsApp bridge:
   ```
   cd backend/whatsapp-bridge
   npm install
   npm start
   ```

## Configure a new clinic

Set the env vars in `.env`:

```
CLINIC_NAME=Sunrise Dental
DOCTOR_NAME=Dr. Sara
DOCTOR_SPECIALTY=Dentist
CLINIC_TIMEZONE=Asia/Beirut
CLINIC_ID=1
WORKING_DAYS=0,1,2,3,4
START_TIME=09:00
END_TIME=17:00
APPOINTMENT_DURATION=30
```

Restart the server, then call `POST /setup` once to create the doctor row for that clinic.

## Deployment (per-client)

1. Provision a server (Render/Railway/VPS) with Python 3.11+ and Node 18+.
2. Use a managed Postgres/MySQL/SQL Server instead of local SQLEXPRESS; update `DATABASE_URL`.
3. Run `python init_db.py` then `uvicorn main:app --host 0.0.0.0 --port 8000`.
4. Point the client's WhatsApp Business Cloud API webhook to `https://your-domain/whatsapp/webhook` with the same `WHATSAPP_VERIFY_TOKEN`.
5. Set `DAILY_SUMMARY_ENABLED=true` and `WHATSAPP_DOCTOR_PHONE` if you want the doctor to receive tomorrow's schedule each evening. Set `REMINDERS_ENABLED=true` to text patients their upcoming appointment the evening before (`REMINDER_HOUR`/`REMINDER_MINUTE`).
6. Use `GET /health` for uptime checks (verifies DB connectivity).

## Selling / multi-clinic notes

- One deployment per clinic is simplest: each client gets its own server, `.env`, database, and WhatsApp number.
- The schema already has `clinic_id` on all tables, so a shared database/deployment is possible later by routing WhatsApp phone-number-id to `Clinic.whatsapp_phone_number_id`.
- Never commit `.env`. Rotate all API keys before sharing this repo.
