"""Durable outbox: dedupe, scheduling, retries with exponential backoff, dead-letter.

Why an outbox instead of sending inline?
* A business write must never fail because an SMTP relay hiccuped (atomicity + fail-soft).
* Retries survive process restarts - important because the campus runs the API on a
  free-tier instance that can sleep between classes.
* Every alert leaves an auditable artifact (delivery log) which feeds the analytics
  module ("did the reminder actually go out before the deadline?").
"""

from __future__ import annotations

import json
import os
import random
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.config.settings import settings
from app.notify.base import DeliveryResult, OutboundMessage, ProviderError, iso, now_utc
from app.notify.providers import DevOutboxProvider, build_providers
from app.notify.routing import PlannedDelivery

OUTBOX = "notification_outbox"
DELIVERIES = "notification_deliveries"
ACTIVE_STATUSES = ("pending", "retry")

_rate_window: Dict[str, List[float]] = {}
_providers_cache: Optional[Dict[str, List[Any]]] = None


def providers() -> Dict[str, List[Any]]:
    global _providers_cache
    if _providers_cache is None:
        _providers_cache = build_providers(settings)
    return _providers_cache


def reset_providers_cache() -> None:  # used by tests after env changes
    global _providers_cache
    _providers_cache = None


def _pick_provider(channel: str):
    chain = providers().get(channel) or []
    for provider in chain:
        if provider.enabled() and provider.is_configured():
            return provider
    return chain[-1] if chain else DevOutboxProvider(settings, channel)


# ------------------------------------------------------------------ rate limiting (safety)
def _rate_limited(channel: str) -> bool:
    limit = int(settings.NOTIFY_RATE_LIMIT_PER_MIN or 0)
    if limit <= 0:
        return False
    now = now_utc().timestamp()
    bucket = _rate_window.setdefault(channel, [])
    bucket[:] = [t for t in bucket if now - t < 60]
    if len(bucket) >= limit:
        return True
    bucket.append(now)
    return False


# ------------------------------------------------------------------ enqueue
def enqueue(
    db: Any,
    plan: PlannedDelivery,
    *,
    subject: str,
    text: str,
    html: str = "",
    whatsapp_text: str = "",
    fingerprint: str,
    meta: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str]:
    """Insert one outbox row. Returns (outbox_id, 'queued'|'deduped'|'skipped_reason')."""
    if not settings.NOTIFY_ENABLED:
        return "", "disabled"

    # The key is channel-scoped: sending e-mail must not swallow the SMS for the same event.
    key = f"{fingerprint}:{plan.channel}"
    window = timedelta(minutes=max(0, int(settings.NOTIFY_DEDUPE_MINUTES)))
    cutoff = (now_utc() - window).isoformat(timespec="seconds")
    try:
        for snap in db.collection(OUTBOX).where("fingerprint", "==", key).stream():
            d = snap.to_dict()
            if d.get("created_at", "") >= cutoff and d.get("status") not in ("dead",):
                return snap.id, "deduped"
    except Exception:  # pragma: no cover - never block business flow on a dedupe read
        pass

    outbox_id = f"obx_{uuid.uuid4().hex[:16]}"
    now = now_utc()
    scheduled_at = plan.scheduled_at or now
    doc = {
        "id": outbox_id,
        "user_id": plan.user_id,
        "channel": plan.channel,
        "address": plan.address,
        "kind": plan.kind,
        "severity": plan.severity,
        "subject": subject,
        "text": whatsapp_text if plan.channel in ("whatsapp", "sms") and whatsapp_text else text,
        "html": html,
        "fingerprint": key,
        "status": "pending" if plan.immediate else "scheduled",
        "attempts": 0,
        "max_attempts": settings.NOTIFY_MAX_ATTEMPTS,
        "created_at": iso(now),
        "updated_at": iso(now),
        "scheduled_at": iso(scheduled_at),
        "next_attempt_at": iso(scheduled_at),
        "defer_reason": plan.reason,
        "meta": meta or {},
    }
    db.collection(OUTBOX).document(outbox_id).set(doc)
    return outbox_id, "digest" if plan.reason.startswith("digest") else ("queued" if plan.immediate else "scheduled")


# ------------------------------------------------------------------ delivery log
def _log_delivery(db: Any, row: Dict[str, Any], result, outbox_status: str) -> None:
    try:
        db.collection(DELIVERIES).document(f"dlv_{uuid.uuid4().hex[:16]}").set(
            {
                "outbox_id": row.get("id"),
                "user_id": row.get("user_id"),
                "channel": row.get("channel"),
                "provider": result.provider,
                "address": row.get("address"),
                "kind": row.get("kind"),
                "severity": row.get("severity"),
                "status": outbox_status,
                "simulated": result.simulated,
                "ok": result.ok,
                "error": result.error,
                "external_id": result.external_id,
                "latency_ms": result.latency_ms,
                "attempts": row.get("attempts", 0),
                "created_at": iso(),
            }
        )
    except Exception:  # pragma: no cover
        pass


