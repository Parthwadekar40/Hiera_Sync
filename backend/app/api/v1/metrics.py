"""Analytics v2 (Slide 19): departmental completion stats, faculty performance table,
on-time rate tracking, and one-click exportable summaries.

Every number is served together with the formula that produced it, and exports are
NAAC/NBA-shaped CSV/JSON so the accreditation pack is a download, not a weekend.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field

from app.auth.permissions import get_current_active_user
from app.auth.rbac import analytics_scope, can
from app.database.session import get_db
from app.engine import analytics as AN
from app.engine import risk as R
from app.models.models import User

router = APIRouter()


def _guard(user: User, need: str = "view_analytics"):
    if not can(user.role.value, need):
        raise HTTPException(status_code=403, detail=f"Role {user.role.value} cannot {need}")


@router.get("/scorecard")
def scorecard(
    days: int = Query(90, ge=7, le=730),
    department_id: Optional[str] = None,
    db: Any = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """The single health view: tasks, risk bands, approvals SLA, workload, automation."""
    _guard(current_user)
    scope = analytics_scope(current_user.role.value)
    dept = department_id if scope == "full_institute" else current_user.department_id
    data = AN.scorecard(db, department_id=dept, assignee_id=None if scope != "self" else current_user.id, days=days)
    data["insights"] = AN.insights(data)
    data["analytics_scope"] = scope
    data["formulas"] = {
        "completion_rate": "closed tasks / total tasks in window",
        "on_time_rate": "tasks closed at or before deadline / closed tasks",
        "overdue_rate": "active tasks past deadline / active tasks",
        "projected_misses": "sum of delay_probability over active tasks",
        "sla_compliance": "pending approvals within SLA / pending approvals",
        "balance_index": "max(0, 100 - 18 * (max load - min load))",
        "delivery_success_rate": "sent+simulated deliveries / all delivery attempts",
    }
    return data


@router.get("/faculty")
def faculty(
    days: int = Query(90, ge=7, le=730),
    department_id: Optional[str] = None,
    db: Any = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Faculty performance table with explicit weights (Slide 19 / M8)."""
    _guard(current_user)
    dept = department_id if analytics_scope(current_user.role.value) == "full_institute" else current_user.department_id
    rows = AN.faculty_metrics(db, department_id=dept, days=days)
    if analytics_scope(current_user.role.value) == "self":
        rows = [r for r in rows if r["assignee_id"] == current_user.id]
    return {
        "count": len(rows),
        "weights": {"on_time": 0.32, "completion": 0.20, "progress": 0.18, "workload_balance": 0.15, "responsiveness": 0.15},
        "note": "score = 0.32*on_time + 0.20*completion + 0.18*avg_progress + 0.15*balance + 0.15*(100-18*overdue), each 0-100",
        "items": rows,
    }


