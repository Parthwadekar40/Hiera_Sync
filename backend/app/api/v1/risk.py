"""Risk engine API: scoring, board view, what-if simulator, weight governance, benchmark."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.auth.permissions import check_role, get_current_active_user
from app.database.session import get_db
from app.engine import risk as R
from app.engine.benchmarks import evaluate as run_benchmark
from app.engine.calibrate import calibrate_db
from app.models.models import RoleEnum, User

router = APIRouter()

_BENCH_CACHE: Dict[str, Any] = {"key": None, "result": None}


class WhatIfRequest(BaseModel):
    task_id: Optional[str] = None
    overrides: Dict[str, Any] = Field(default_factory=dict)
    task: Optional[Dict[str, Any]] = None


class WeightsRequest(BaseModel):
    weights: Dict[str, float]
    persist: bool = True


def _load_tasks(db: Any, user: User) -> List[Dict[str, Any]]:
    rows = [dict(s.to_dict(), id=s.id) for s in db.collection("tasks").stream()]
    if user.role in (RoleEnum.FACULTY, RoleEnum.TEACHER, RoleEnum.TA, RoleEnum.STUDENT):
        rows = [
            t
            for t in rows
            if str(t.get("assigned_id") or "") == user.id or user.name.lower() in str(t.get("assigned") or "").lower()
        ]
    return rows


@router.get("/board")
def risk_board(
    db: Any = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    band: Optional[str] = Query(None, description="LOW|MEDIUM|HIGH"),
    include_closed: bool = False,
    department_id: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
):
    """Every visible task with its assessment, sorted by risk - the HOD 'war room' feed."""
    tasks = _load_tasks(db, current_user)
    users = {str(u.id): u.to_dict() for u in db.collection("users").stream()}
    ctx = R.build_context(db, tasks=tasks, users=users)
    if department_id:
        tasks = [t for t in tasks if not t.get("department_id") or t.get("department_id") == department_id]

    scored = []
    for t in tasks:
        if not include_closed and not R.is_active(t):
            continue
        a = R.assess(t, ctx)
        if band and a["risk_level"] != band.upper():
            continue
        scored.append({**{k: t.get(k) for k in ("id", "title", "status", "priority", "progress", "deadline", "assigned", "assigned_id")}, "assessment": a})
    scored.sort(key=lambda x: -x["assessment"]["risk_score"])
    bands: Dict[str, int] = {b: 0 for b in ("LOW", "MEDIUM", "HIGH")}
    for row in scored:
        bands[row["assessment"]["risk_level"]] = bands.get(row["assessment"]["risk_level"], 0) + 1
    return {
        "count": len(scored),
        "bands": bands,
        "weights": ctx.weights,
        "context": {
            "mean_reliability": ctx.mean_reliability,
            "median_approval_hours": ctx.median_approval_hours,
            "department_overdue_share": ctx.overdue_share,
        },
        "tasks": scored[:limit],
    }


@router.get("/score/{task_id}")
def score_task(task_id: str, db: Any = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    tasks = _load_tasks(db, current_user)
    task = next((t for t in tasks if str(t.get("id")) == task_id), None)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found or not visible to you")
    users = {str(u.id): u.to_dict() for u in db.collection("users").stream()}
    ctx = R.build_context(db, tasks=tasks, users=users)
    return R.assess(task, ctx)


@router.post("/what-if")
def what_if(payload: WhatIfRequest, db: Any = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Interactive simulator: 'if I move this deadline / reassign it, how does risk react?'."""
    tasks = _load_tasks(db, current_user)
    users = {str(u.id): u.to_dict() for u in db.collection("users").stream()}
    ctx = R.build_context(db, tasks=tasks, users=users)
    if payload.task:
        return R.what_if(payload.task, ctx, payload.overrides)
    task = next((t for t in tasks if str(t.get("id")) == payload.task_id), None)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return R.what_if(task, ctx, payload.overrides)


@router.get("/weights")
def get_weights(db: Any = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    doc = db.collection("risk_weights").document("global").get()
    stored = doc.to_dict() if doc.exists else {}
    ctx = R.build_context(db)
    return {
        "effective_weights": ctx.weights,
        "default_weights": R.DEFAULT_WEIGHTS,
        "calibration": {k: v for k, v in stored.items() if k != "weights"} or {"status": "uncalibrated (defaults in use)"},
        "bands": [{"min": lo, "label": lbl} for lo, lbl in R.BANDS],
        "factor_labels": R.FACTOR_LABELS,
    }


@router.put("/weights")
def set_weights(
    payload: WeightsRequest,
    db: Any = Depends(get_db),
    current_user: User = Depends(check_role([RoleEnum.ADMIN, RoleEnum.PRINCIPAL, RoleEnum.HOD])),
):
    unknown = [k for k in payload.weights if k not in R.DEFAULT_WEIGHTS]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown factor(s): {', '.join(unknown)}")
    if payload.persist:
        db.collection("risk_weights").document("global").set(
            {
                "weights": payload.weights,
                "updated_by": current_user.id,
                "updated_at": datetime.utcnow().isoformat(timespec="seconds"),
                "source": "manual",
            }
        )
    return {"ok": True, "weights": payload.weights}


@router.post("/calibrate")
def calibrate(
    db: Any = Depends(get_db),
    current_user: User = Depends(check_role([RoleEnum.ADMIN, RoleEnum.PRINCIPAL])),
):
    """Re-fit factor weights on this department's own closed-task history (max AUC)."""
    report = calibrate_db(db)
    if not report.get("persisted"):
        report["note"] = "Defaults retained. Seed or complete more tasks, then re-run."
    return report


@router.get("/benchmark")
def benchmark(
    tasks: int = Query(400, ge=80, le=2000),
    seed: int = 7,
    db: Any = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Measured comparison against baselines and trained models (see docs/EVALUATION.md)."""
    key = f"{tasks}:{seed}"
    if _BENCH_CACHE["key"] != key:
        _BENCH_CACHE["result"] = run_benchmark(n=tasks, seed=seed, verbose=False)
        _BENCH_CACHE["key"] = key
    result = dict(_BENCH_CACHE["result"])
    stored = db.collection("risk_weights").document("global").get()
    result["live_profile"] = stored.to_dict() if stored.exists else {"status": "defaults"}
    return result
