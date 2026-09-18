"""Notification facade - the one write path every business module uses.

    from app.notify.engine import notify_user, notify_department, dispatch

The engine (1) persists the in-app record that the UI reads, (2) resolves recipients and
their channel preferences, (3) renders per-channel templates, and (4) hands the rest to
the durable outbox. Callers never deal with SMTP/Twilio/Meta details.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any, Dict, List, Optional

from app.config.settings import settings
from app.notify import templates
from app.notify.base import CHANNEL_INAPP, iso, now_utc, severity_rank
from app.notify.queue import enqueue
from app.notify.routing import (
    fingerprint,
    kind_severity,
    load_preferences,
    plan_channels,
    resolve_recipients,
)

PRIORITY_TO_SEVERITY = {
    "urgent": "CRITICAL",
    "high": "HIGH",
    "medium": "MEDIUM",
    "low": "LOW",
    "critical": "CRITICAL",
    "important": "HIGH",
    "info": "LOW",
}

# Legacy `notif_type` strings used across the existing routers -> canonical kinds
TYPE_TO_KIND = {
    "ASSIGNMENT": "task_assigned",
    "TASK_ASSIGNED": "task_assigned",
    "DEADLINE RISK": "deadline_risk",
    "DEADLINE_RISK": "deadline_risk",
    "TASK OVERDUE": "task_overdue",
    "TASK_OVERDUE": "task_overdue",
    "OVERDUE": "task_overdue",
    "APPROVAL": "approval_request",
    "APPROVAL_REQUEST": "approval_request",
    "APPROVED": "approval_approved",
    "REJECTED": "approval_rejected",
    "REVISION REQUIRED": "revision_required",
    "EVENT_INVITE": "event_reminder",
    "SYSTEM_ALERT": "system_alert",
    "AI": "ai_insight",
    "AI_ALERT": "ai_insight",
    "ESCALATION": "escalation",
    "DIGEST": "daily_digest",
    "CALENDAR": "event_reminder",
    "GOAL": "goal_checkin",
}

SEVERITY_ICON = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🔵", "LOW": "⚪"}
SEVERITY_LABEL = {"CRITICAL": "Urgent", "HIGH": "High", "MEDIUM": "Medium", "LOW": "Low"}


def normalize_severity(value: Optional[str], kind: str) -> str:
    if not value:
        return kind_severity(kind)
    mapped = PRIORITY_TO_SEVERITY.get(str(value).strip().lower())
    return mapped or kind_severity(kind, value)


def dispatch(
    db: Any,
    *,
    target: str,
    kind: str,
    title: str,
    message: str,
    severity: Optional[str] = None,
    route: str = "/tasks",
    facts: Optional[Dict[str, Any]] = None,
    meta: Optional[Dict[str, Any]] = None,
    actor: Optional[Dict[str, Any]] = None,
    force_channels: Optional[List[str]] = None,
    write_inapp: bool = True,
) -> Dict[str, Any]:
    """Fan one event out to the correct people over the correct channels."""
    sev = normalize_severity(severity or kind, kind)
    recipients = resolve_recipients(db, target, actor)
    summary = {
        "kind": kind,
        "severity": sev,
        "recipients": [r.get("id") for r in recipients],
        "inapp_written": False,
        "queued": {},
        "deduped": [],
        "skipped": [],
        "outbox_ids": [],
    }

    if not settings.NOTIFY_ENABLED:
        summary["skipped"].append("notifications_disabled")
        return summary

    if not recipients:
        summary["skipped"].append("no_recipients_resolved")
        return summary

    facts = dict(facts or {})
    ctx = {"title": title, "message": message, "facts": facts}
    rendered = templates.render(settings, kind=kind, severity=sev, ctx=ctx)
    fp_base = fingerprint(target, kind, title, message)

    # 1) in-app record (system of record; broadcast uses the 'department' pseudo-user)
    if write_inapp and settings.NOTIFY_INAPP_ENABLED and kind != "daily_digest":
        if not _inapp_exists(db, target, title, message):
            notif_id = f"notif_{uuid.uuid4().hex[:10]}"
            db.collection("notifications").document(notif_id).set(
                {
                    "id": notif_id,
                    "user_id": target,
                    "title": title,
                    "message": message,
                    "type": kind.upper().replace("_", " "),
                    "severity": sev,
                    "priority": SEVERITY_LABEL.get(sev, "Medium"),
                    "icon": meta.get("icon") if meta and meta.get("icon") else SEVERITY_ICON.get(sev, "🔔"),
                    "status": "New",
                    "target_route": route,
                    "time": "Just now",
                    "is_read": False,
                    "facts": facts,
                    "meta": meta or {},
                    "created_at": iso(),
                }
            )
            summary["inapp_written"] = True

    # 2) outbound channels (email / SMS / WhatsApp), per recipient preference
    for user in recipients:
        prefs = load_preferences(db, user.get("id") or "", user)
        plan, skipped = plan_channels(user, prefs, kind, sev)
        for item in plan:
            if item.channel == CHANNEL_INAPP:
                continue
            if force_channels and item.channel not in force_channels:
                continue
            outbox_id, state = enqueue(
                db,
                item,
                subject=rendered["subject"],
                text=rendered["text"],
                html=rendered["html"],
                whatsapp_text=rendered["whatsapp"] if item.channel == "whatsapp" else rendered["text"],
                fingerprint=fingerprint(user.get("id", "?"), kind, title, message),
                meta={"route": route, "title": title, **(meta or {})},
            )
            if state == "deduped":
                summary["deduped"].append(f"{user.get('id')}:{item.channel}")
            elif state in ("queued", "scheduled", "digest"):
                summary["queued"][item.channel] = summary["queued"].get(item.channel, 0) + 1
                if outbox_id:
                    summary["outbox_ids"].append(outbox_id)
        if skipped:
            summary["skipped"].extend([f"{user.get('id')}:{s}" for s in skipped])

    return summary


def _inapp_exists(db: Any, user_id: str, title: str, message: str) -> bool:
    """Suppress duplicate in-app alerts inside the dedupe window (prevents 3am spam)."""
    cutoff = (now_utc() - timedelta(minutes=max(0, settings.NOTIFY_DEDUPE_MINUTES))).isoformat(timespec="seconds")
    try:
        for snap in db.collection("notifications").where("user_id", "==", user_id).where("title", "==", title).stream():
            d = snap.to_dict()
            if (d.get("created_at") or "") >= cutoff and (d.get("message") or "")[:200] == (message or "")[:200]:
                return True
    except Exception:  # pragma: no cover
        return False
    return False


# ------------------------------------------------------------- convenience wrappers
def notify_user(db: Any, user_id: str, kind: str, title: str, message: str, **kw) -> Dict[str, Any]:
    return dispatch(db, target=user_id or "", kind=kind, title=title, message=message, **kw)


def notify_department(db: Any, kind: str, title: str, message: str, **kw) -> Dict[str, Any]:
    return dispatch(db, target="department", kind=kind, title=title, message=message, **kw)


def notify_role(db: Any, role: str, kind: str, title: str, message: str, **kw) -> Dict[str, Any]:
    return dispatch(db, target=f"role:{role}", kind=kind, title=title, message=message, **kw)


def trigger_notification(
    db: Any,
    user_id: str,
    notif_type: str,
    title: str,
    message: str,
    target_route: str = "/tasks",
    priority: str = "Medium",
    icon: str = "🔔",
) -> Dict[str, Any]:
    """Compatibility shim for the existing routers.

    Old signature: trigger_notification(db, user_id, "DEADLINE RISK", title, body,
    route, priority, icon). It now also fans out to e-mail/SMS/WhatsApp under the hood.
    """
    kind = TYPE_TO_KIND.get((notif_type or "").upper(), (notif_type or "system_alert").lower().replace(" ", "_"))
    return dispatch(
        db,
        target=user_id,
        kind=kind,
        title=title,
        message=message,
        severity=PRIORITY_TO_SEVERITY.get(str(priority).lower()),
        route=target_route,
        meta={"icon": icon, "legacy_type": notif_type},
    )


def send_test(db: Any, user: Dict[str, Any], channels: Optional[List[str]] = None) -> Dict[str, Any]:
    """Fire a test alert at the calling user only - used by Settings → Notifications."""
    summary = dispatch(
        db,
        target=user.get("id", ""),
        kind="system_alert",
        title="HieraSync test alert",
        message="This is a test notification. If you can read it, your routing, "
        "credentials and quiet-hours window are all working.",
        severity="CRITICAL",  # break through quiet hours on purpose
        route="/settings",
        facts={"Requested channels": ", ".join(channels) if channels else "all enabled", "Sent by": user.get("name", "you")},
    )
    from app.notify.queue import process_due

    summary["flush"] = process_due(db, limit=50)
    return summary