def _backoff(attempts: int) -> timedelta:
    base = max(5, int(settings.NOTIFY_BACKOFF_BASE_SECONDS))
    cap = max(base, int(settings.NOTIFY_BACKOFF_MAX_SECONDS))
    delay = min(cap, base * (2 ** max(0, attempts - 1)))
    return timedelta(seconds=delay + random.randint(0, max(0, settings.NOTIFY_JITTER_SECONDS)))


def _send(db: Any, row: Dict[str, Any], *, force_digest: bool = False) -> str:
    """Deliver one outbox row. Returns sent|retry|dead|scheduled|skipped."""
    channel = row.get("channel") or "email"
    if channel == "inapp":  # in-app notifications are written directly by the engine
        return "skipped"

    provider = _pick_provider(channel)
    msg = OutboundMessage(
        channel=channel,
        to=row.get("address") or "",
        subject=row.get("subject") or "",
        text=row.get("text") or "",
        html=row.get("html") or "",
        kind=row.get("kind") or "generic",
        severity=row.get("severity") or "MEDIUM",
        user_id=row.get("user_id") or "",
        meta={**(row.get("meta") or {}), "outbox_id": row.get("id")},
    )

    if _rate_limited(channel):
        ref = db.collection(OUTBOX).document(row["id"])
        ref.update({"status": "retry", "next_attempt_at": iso(now_utc() + timedelta(minutes=1)), "last_error": "rate_limited"})
        return "retry"

    attempts = int(row.get("attempts", 0)) + 1
    ref = db.collection(OUTBOX).document(row["id"])
    try:
        result = provider.send(msg)
    except ProviderError as exc:
        # Transport-level failure: retryable, so it must not be recorded as a rejection.
        result = DeliveryResult(
            ok=False,
            channel=channel,
            provider=getattr(provider, "name", channel),
            to=msg.to,
            error=f"transport error: {exc}",
            detail="retryable",
        )
        return _handle_failure(db, ref, row, result, attempts)

    if not result.ok:
        return _handle_failure(db, ref, row, result, attempts, retryable=False)

    ref.update(
        {
            "status": "sent",
            "attempts": attempts,
            "sent_at": iso(),
            "updated_at": iso(),
            "provider": result.provider,
            "external_id": result.external_id,
            "simulated": result.simulated,
            "last_error": None,
        }
    )
    _log_delivery(db, {**row, "attempts": attempts}, result, "simulated" if result.simulated else "sent")
    return "sent"


def _handle_failure(db: Any, ref, row: Dict[str, Any], result, attempts: int, *, retryable: bool = True) -> str:
    max_attempts = int(row.get("max_attempts") or settings.NOTIFY_MAX_ATTEMPTS)
    if not retryable or attempts >= max_attempts:
        ref.update({"status": "dead", "attempts": attempts, "last_error": result.error, "updated_at": iso()})
        _log_delivery(db, {**row, "attempts": attempts}, result, "dead")
        _alert_operators(db, row, result.error or "delivery failed", attempts)
        return "dead"
    delay = _backoff(attempts)
    ref.update(
        {
            "status": "retry",
            "attempts": attempts,
            "last_error": result.error,
            "next_attempt_at": iso(now_utc() + delay),
            "updated_at": iso(),
        }
    )
    _log_delivery(db, {**row, "attempts": attempts}, result, "retry")
    return "retry"


def _alert_operators(db: Any, row: Dict[str, Any], error: str, attempts: int) -> None:
    """Dead-letter must never be silent: page the admin inbox."""
    try:
        db.collection("notifications").document(f"notif_{uuid.uuid4().hex[:10]}").set(
            {
                "user_id": "department",
                "title": "Notification delivery failed",
                "message": (
                    f"Channel {row.get('channel')} to {row.get('address')} for user {row.get('user_id')} "
                    f"exhausted {attempts} attempts.\nLast error: {error[:280]}"
                ),
                "type": "SYSTEM_ALERT",
                "priority": "High",
                "icon": "🛑",
                "status": "New",
                "target_route": "/settings",
                "time": "Just now",
                "is_read": False,
                "created_at": iso(),
            }
        )
    except Exception:  # pragma: no cover
        pass


