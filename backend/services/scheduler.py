
import logging
import os
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler

from services.daily_summary import send_tomorrow_summary
from services.reminders import send_tomorrow_reminders

logger = logging.getLogger(__name__)

_scheduler = None


def _flag(name: str) -> bool:
    return os.getenv(name, "false").strip().lower() == "true"


def start_daily_summary_scheduler():
    """Start the shared background scheduler with all enabled jobs."""
    global _scheduler

    summary_enabled = _flag("DAILY_SUMMARY_ENABLED")
    reminders_enabled = _flag("REMINDERS_ENABLED")

    if not summary_enabled and not reminders_enabled:
        logger.info("No scheduled WhatsApp jobs enabled.")
        return

    if _scheduler is not None and _scheduler.running:
        return

    timezone_name = os.getenv("CLINIC_TIMEZONE", "Asia/Beirut")

    _scheduler = BackgroundScheduler(timezone=ZoneInfo(timezone_name))

    def _add_daily(fn, hour_env, minute_env, default_hour, job_id, label):
        hour = int(os.getenv(hour_env, str(default_hour)))
        minute = int(os.getenv(minute_env, "0"))

        if not 0 <= hour <= 23 or not 0 <= minute <= 59:
            raise ValueError(f"Invalid schedule time for {label}.")

        _scheduler.add_job(
            fn,
            trigger="cron",
            hour=hour,
            minute=minute,
            id=job_id,
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

        logger.info("%s scheduled for %02d:%02d (%s).", label, hour, minute, timezone_name)

    if summary_enabled:
        _add_daily(
            send_tomorrow_summary,
            "DAILY_SUMMARY_HOUR",
            "DAILY_SUMMARY_MINUTE",
            20,
            "daily_whatsapp_appointment_summary",
            "Daily WhatsApp summary",
        )

    if reminders_enabled:
        _add_daily(
            send_tomorrow_reminders,
            "REMINDER_HOUR",
            "REMINDER_MINUTE",
            18,
            "daily_patient_reminders",
            "Patient reminders",
        )

    _scheduler.start()


def stop_daily_summary_scheduler():
    global _scheduler

    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None
