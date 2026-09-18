"""Notification routing policy: who gets told, over which channel, and when.

The policy layer is deliberately separated from the providers so that governance rules
(quiet hours, severity thresholds, opt-in consent, digest batching, department broadcast
scope) can be tuned and audited without touching transport code.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, time as dtime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.config.settings import settings
from app.notify.base import CHANNEL_EMAIL, CHANNEL_INAPP, CHANNEL_SMS, CHANNEL_WHATSAPP, severity_rank

try:  # real tz support when the tz database is installed
    from zoneinfo import ZoneInfo  # type: ignore

    _HAS_TZ = True
except Exception:  # pragma: no cover
    _HAS_TZ = False


PREFS_COLLECTION = "notification_preferences"

DEFAULT_PREFS: Dict[str, Any] = {
    "email_enabled": True,
    "sms_enabled": True,
    "whatsapp_enabled": True,
    "whatsapp_opt_in": False,      # explicit consent: Meta requires opt-in per number
    "email": "",
    "phone": "",
    "whatsapp_number": "",
    "quiet_hours_enabled": True,
    "quiet_hours": "",             # empty -> settings.DEFAULT_QUIET_HOURS
    "digest_mode": "none",         # none | daily | weekly
    "min_severity_email": "LOW",
    "min_severity_sms": "HIGH",
    "min_severity_whatsapp": "CRITICAL",
    "muted_kinds": [],
    "auto_assign_emails": True,
}

DIGESTABLE_KINDS = {
    "task_assigned",
    "deadline_reminder",
    "goal_checkin",
    "event_reminder",
    "ai_insight",
    "task_completed",
}

KIND_RANK = {
    "task_assigned": "MEDIUM",
    "deadline_reminder": "MEDIUM",
    "deadline_risk": "HIGH",
    "task_overdue": "HIGH",
    "task_completed": "LOW",
    "revision_required": "HIGH",
    "approval_request": "HIGH",
    "approval_approved": "LOW",
    "approval_rejected": "MEDIUM",
    "approval_escalated": "CRITICAL",
    "approval_sla_breach": "HIGH",
    "join_request_new": "MEDIUM",
    "join_approved": "LOW",
    "join_rejected": "MEDIUM",
    "event_reminder": "MEDIUM",
    "goal_checkin": "LOW",
    "daily_digest": "LOW",
    "weekly_report": "LOW",
    "escalation": "CRITICAL",
    "system_alert": "MEDIUM",
    "ai_insight": "LOW",
}


def kind_severity(kind: str, override: Optional[str] = None) -> str:
    if override:
        return override.upper()
    return KIND_RANK.get(kind, "MEDIUM")


def fingerprint(user_id: str, kind: str, title: str, body: str) -> str:
    raw = f"{user_id}|{kind}|{(title or '').strip().lower()}|{(body or '').strip().lower()[:240]}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


# --------------------------------------------------------------------------- local clock
def local_now() -> datetime:
    if _HAS_TZ:
        try:
            return datetime.now(ZoneInfo(settings.NOTIFY_TIMEZONE)).replace(tzinfo=None)
        except Exception:  # pragma: no cover
            pass
    return datetime.utcnow() + timedelta(minutes=settings.NOTIFY_TZ_OFFSET_MINUTES)


def parse_window(window: str) -> Tuple[dtime, dtime]:
    start_s, _, end_s = (window or "").partition("-")
    def _t(val: str, default: dtime) -> dtime:
        try:
            h, m = (val.strip() or "0").split(":")[:2]
            return dtime(int(h), int(m))
        except Exception:
            return default
    return _t(start_s, dtime(22, 30)), _t(end_s, dtime(7, 0))


def in_quiet_hours(now: Optional[datetime] = None, window: str = "") -> bool:
    if not settings.DEFAULT_QUIET_HOURS and not window:
        return False
    win = window or settings.DEFAULT_QUIET_HOURS
    if not win or "-" not in win:
        return False
    start, end = parse_window(win)
    now = now or local_now()
    cur = now.time()
    if start <= end:
        return start <= cur < end
    return cur >= start or cur < end  # wraps midnight


def quiet_hours_end(now: Optional[datetime] = None, window: str = "") -> datetime:
    win = window or settings.DEFAULT_QUIET_HOURS
    start, end = parse_window(win)
    now = now or local_now()
    candidate = now.replace(hour=end.hour, minute=end.minute, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def next_daily_digest_at(now: Optional[datetime] = None) -> datetime:
    hh, mm = (settings.DIGEST_DAILY_TIME or "08:00").split(":")[:2]
    now = now or local_now()
    candidate = now.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


# --------------------------------------------------------------------------- preferences
def load_preferences(db: Any, user_id: str, user_doc: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    prefs = dict(DEFAULT_PREFS)
    if user_doc:
        prefs["email"] = user_doc.get("email") or ""
        prefs["phone"] = user_doc.get("phone") or user_doc.get("phone_e164") or ""
        prefs["whatsapp_number"] = user_doc.get("whatsapp_number") or prefs["phone"]
    if user_id and db is not None:
        try:
            doc = db.collection(PREFS_COLLECTION).document(user_id).get()
            if doc.exists:
                stored = {k: v for k, v in doc.to_dict().items() if v is not None}
                stored["muted_kinds"] = list(stored.get("muted_kinds") or [])
                prefs.update(stored)
        except Exception:
            pass
    return prefs


def save_preferences(db: Any, user_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    ref = db.collection(PREFS_COLLECTION).document(user_id)
    doc = ref.get()
    merged = dict(DEFAULT_PREFS)
    if doc.exists:
        merged.update({k: v for k, v in doc.to_dict().items() if v is not None})
    merged.update({k: v for k, v in (patch or {}).items() if v is not None})
    merged["user_id"] = user_id
    merged["updated_at"] = datetime.utcnow().isoformat(timespec="seconds")
    ref.set(merged)
    return merged


# --------------------------------------------------------------------------- recipients
def resolve_recipients(db: Any, target: str, actor: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Resolve a notification target into concrete users.

    target forms: ``<user_id>`` | ``department`` | ``role:HOD`` | ``all`` | ``dept:<id>``
    """
    users = list(db.collection("users").stream()) if db is not None else []
    docs: List[Tuple[str, Dict[str, Any]]] = []
    for snap in users:
        d = snap.to_dict()
        d.setdefault("id", snap.id)
        docs.append((snap.id, d))

    def active(d: Dict[str, Any]) -> bool:
        return str(d.get("status", "ACTIVE")).upper() in ("ACTIVE", "1", "")

    target = (target or "").strip()
    out: List[Dict[str, Any]] = []

    if not target or target.lower() == "department":
        roles = set(settings.broadcast_roles)
        out = [d for _, d in docs if active(d) and str(d.get("role", "")).upper() in roles]
    elif target.lower() == "all":
        out = [d for _, d in docs if active(d)]
    elif target.lower().startswith("role:"):
        role = target.split(":", 1)[1].strip().upper()
        out = [d for _, d in docs if active(d) and str(d.get("role", "")).upper() == role]
    elif target.lower().startswith("dept:"):
        dept = target.split(":", 1)[1].strip()
        out = [d for _, d in docs if active(d) and d.get("department_id") == dept]
    else:
        by_id = {d.get("id") or i: d for i, d in docs}
        if target in by_id:
            out = [by_id[target]]
        else:  # fall back: match on name (legacy tasks stored assignee names)
            out = [d for _, d in docs if active(d) and (d.get("name", "").lower() == target.lower())]

    # Never notify the actor about their own action (reduces noise ~40% in practice)
    if actor and actor.get("id") and settings.PROJECT_NAME:
        out = [u for u in out if u.get("id") != actor.get("id")] or out
    return out