# ------------------------------------------------------------------ worker entrypoints
def process_due(db: Any, *, limit: int = 60, now: Optional[datetime] = None, channels: Optional[Tuple[str, ...]] = None) -> Dict[str, Any]:
    """Send everything that is due. Safe to call from the scheduler, CLI or tests."""
    now = now or now_utc()
    now_iso = iso(now)
    summary = {"scanned": 0, "sent": 0, "retry": 0, "dead": 0, "skipped": 0, "waiting": 0}
    try:
        rows = list(db.collection(OUTBOX).where("status", "in", ["pending", "retry", "scheduled"]).stream())
    except Exception:  # pragma: no cover
        return summary

    for snap in rows:
        row = snap.to_dict()
        row.setdefault("id", snap.id)
        if row.get("status") == "scheduled":
            if row.get("next_attempt_at", "") > now_iso:
                summary["waiting"] += 1
                continue
        elif row.get("next_attempt_at") and row.get("next_attempt_at", "") > now_iso:
            summary["waiting"] += 1
            continue
        if channels and row.get("channel") not in channels:
            continue
        summary["scanned"] += 1
        outcome = _send(db, row)
        summary[outcome if outcome in summary else "skipped"] += 1
        if summary["scanned"] >= limit:
            break
    return summary


def flush_all(db: Any, *, limit: int = 500) -> Dict[str, Any]:
    """Force-send everything pending (used by the 'Send now' admin button + demos)."""
    total = {"scanned": 0, "sent": 0, "retry": 0, "dead": 0, "skipped": 0, "waiting": 0}
    for _ in range(4):
        run = process_due(db, limit=limit)
        for k in total:
            total[k] += run.get(k, 0)
        if run["scanned"] == 0:
            break
    total["channels"] = provider_summary()
    return total


def pending_digest(db: Any, user_id: str, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    end_of_day = iso((now or now_utc()).replace(hour=23, minute=59, second=59))
    out: List[Dict[str, Any]] = []
    for snap in db.collection(OUTBOX).where("status", "in", ["scheduled", "pending"]).where("user_id", "==", user_id).stream():
        d = snap.to_dict()
        d.setdefault("id", snap.id)
        if d.get("defer_reason", "").startswith("digest") and d.get("created_at", "") <= end_of_day:
            out.append(d)
    return out


def mark_digest_consumed(db: Any, ids: List[str]) -> None:
    for _id in ids:
        try:
            db.collection(OUTBOX).document(_id).update({"status": "sent", "sent_at": iso(), "updated_at": iso(), "defer_reason": "digest_sent"})
        except Exception:  # pragma: no cover
            continue


def provider_summary() -> Dict[str, Any]:
    from app.notify.providers import provider_status

    st = provider_status(settings)
    return {
        k: {"will_use": v["will_use"], "live": v["live"], "simulated_only": v["simulated_only"]}
        for k, v in st.items()
    }


def outbox_stats(db: Any) -> Dict[str, Any]:
    counts: Dict[str, int] = {}
    per_channel: Dict[str, int] = {}
    for snap in db.collection(OUTBOX).stream():
        d = snap.to_dict()
        counts[d.get("status", "?")] = counts.get(d.get("status", "?"), 0) + 1
        per_channel[d.get("channel", "?")] = per_channel.get(d.get("channel", "?"), 0) + 1
    return {"by_status": counts, "by_channel": per_channel, "total": sum(counts.values())}


def list_recent(db: Any, collection: str = OUTBOX, limit: int = 50) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for snap in db.collection(collection).stream():
        d = snap.to_dict()
        d.setdefault("id", snap.id)
        rows.append(d)
    rows.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return rows[:limit]


def purge_old(db: Any) -> int:
    cutoff = (now_utc() - timedelta(days=max(1, settings.NOTIFY_RETENTION_DAYS))).isoformat(timespec="seconds")
    removed = 0
    for name in (OUTBOX, DELIVERIES):
        for snap in db.collection(name).stream():
            if (snap.to_dict().get("created_at") or "") < cutoff:
                snap.reference.delete()
                removed += 1
    return removed


def dev_outbox_files(limit: int = 20) -> List[Dict[str, str]]:
    """List artifacts written by the dev provider (proof-of-send for demos/audits)."""
    root = settings.NOTIFY_DEV_OUTBOX_DIR
    if not os.path.isdir(root):
        return []
    files: List[Tuple[float, str, str]] = []
    for channel in os.listdir(root):
        chan_dir = os.path.join(root, channel)
        if not os.path.isdir(chan_dir):
            continue
        for fn in os.listdir(chan_dir):
            fp = os.path.join(chan_dir, fn)
            if os.path.isfile(fp):
                files.append((os.path.getmtime(fp), f"{channel}/{fn}", fp))
    files.sort(reverse=True)
    return [
        {"name": name, "channel": name.split("/")[0], "modified": datetime.utcfromtimestamp(m).isoformat(timespec="seconds")}
        for m, name, _ in files[:limit]
    ]
