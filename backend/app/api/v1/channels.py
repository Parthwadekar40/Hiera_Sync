"""Notification operations + automation control (Slide 19 "Notifications & Cron").

v1 shipped an in-app inbox with "prepared email gateway hooks". This turns those hooks into
a real delivery control plane: live channel status, per-user routing preferences, the
durable outbox, the delivery ledger, a template previewer, manual job triggers for demos,
and an SSE stream so alerts appear without a refresh.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.auth.jwt import verify_token
from app.auth.permissions import get_current_active_user
from app.auth.rbac import can
from app.config.settings import settings
from app.database.session import active_backend, backend_info, get_db
from app.models.models import User
from app.notify import templates
from app.notify.base import CHANNEL_EMAIL, CHANNEL_INAPP, CHANNEL_SMS, CHANNEL_WHATSAPP
from app.notify.engine import send_test
from app.notify.providers import provider_status
from app.notify.queue import dev_outbox_files, list_recent, outbox_stats, process_due, purge_old
from app.notify.routing import DEFAULT_PREFS, kind_severity, load_preferences, save_preferences
from app.schemas.schemas import TokenData
from app.utils.logging import logger
from app.notify.base import iso

router = APIRouter()


class PreferencesUpdate(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    whatsapp_number: Optional[str] = None
    email_enabled: Optional[bool] = None
    sms_enabled: Optional[bool] = None
    whatsapp_enabled: Optional[bool] = None
    whatsapp_opt_in: Optional[bool] = None
    quiet_hours_enabled: Optional[bool] = None
    quiet_hours: Optional[str] = None
    digest_mode: Optional[str] = Field(None, description="none|daily|weekly")
    min_severity_email: Optional[str] = None
    min_severity_sms: Optional[str] = None
    min_severity_whatsapp: Optional[str] = None
    muted_kinds: Optional[List[str]] = None


class PreviewRequest(BaseModel):
    kind: str = "deadline_risk"
    severity: str = "HIGH"
    title: str = "AI Lab Maintenance"
    message: str = "Progress has been flat for 4 days with 2 days left."


class TestRequest(BaseModel):
    channels: Optional[List[str]] = None


@router.get("/status")
def channel_status(db: Any = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Exactly which sender will be used per channel - no ambiguity during a demo."""
    status = provider_status(settings)
    # in-app is the system of record (a store write, not a network send) - report it too.
    status.setdefault(
        "inapp",
        {
            "channel": "inapp",
            "will_use": "document store collection `notifications`",
            "live": bool(settings.NOTIFY_INAPP_ENABLED),
            "simulated_only": False,
            "chain": [],
        },
    )
    prefs = load_preferences(db, current_user.id, current_user.dict())
    return {
        "notifications_enabled": settings.NOTIFY_ENABLED,
        "timezone": settings.NOTIFY_TIMEZONE,
        "quiet_hours_default": settings.DEFAULT_QUIET_HOURS,
        "policy": {
            "CRITICAL": settings.policy_for("CRITICAL"),
            "HIGH": settings.policy_for("HIGH"),
            "MEDIUM": settings.policy_for("MEDIUM"),
            "LOW": settings.policy_for("LOW"),
        },
        "retry": {
            "max_attempts": settings.NOTIFY_MAX_ATTEMPTS,
            "backoff_base_seconds": settings.NOTIFY_BACKOFF_BASE_SECONDS,
            "backoff_max_seconds": settings.NOTIFY_BACKOFF_MAX_SECONDS,
            "dedupe_window_minutes": settings.NOTIFY_DEDUPE_MINUTES,
            "rate_limit_per_minute": settings.NOTIFY_RATE_LIMIT_PER_MIN,
        },
        "channels": status,
        "your_reachability": {
            "email": prefs.get("email") or current_user.email,
            "phone": prefs.get("phone") or "not on file",
            "whatsapp_opt_in": bool(prefs.get("whatsapp_opt_in")),
        },
        "outbox": outbox_stats(db),
        "persistence": backend_info(),
    }


