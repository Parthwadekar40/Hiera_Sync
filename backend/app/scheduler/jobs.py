"""Background jobs for the department workflow.

The README promises reminders; until now `daily_reminder` only wrote a log line.
These jobs look at the activities on the calendar and queue real notifications
for the responsible faculty, so nothing depends on somebody remembering.
"""

import logging
import uuid
from datetime import date, datetime, timedelta
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()

REMINDER_WINDOW_DAYS = 2


def _resolve_user_id(db, name: Optional[str]) -> str:
    """Notifications are read per `user_id`; fall back to the department channel."""
    if not name:
        return "department"
    try:
        match = list(db.collection("users").where("name", "==", name).limit(1).stream())
        if match:
            return match[0].to_dict().get("id") or match[0].id
    except Exception as exc:
        logger.debug(f"Faculty lookup failed for '{name}': {exc}")
    return "department"


def _push(db, user_id: str, title: str, message: str, priority: str = "Medium") -> None:
    notification_id = f"notif_{uuid.uuid4().hex[:8]}"
    db.collection("notifications").document(notification_id).set(
        {
            "id": notification_id,
            "user_id": user_id,
            "title": title,
            "message": message,
            "type": "Calendar",
            "priority": priority,
            "target_route": "/calendar",
            "icon": "⏰",
            "status": "New",
            "time": "Just now",
            "is_read": False,
            "created_at": datetime.utcnow().isoformat(),
        }
    )


def send_event_reminders() -> int:
    """Notify owners of activities that start within the reminder window."""
    import app.database.session as session
    from app.utils.dates import to_iso_date

    db = session.db
    if db is None:
        logger.info("Firestore unavailable — skipping calendar reminders.")
        return 0

    today = date.today()
    horizon = today + timedelta(days=REMINDER_WINDOW_DAYS)
    sent = 0

    for doc in db.collection("events").stream():
        event = doc.to_dict()
        when = to_iso_date(event.get("date"))
        if not (today.isoformat() <= when <= horizon.isoformat()):
            continue
        if (event.get("status") or "") == "Completed":
            continue
        if event.get("reminded_at"):
            continue

        title = event.get("title", "Untitled activity")
        detail = f"{when}"
        if event.get("start_time"):
            detail += f" at {event['start_time']}"
        if event.get("location"):
            detail += f" · {event['location']}"

        _push(
            db,
            _resolve_user_id(db, event.get("person")),
            f"Starting soon: {title}",
            f"{detail}. Please confirm arrangements with the HOD desk.",
            event.get("priority") or "Medium",
        )
        doc.reference.update({"reminded_at": datetime.utcnow().isoformat()})
        sent += 1

    if sent:
        logger.info(f"Queued {sent} calendar reminder(s).")
    return sent


def flag_overdue_events() -> int:
    """Escalate activities whose date has passed without being completed."""
    import app.database.session as session
    from app.utils.dates import to_iso_date

    db = session.db
    if db is None:
        return 0

    today = date.today().isoformat()
    flagged = 0

    for doc in db.collection("events").stream():
        event = doc.to_dict()
        when = to_iso_date(event.get("date"))
        if when >= today or (event.get("status") or "") == "Completed":
            continue
        if event.get("overdue_notified_at"):
            continue

        _push(
            db,
            _resolve_user_id(db, event.get("person")),
            f"Overdue activity: {event.get('title', 'Untitled')}",
            f"Planned for {when} and still marked {event.get('status') or 'Planned'}. "
            "Update the status or reschedule it.",
            "High",
        )
        doc.reference.update({"overdue_notified_at": datetime.utcnow().isoformat()})
        flagged += 1

    if flagged:
        logger.info(f"Escalated {flagged} overdue calendar activity(ies).")
    return flagged


def daily_reminder() -> None:
    logger.info("Running department reminder sweep...")
    try:
        send_event_reminders()
        flag_overdue_events()
    except Exception as exc:  # never let a job kill the scheduler
        logger.error(f"Reminder sweep failed: {exc}")


def start_scheduler():
    scheduler.add_job(daily_reminder, "cron", hour=8, minute=0, id="daily_reminder",
                      replace_existing=True)
    # Catch activities added during the day without waiting for tomorrow 08:00.
    scheduler.add_job(daily_reminder, "interval", hours=6, id="reminder_sweep",
                      replace_existing=True)
    scheduler.start()
    logger.info("Scheduler started (daily 08:00 + 6-hourly sweep).")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped.")