@router.get("/departments")
def departments(db: Any = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Institute rollup across departments, ranked by health index."""
    _guard(current_user)
    return {"items": AN.department_rollup(db)}


@router.get("/forecast")
def forecast(
    horizon_days: int = Query(14, ge=3, le=120),
    department_id: Optional[str] = None,
    db: Any = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _guard(current_user)
    return AN.forecast(db, horizon_days=horizon_days, department_id=department_id)


@router.get("/risk-trend")
def risk_trend(db: Any = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Risk distribution snapshot history (written by the scheduler sweep) for trend charts."""
    _guard(current_user)
    snaps = [dict(s.to_dict(), id=s.id) for s in db.collection("risk_snapshots").stream()]
    snaps.sort(key=lambda x: x.get("taken_at") or "")
    return {"count": len(snaps), "items": snaps[-60:]}


@router.get("/export")
def export(
    kind: str = Query("scorecard", description="scorecard|faculty|tasks|approvals|departments|audit"),
    format: str = Query("csv", pattern="^(csv|json)$"),
    days: int = Query(90, ge=7, le=730),
    db: Any = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """One-click export for NAAC / NBA / NIRF evidence packs."""
    _guard(current_user, "export_reports")
    dept = None if analytics_scope(current_user.role.value) == "full_institute" else current_user.department_id

    if kind == "scorecard":
        data = AN.scorecard(db, department_id=dept, days=days)
        data["insights"] = AN.insights(data)
        rows = [data["tasks"] | data["risk"] | data["approvals"] | data["workload"] | {"generated_at": data["generated_at"]}]
        payload, filename = _render(rows, format, f"hierasync-scorecard-{datetime.utcnow():%Y%m%d}")
    elif kind == "faculty":
        rows = AN.faculty_metrics(db, department_id=dept, days=days)
        payload, filename = _render(rows, format, f"hierasync-faculty-{datetime.utcnow():%Y%m%d}")
    elif kind == "departments":
        rows = AN.department_rollup(db, days=days)
        payload, filename = _render(rows, format, f"hierasync-departments-{datetime.utcnow():%Y%m%d}")
    elif kind == "approvals":
        rows = [dict(s.to_dict(), id=s.id) for s in db.collection("approvals").stream()]
        for r in rows:
            r.pop("audit", None)
        payload, filename = _render(rows, format, f"hierasync-approvals-{datetime.utcnow():%Y%m%d}")
    elif kind == "audit":
        rows = []
        for s in db.collection("approvals").stream():
            d = dict(s.to_dict(), id=s.id)
            for e in d.get("audit", []) or []:
                rows.append({"approval_id": d.get("id"), "title": d.get("title"), "kind": d.get("kind"), **{k: v for k, v in e.items() if k != "hash"}, "hash": (e.get("hash") or "")[:16]})
        payload, filename = _render(rows, format, f"hierasync-audit-{datetime.utcnow():%Y%m%d}")
    else:  # tasks
        tasks = []
        ctx = R.build_context(db)
        for s in db.collection("tasks").stream():
            t = dict(s.to_dict(), id=s.id)
            if dept and t.get("department_id") and t.get("department_id") != dept:
                continue
            a = R.assess(t, ctx)
            tasks.append(
                {
                    "id": t.get("id"),
                    "title": t.get("title"),
                    "assignee": t.get("assigned") or t.get("assigned_id"),
                    "priority": t.get("priority"),
                    "status": t.get("status"),
                    "progress_pct": a and t.get("progress"),
                    "deadline": t.get("deadline"),
                    "risk_score": a["risk_score"],
                    "risk_level": a["risk_level"],
                    "delay_probability": a["delay_probability"],
                    "top_factor": (a["drivers"] or [""])[0],
                    "recommendation": (a["recommendations"] or [""])[0],
                }
            )
        payload, filename = _render(tasks, format, f"hierasync-tasks-{datetime.utcnow():%Y%m%d}")

    media = "text/csv" if format == "csv" else "application/json"
    return Response(
        content=payload,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _render(rows, format: str, base: str):
    import json

    if format == "json":
        return json.dumps(rows, indent=2, default=str), base + ".json"
    return AN.to_csv(rows), base + ".csv"


@router.post("/snapshot")
def take_snapshot(db: Any = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Persist the current risk distribution (feeds /risk-trend and the weekly report)."""
    if not can(current_user.role.value, "manage_system"):
        raise HTTPException(status_code=403, detail="Administrators only")
    snap = _run_snapshot(db)
    return {"ok": True, **snap}


def _run_snapshot(db: Any) -> dict:
    now = datetime.utcnow()
    tasks = [dict(s.to_dict(), id=s.id) for s in db.collection("tasks").stream()]
    ctx = R.build_context(db, tasks=tasks)
    open_tasks = [t for t in tasks if R.is_active(t)]
    bands = {b: 0 for b in ("LOW", "MEDIUM", "HIGH")}
    total, at_risk, prob = 0, 0, 0.0
    for t in open_tasks:
        a = R.assess(t, ctx, now=now)
        bands[a["risk_level"]] = bands.get(a["risk_level"], 0) + 1
        total += a["risk_score"]
        prob += a["delay_probability"]
        at_risk += 1 if a["at_risk"] else 0
    doc = {
        "taken_at": now.isoformat(timespec="seconds"),
        "bands": bands,
        "open_tasks": len(open_tasks),
        "mean_risk": round(total / len(open_tasks), 1) if open_tasks else 0.0,
        "at_risk": at_risk,
        "expected_misses": round(prob, 2),
        "created_by": "scheduler",
    }
    db.collection("risk_snapshots").document(f"snap_{now:%Y%m%d_%H%M%S}").set(doc)
    return doc