@router.get("/preferences")
def get_preferences(db: Any = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    prefs = load_preferences(db, current_user.id, current_user.dict())
    return {
        "preferences": prefs,
        "defaults": DEFAULT_PREFS,
        "policy_channels": {s: settings.policy_for(s) for s in ("CRITICAL", "HIGH", "MEDIUM", "LOW")},
        "muted_kinds_options": sorted(templates.TITLE_BY_KIND),
    }


@router.put("/preferences")
def update_preferences(
    payload: PreferencesUpdate,
    db: Any = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    patch = payload.dict(exclude_unset=True)
    if patch.get("phone") or patch.get("whatsapp_number"):
        from app.notify.base import normalize_phone

        if patch.get("phone"):
            patch["phone"] = normalize_phone(patch["phone"])
        if patch.get("whatsapp_number"):
            patch["whatsapp_number"] = normalize_phone(patch["whatsapp_number"])
    if patch.get("digest_mode") and patch["digest_mode"] not in ("none", "daily", "weekly"):
        raise HTTPException(status_code=422, detail="digest_mode must be none|daily|weekly")
    saved = save_preferences(db, current_user.id, patch)
    return {"ok": True, "preferences": saved}


@router.get("/outbox")
def outbox(
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    db: Any = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    rows = list_recent(db, "notification_outbox", limit=500)
    mine = [r for r in rows if r.get("user_id") == current_user.id or can(current_user.role.value, "run_automation")]
    if status:
        mine = [r for r in mine if r.get("status") == status.upper()]
    return {"count": len(mine), "stats": outbox_stats(db), "items": mine[:limit], "dev_artifacts": dev_outbox_files(12)}


@router.get("/deliveries")
def deliveries(
    limit: int = Query(60, ge=1, le=500),
    db: Any = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    rows = list_recent(db, "notification_deliveries", limit=limit)
    mine = [r for r in rows if r.get("user_id") == current_user.id or can(current_user.role.value, "run_automation")]
    summary: Dict[str, int] = {}
    for r in mine:
        summary[r.get("status", "?")] = summary.get(r.get("status", "?"), 0) + 1
    return {"count": len(mine), "summary": summary, "items": mine}


@router.post("/flush")
def flush(db: Any = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Send everything due, right now (used by demos and by the retry dashboard)."""
    if not can(current_user.role.value, "run_automation"):
        raise HTTPException(status_code=403, detail="Only HOD/Principal/Admin may drive the delivery worker")
    return process_due(db, limit=300)


@router.post("/test")
def test(payload: TestRequest, db: Any = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    return send_test(db, current_user.dict(), channels=payload.channels)


@router.post("/preview")
def preview(payload: PreviewRequest, current_user: User = Depends(get_current_active_user)):
    """Render the exact mail / SMS / WhatsApp text without sending anything."""
    rendered = templates.render(
        settings,
        kind=payload.kind,
        severity=payload.severity.upper(),
        ctx={"title": payload.title, "message": payload.message, "facts": {"Deadline": "2 days", "Progress": "35%"}},
    )
    return {**rendered, "html_length": len(rendered["html"]), "sms_segments": max(1, -(-len(rendered["text"]) // 160))}


@router.get("/kinds")
def kinds(current_user: User = Depends(get_current_active_user)):
    return {
        "kinds": [
            {"kind": k, "label": v, "default_severity": kind_severity(k), "routes_to": sorted({c for s in ("LOW", "MEDIUM", "HIGH", "CRITICAL") for c in settings.policy_for(s)})}
            for k, v in templates.TITLE_BY_KIND.items()
        ]
    }


@router.get("/jobs")
def jobs(current_user: User = Depends(get_current_active_user)):
    from app.scheduler.jobs import job_specs

    return {"scheduler_enabled": settings.SCHEDULER_ENABLED, "timezone": settings.NOTIFY_TIMEZONE, "jobs": job_specs()}


@router.post("/jobs/{job_id}/run")
def run_job(job_id: str, db: Any = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Manual trigger - a seminar audience will not wait for 08:00."""
    if not can(current_user.role.value, "run_automation"):
        raise HTTPException(status_code=403, detail="Only HOD/Principal/Admin may run jobs")
    from app.scheduler.jobs import run_job as _run

    result = _run(job_id, db, actor={"id": current_user.id, "name": current_user.name})
    if result is None:
        raise HTTPException(status_code=404, detail=f"Unknown job '{job_id}'")
    logger.info(f"Job {job_id} run manually by {current_user.name}: {result}")
    return {"job": job_id, "triggered_by": current_user.name, "result": result}


@router.post("/purge")
def purge(db: Any = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    if not can(current_user.role.value, "run_automation"):
        raise HTTPException(status_code=403, detail="Administrators only")
    return {"removed": purge_old(db), "retention_days": settings.NOTIFY_RETENTION_DAYS}


@router.get("/stream")
async def stream(token: str = Query(...), db: Any = Depends(get_db)):
    """SSE feed for live in-app alerts (EventSource cannot send Authorization headers)."""

    async def resolve_user():
        try:
            payload = verify_token(token, HTTPException(status_code=401, detail="invalid token"))
        except HTTPException:
            return None
        for snap in db.collection("users").where("email", "==", payload.email).stream():
            d = dict(snap.to_dict(), id=snap.id)
            d.pop("hashed_password", None)
            return d
        return None

    user = await resolve_user()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    seen = set()

    async def gen():
        # prime with the newest id so we only emit what happens after connect
        for snap in db.collection("notifications").stream():
            seen.add(snap.id)
        yield "retry: 3000\n\n"
        idle = 0
        while idle < 400:  # ~20 min ceiling per connection
            await asyncio.sleep(3)
            new_rows = []
            for snap in db.collection("notifications").stream():
                if snap.id in seen:
                    continue
                seen.add(snap.id)
                d = dict(snap.to_dict(), id=snap.id)
                if d.get("user_id") in (user.get("id"), "department", f"dept:{user.get('department_id')}"):
                    new_rows.append(d)
            if new_rows:
                idle = 0
                for row in new_rows:
                    yield f"event: alert\ndata: {json.dumps(row, default=str)}\n\n"
            else:
                idle += 1
                yield ": keep-alive\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