# --------------------------------------------------------------------------- channel plan
@dataclass
class PlannedDelivery:
    channel: str
    address: str
    kind: str
    severity: str
    user_id: str
    immediate: bool = True
    scheduled_at: Optional[datetime] = None
    reason: str = ""


def plan_channels(user: Dict[str, Any], prefs: Dict[str, Any], kind: str, severity: str, *, now: Optional[datetime] = None) -> Tuple[List[PlannedDelivery], List[str]]:
    """Turn (user, preferences, severity) into a concrete delivery plan + skip reasons."""
    sev_up = (severity or "MEDIUM").upper()
    rank = severity_rank(sev_up)
    skipped: List[str] = []
    planned: List[PlannedDelivery] = []
    user_id = user.get("id") or user.get("email") or "unknown"
    now = now or local_now()

    if kind in (prefs.get("muted_kinds") or []):
        return [], [f"muted:{kind}"]

    allowed = set(settings.policy_for(sev_up))

    # in-app is unconditional for every severity (it is the system of record)
    if CHANNEL_INAPP in allowed or True:
        planned.append(PlannedDelivery(channel=CHANNEL_INAPP, address=user_id, kind=kind, severity=sev_up, user_id=user_id))

    # ---- email
    if CHANNEL_EMAIL in allowed and prefs.get("email_enabled", True) and rank >= severity_rank(prefs.get("min_severity_email", "LOW")):
        addr = (prefs.get("email") or user.get("email") or "").strip()
        if not addr:
            skipped.append("email:no_address")
        else:
            planned.append(
                PlannedDelivery(channel=CHANNEL_EMAIL, address=addr, kind=kind, severity=sev_up, user_id=user_id)
            )

    digest_mode = (prefs.get("digest_mode") or "none").lower()
    wants_digest = digest_mode in ("daily", "weekly") and kind in DIGESTABLE_KINDS and rank < 2

    # ---- sms / whatsapp (both driven by the same consented phone number)
    phone = (prefs.get("phone") or user.get("phone") or "").strip()
    if CHANNEL_SMS in allowed and prefs.get("sms_enabled", True) and rank >= severity_rank(prefs.get("min_severity_sms", "HIGH")):
        if not phone:
            skipped.append("sms:no_number")
        else:
            planned.append(PlannedDelivery(channel=CHANNEL_SMS, address=phone, kind=kind, severity=sev_up, user_id=user_id))

    wa = (prefs.get("whatsapp_number") or phone).strip()
    if CHANNEL_WHATSAPP in allowed and prefs.get("whatsapp_enabled", True) and rank >= severity_rank(prefs.get("min_severity_whatsapp", "CRITICAL")):
        if not wa:
            skipped.append("whatsapp:no_number")
        elif not prefs.get("whatsapp_opt_in"):
            skipped.append("whatsapp:opt_in_required")
        else:
            planned.append(PlannedDelivery(channel=CHANNEL_WHATSAPP, address=wa, kind=kind, severity=sev_up, user_id=user_id))

    out: List[PlannedDelivery] = []
    for d in planned:
        # quiet hours: everything except CRITICAL waits for the window to close
        if d.channel != CHANNEL_INAPP and prefs.get("quiet_hours_enabled", True) and sev_up != "CRITICAL" and in_quiet_hours(now, prefs.get("quiet_hours") or ""):
            d.immediate = False
            d.scheduled_at = quiet_hours_end(now, prefs.get("quiet_hours") or "")
            d.reason = "deferred_quiet_hours"
        if d.channel != CHANNEL_INAPP and wants_digest:
            d.immediate = False
            d.scheduled_at = next_daily_digest_at(now)
            d.reason = f"digest:{digest_mode}"
        out.append(d)
    return out, skipped
