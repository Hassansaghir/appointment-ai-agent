# AGENTS.md

## What this is
FastAPI backend for an AI appointment-booking agent (dental clinic). Two WhatsApp entry points:
- Meta Cloud API webhook: `backend/whatsapp_routes.py` (`/whatsapp/webhook`)
- Local Baileys bridge: `backend/whatsapp-bridge/index.js` (Node, `npm start`) → POSTs to `/bridge/message`

The agent brain is `backend/ai_agent.py::run_agent(session_id, message, sender_phone=None)`, using **Groq** (`GROQ_API_KEY`, model `openai/gpt-oss-120b`) with OpenAI-style tool calls.
`README.md` is the canonical setup/deploy doc — keep it in sync with code changes.

## Run commands
- Backend: `cd backend && uvicorn main:app --reload` (imports are flat, e.g. `from database import ...`, so cwd must be `backend/`)
- Bridge: `cd backend/whatsapp-bridge && npm start` (scan QR once; session stored in `auth_info/`)
- Init tables: `cd backend && python init_db.py`
- Deps: pinned in root `requirements.txt`; use the existing `venv/` at repo root

## Hard-earned facts
- `.env` lives at the **repo root**, not in `backend/`. `database.py` and `config.py` both call `load_dotenv()`.
- `DATABASE_URL` is SQL Server via pyodbc (`mssql+pyodbc://...TrustServerCertificate=yes`); missing it raises at import. `backend/appointments.db` is a stale SQLite leftover — not used.
- Tables auto-create on `main.py` import (`Base.metadata.create_all`).
- All clinic/schedule settings come from env via `backend/config.py` (`CLINIC_NAME`, `DOCTOR_NAME`, `WORKING_DAYS`, `START_TIME`, `END_TIME`, `APPOINTMENT_DURATION`, `CLINIC_TIMEZONE`, `CLINIC_ID`). `WORKING_DAYS` uses `date.weekday()` numbering (0=Mon); default `0,1,2,3,4`.
- Booking/reschedule reject times not aligned to `APPOINTMENT_DURATION` slots and non-working days; slot math is duplicated in `ai_agent.py` and `main.py` — change both.
- Conversation history is stored in the `messages` table and capped to the last 20 entries when sent to the model (`ai_agent.py` ~line 972).
- `main.py` still imports `from google.genai import errors` for `/chat` error mapping, but the agent uses Groq. `backend/ai_agent - Copy.py` is a stale Gemini-based backup — do not "fix" it.
- Daily WhatsApp summary is off by default (`DAILY_SUMMARY_ENABLED=false`); sends `DAILY_SUMMARY_HOUR`:`DAILY_SUMMARY_MINUTE` in `CLINIC_TIMEZONE` (default `Asia/Beirut`); logic in `backend/services/`.
- CORS allows only `localhost:5173` / `127.0.0.1:5173` (Vite frontend, not in this repo).

## Gotchas
- WhatsApp webhook verify token: `WHATSAPP_VERIFY_TOKEN` env var; sender phone becomes session id `whatsapp_<phone>`.
- Baileys bridge: if logged out, delete `backend/whatsapp-bridge/auth_info/` and re-scan the QR. Groups/status broadcasts are filtered in `index.js`.
- No tests, no linter, no CI. Verify changes by hitting `/`, `/setup`, `/availability` on the running FastAPI app or exercising `run_agent()` directly.
