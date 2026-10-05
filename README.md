# 🦷 AI Appointment Agent

An AI receptionist for a dental clinic that books, reschedules, and cancels appointments over WhatsApp — in English **and** Arabic, 24/7.

Built with FastAPI, Groq (`openai/gpt-oss-120b`) tool calling, SQLAlchemy, and the WhatsApp Cloud API.

## ✨ Features

- 💬 **Conversational booking** — patients just say *"Hi, I want an appointment tomorrow"* and the agent checks availability and books ("بدي موعد بكرة" works too)
- 🔍 **Checks availability** against real doctor schedules and existing bookings
- ✏️ **Book / cancel / reschedule** via natural language
- ❓ **Answers FAQs** about the clinic
- 🧠 **Remembers conversations** per patient (last 20 messages used as context)
- ⏰ **Patient reminders** — WhatsApp reminder sent the evening before each appointment
- 📋 **Doctor's daily schedule** — summary WhatsApp message to the doctor every evening
- 🌐 **English + Arabic** — patient writes in either language, agent replies in kind
- 🔁 **Two WhatsApp entry points** — Meta Cloud API webhook, or a local Baileys bridge for dev/testing
- 🏢 **Multi-clinic ready** — every table is keyed by `clinic_id`

## 🏗 Architecture

```
WhatsApp Cloud API ──► backend/whatsapp_routes.py ─┐
                                                    ▼
Baileys bridge (index.js) ──► POST /bridge/message │
                                                    ▼
                                   backend/ai_agent.py  ──►  Groq (tool calling)
                                                    │
                                                    ▼
                              SQL Server / SQLAlchemy models
                                                    ▲
        APScheduler ──► daily doctor summary + patient reminders
```

- `backend/main.py` — FastAPI app, REST endpoints, scheduler lifecycle, `/health`
- `backend/ai_agent.py` — `run_agent()` conversation loop with Groq tool calling
- `backend/config.py` — all clinic/schedule settings from env vars
- `backend/models.py` — SQLAlchemy models (`Clinic`, `Doctor`, `Patient`, `Appointment`, `Conversation`, `Message`)
- `backend/whatsapp_routes.py` — Meta WhatsApp Cloud API webhook (`/whatsapp/webhook`)
- `backend/services/` — WhatsApp sender, daily summary, patient reminders, scheduler, helpers
- `backend/whatsapp-bridge/` — optional local Baileys bridge (dev/testing) → `POST /bridge/message`

## 🚀 Quick start

1. **Create a venv and install deps:**
   ```bash
   python -m venv venv
   venv\Scripts\activate        # Windows
   pip install -r requirements.txt
   ```

2. **Configure:**
   ```bash
   copy .env.example .env
   ```
   Fill in `GROQ_API_KEY`, `DATABASE_URL`, and the WhatsApp variables.

3. **Initialize the database:**
   ```bash
   cd backend
   python init_db.py
   ```

4. **Run the API:**
   ```bash
   uvicorn main:app --reload
   ```

5. **(Optional) Local WhatsApp bridge for testing:**
   ```bash
   cd backend/whatsapp-bridge
   npm install
   npm start        # scan the QR once
   ```

Then test it: call `POST /setup` once, and chat via `POST /chat`:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d "{\"session_id\": \"test1\", \"message\": \"Hi, I want an appointment tomorrow\"}"
```

## ⚙️ Configuration

All clinic settings live in `.env` (see `.env.example`):

```env
CLINIC_NAME=Sunrise Dental
DOCTOR_NAME=Dr. Sara
DOCTOR_SPECIALTY=Dentist
CLINIC_TIMEZONE=Asia/Beirut
CLINIC_ID=1
WORKING_DAYS=0,1,2,3,4        # 0 = Monday
START_TIME=09:00
END_TIME=17:00
APPOINTMENT_DURATION=30       # minutes
```

Scheduled jobs (both off by default):

| Env vars | Effect |
|---|---|
| `DAILY_SUMMARY_ENABLED`, `DAILY_SUMMARY_HOUR`, `DAILY_SUMMARY_MINUTE` | Doctor gets tomorrow's schedule each evening |
| `REMINDERS_ENABLED`, `REMINDER_HOUR`, `REMINDER_MINUTE` | Patients get a WhatsApp reminder the evening before |

After changing clinic config, restart the server and call `POST /setup` once to (re)create the doctor row.

## 🌐 Deployment

1. Server with Python 3.11+ and Node 18+ (Render/Railway/VPS).
2. Managed database (Postgres/MySQL/SQL Server) instead of local SQLEXPRESS → update `DATABASE_URL`.
3. `python init_db.py`, then `uvicorn main:app --host 0.0.0.0 --port 8000`.
4. Point the WhatsApp Business webhook to `https://your-domain/whatsapp/webhook` with the same `WHATSAPP_VERIFY_TOKEN`.
5. Use `GET /health` for uptime monitoring.

**Selling / multi-clinic:** one deployment per clinic is simplest (own server, `.env`, DB, WhatsApp number). All tables already carry `clinic_id`, so a shared deployment is possible later by routing on `Clinic.whatsapp_phone_number_id`.

## 🔒 Security notes

- Never commit `.env` — it's gitignored. Rotate all API keys before sharing a fork.
- `auth_info/` (WhatsApp session) and `node_modules/` are gitignored.

## 📄 License

Private / proprietary — add a license before open-sourcing.
