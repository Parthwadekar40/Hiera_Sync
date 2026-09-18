"""Analytics engine: institutional KPIs, faculty scorecards, forecasting, exports.

Everything is computed from the live store on demand (no stale materialised tables at
this scale), and every metric carries its formula so the number can be defended in a
review meeting. Exports are CSV/JSON for NAAC / AQAR / AICTE-style reporting.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.engine import risk as R
from app.engine.approvals import evaluate_sla

BAND_ORDER = ["LOW", "MEDIUM", "HIGH"]


def _pct(part: float, whole: float) -> float:
    return round((part / whole * 100.0) if whole else 0.0, 1)


def scoped_tasks(tasks: List[Dict[str, Any]], *, department_id: Optional[str], assignee_id: Optional[str], days: int, now: datetime) -> List[Dict[str, Any]]:
    cutoff = now - timedelta(days=days)
    out = []
    for t in tasks:
        if department_id and t.get("department_id") and t.get("department_id") != department_id:
            continue
        if assignee_id and str(t.get("assigned_id") or t.get("assigned") or "") not in (assignee_id, ""):
            continue
        created = R.created_of(t)
        if created and created < cutoff:
            continue
        out.append(t)
    return out


def on_time_stats(tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
    closed, on_time, late, late_by = 0, 0, 0, []
    for t in tasks:
        if not R.is_closed(t):
            continue
        closed += 1
        dl, fin = R.deadline_of(t), R._parse_completed(t)
        if not dl or not fin:
            continue
        if fin <= dl:
            on_time += 1
        else:
            late += 1
            late_by.append((fin - dl).total_seconds() / 86400.0)
    return {
        "closed": closed,
        "on_time": on_time,
        "late": late,
        "on_time_rate": _pct(on_time, closed),
        "avg_days_late": round(sum(late_by) / len(late_by), 2) if late_by else 0.0,
    }


# small helper exposed on the module for readability
def _parse_completed(task: Dict[str, Any]):
    for key in ("completed_at", "closed_at", "updated_at"):
        dt = R.parse_dt(task.get(key))
        if dt:
            return dt
    return None


R._parse_completed = _parse_completed  # type: ignore[attr-defined]


def scorecard(db: Any, *, department_id: Optional[str] = None, assignee_id: Optional[str] = None, days: int = 90, now: Optional[datetime] = None) -> Dict[str, Any]:
    """One endpoint that answers: is this department healthy, and where do I intervene?"""
    now = now or datetime.utcnow()
    tasks_all = [dict(s.to_dict(), id=s.id) for s in db.collection("tasks").stream()]
    users = {str(u.id): u.to_dict() for u in db.collection("users").stream()}
    ctx = R.build_context(db, tasks=tasks_all, users=users)
    tasks = scoped_tasks(tasks_all, department_id=department_id, assignee_id=assignee_id, days=days, now=now)

    assessments = [R.assess(t, ctx, now=now) for t in tasks]
    by_id = {str(t.get("id")): t for t in tasks}
    open_tasks = [(t, a) for t, a in zip(tasks, assessments) if R.is_active(t)]
    bands = {b: sum(1 for _, a in open_tasks if a["risk_level"] == b) for b in BAND_ORDER}

    otd = on_time_stats(tasks)
    active = len(open_tasks)
    overdue = sum(1 for t, _ in open_tasks if (R.deadline_of(t) or now) < now)

    # approvals
    approvals = [dict(s.to_dict(), id=s.id) for s in db.collection("approvals").stream()]
    pending_appr, breached, decided = [], 0, []
    approval_hours: List[float] = []
    for a in approvals:
        if (a.get("status") or "").upper() in ("PENDING",):
            sla = evaluate_sla(a, now)
            pending_appr.append({**a, "sla": sla})
            breached += 1 if sla["breached"] else 0
        elif (a.get("status") or "").upper() in ("APPROVED", "REJECTED"):
            decided.append(a)
            started, done = R.parse_dt(a.get("created_at")), R.parse_dt(a.get("decided_at"))
            if started and done:
                approval_hours.append(max(0.0, (done - started).total_seconds() / 3600.0))

    # notifications / automation health
    deliveries = [s.to_dict() for s in db.collection("notification_deliveries").stream()]
    sent = sum(1 for d in deliveries if d.get("status") in ("sent", "simulated"))
    failed = sum(1 for d in deliveries if d.get("status") in ("dead", "retry"))
    latencies = [d.get("latency_ms", 0) for d in deliveries if isinstance(d.get("latency_ms"), (int, float))]

    workload = ctx.weighted_load or {}
    mean_load = round(sum(workload.values()) / len(workload), 2) if workload else 0.0
    spread = round(max(workload.values()) - min(workload.values()), 2) if workload else 0.0

    top_risks = sorted(
        (
            {
                "task_id": t.get("id"),
                "title": t.get("title"),
                "assignee": t.get("assigned") or t.get("assigned_id"),
                "deadline": (R.deadline_of(t).date().isoformat() if R.deadline_of(t) else None),
                "risk_score": a["risk_score"],
                "risk_level": a["risk_level"],
                "delay_probability": a["delay_probability"],
                "drivers": a["drivers"],
                "recommendation": (a["recommendations"] or [""])[0],
            }
            for t, a in open_tasks
        ),
        key=lambda x: -x["risk_score"],
    )[:10]

    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "window_days": days,
        "scope": {"department_id": department_id, "assignee_id": assignee_id},
        "tasks": {  # key contract consumed by insights() and the CSV exporter
            "total": len(tasks),
            "active": active,
            "completed": otd["closed"],
            "overdue": overdue,
            "overdue_rate": _pct(overdue, active),
            "completion_rate": _pct(otd["closed"], len(tasks)),
            "on_time_rate": otd["on_time_rate"],
            "avg_days_late": otd["avg_days_late"],
            "avg_progress": round(sum(R.progress_of(t) for t, _ in open_tasks) / active, 1) if active else 100.0,
        },
        "risk": {
            "bands": bands,
            "mean_score": round(sum(a["risk_score"] for _, a in open_tasks) / active, 1) if active else 0.0,
            "high_risk_count": bands["HIGH"],
            "at_risk_count": sum(1 for _, a in open_tasks if a.get("at_risk")),
            "projected_misses": round(sum(a["delay_probability"] for _, a in open_tasks), 1),
            "mean_confidence": round(sum(a["confidence"] for _, a in open_tasks) / active, 2) if active else 0.0,
        },
        "approvals": {
            "pending": len(pending_appr),
            "breached_sla": breached,
            "sla_compliance": _pct(len(pending_appr) - breached, len(pending_appr)) if pending_appr else 100.0,
            "median_hours_to_decision": round(sorted(approval_hours)[len(approval_hours) // 2], 1) if approval_hours else None,
            "decided": len(decided),
            "rejection_rate": _pct(sum(1 for a in decided if (a.get("status") or "").upper() == "REJECTED"), len(decided)),
        },
        "workload": {
            "per_assignee": [
                {
                    "assignee": key,
                    "name": (users.get(key) or {}).get("name", key),
                    "weighted_load": round(load, 2),
                    "capacity": ctx.capacity_of(key),
                    "utilisation_pct": _pct(load, ctx.capacity_of(key)),
                }
                for key, load in sorted(workload.items(), key=lambda kv: -kv[1])[:15]
            ],
            "mean_load": mean_load,
            "spread": spread,
            "balance_index": round(max(0.0, 100.0 - spread * 18.0), 1),
        },
        "automation": {
            "deliveries_total": len(deliveries),
            "delivered": sent,
            "failed_or_retrying": failed,
            "delivery_success_rate": _pct(sent, len(deliveries)),
            "mean_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else 0.0,
            "simulated_only": sum(1 for d in deliveries if d.get("simulated")),
        },
        "top_risks": top_risks,
        "insights": [],  # filled by insights() below
    }


def faculty_metrics(db: Any, *, department_id: Optional[str] = None, days: int = 90, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Per-teacher scorecard with explicit weights and a data-sufficiency flag."""
    now = now or datetime.utcnow()
    tasks_all = [dict(s.to_dict(), id=s.id) for s in db.collection("tasks").stream()]
    users = {str(u.id): u.to_dict() for u in db.collection("users").stream()}
    ctx = R.build_context(db, tasks=tasks_all, users=users)

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for t in tasks_all:
        if department_id and t.get("department_id") and t.get("department_id") != department_id:
            continue
        key = str(t.get("assigned_id") or t.get("assignee_id") or t.get("assigned") or "unassigned")
        grouped.setdefault(key, []).append(t)

    out: List[Dict[str, Any]] = []
    for key, rows in grouped.items():
        if key == "unassigned":
            continue
        ot = on_time_stats(rows)
        active = [t for t in rows if R.is_active(t)]
        overdue = sum(1 for t in active if (R.deadline_of(t) or now) < now)
        avg_progress = sum(R.progress_of(t) for t in active) / len(active) if active else 100.0
        assess_scores = [R.assess(t, ctx, now=now)["risk_score"] for t in active] or [0.0]
        load = ctx.weighted_load.get(key, 0.0)
        cap = max(1.0, ctx.capacity_of(key))

        on_time = ot["on_time_rate"]
        completion = _pct(ot["closed"], len(rows))
        progress = avg_progress
        balance = max(0.0, 100.0 - abs(load / cap - 0.8) * 100.0)
        responsiveness = max(0.0, 100.0 - overdue * 18.0)
        score = round(on_time * 0.32 + completion * 0.20 + progress * 0.18 + balance * 0.15 + responsiveness * 0.15, 1)
        sample = ot["closed"] + len(active)
        confidence = round(min(0.95, 0.35 + sample / 24.0), 2)

        why: List[str] = []
        if on_time < 80:
            why.append(f"on-time completion is {on_time:.0f}% (target 90%)")
        else:
            why.append(f"strong on-time record ({on_time:.0f}%)")
        if overdue:
            why.append(f"{overdue} task(s) currently past due")
        if load / cap > 1.1:
            why.append(f"carrying {load:.1f} weighted tasks vs capacity {cap:.1f} (overloaded)")
        elif load / cap < 0.35:
            why.append("under-utilised relative to capacity")
        if assess_scores and max(assess_scores) > 70:
            why.append(f"highest single-task risk is {max(assess_scores):.0f}/100")

        user = users.get(key, {})
        out.append(
            {
                "assignee_id": key,
                "name": user.get("name") or key,
                "role": user.get("role", "FACULTY"),
                "designation": user.get("designation", ""),
                "department_id": user.get("department_id") or department_id,
                "tasks_total": len(rows),
                "active": len(active),
                "completed": ot["closed"],
                "overdue": overdue,
                "on_time_rate": on_time,
                "completion_rate": completion,
                "avg_progress": round(progress, 1),
                "peak_risk": round(max(assess_scores), 1),
                "mean_risk": round(sum(assess_scores) / len(assess_scores), 1),
                "weighted_load": round(load, 2),
                "capacity": cap,
                "utilisation_pct": _pct(load, cap),
                "reliability": round(ctx.reliability.get(key, ctx.mean_reliability) * 100, 1),
                "productivity_score": score,
                "confidence": confidence,
                "sample_size": sample,
                "explanation": "; ".join(why).capitalize(),
                "recommendation": (
                    "Rebalance assignments before adding new work."
                    if load / cap > 1.1
                    else "Candidate for additional ownership."
                    if load / cap < 0.35 and on_time >= 85
                    else "Daily check-ins on the highest-risk item."
                    if overdue
                    else "Maintain current cadence."
                ),
            }
        )
    out.sort(key=lambda x: -x["productivity_score"])
    return out


def forecast(db: Any, *, horizon_days: int = 14, department_id: Optional[str] = None, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Deterministic completion forecast from observed velocity (no black box)."""
    now = now or datetime.utcnow()
    tasks = [dict(s.to_dict(), id=s.id) for s in db.collection("tasks").stream()]
    ctx = R.build_context(db, tasks=tasks)
    open_rows = [t for t in tasks if R.is_active(t) and (not department_id or t.get("department_id") in (None, department_id))]

    velocities: List[float] = []
    for t in tasks:
        created, updated, prog = R.created_of(t), R.updated_of(t), R.progress_of(t)
        if created and updated and prog > 0 and updated > created:
            days_active = max(0.5, (updated - created).total_seconds() / 86400.0)
            velocities.append(prog / days_active)
    mean_velocity = round(sum(velocities) / len(velocities), 2) if velocities else 6.0  # ~6 progress pts/day default

    buckets: Dict[str, int] = {}
    at_risk = 0
    for t in open_rows:
        eta = R.projected_eta(t, ctx)
        if eta is None:
            eta = max(0.1, (100.0 - R.progress_of(t)) / max(0.5, mean_velocity))
        finish = now + timedelta(days=eta)
        week = f"week_of_{(finish + timedelta(days=(6 - finish.weekday()) % 7)).date().isoformat()}"
        buckets[week] = buckets.get(week, 0) + 1
        dl = R.deadline_of(t)
        if (dl and finish > dl) or eta > horizon_days:
            at_risk += 1

    return {
        "horizon_days": horizon_days,
        "method": f"velocity-based ETA (mean observed velocity {mean_velocity} progress pts/day, floored by remaining work)",
        "open_tasks": len(open_rows),
        "expected_completions_by_week": [
            {"week": k, "count": v} for k, v in sorted(buckets.items())[: max(1, horizon_days // 7 + 1)]
        ],
        "likely_to_miss": at_risk,
        "within_horizon": len(open_rows) - at_risk,
        "capacity_note": "Excludes assignee saturation; treat as optimistic bound.",
    }


def insights(data: Dict[str, Any]) -> List[Dict[str, str]]:
    """Rule-based natural-language insights (explainable by construction)."""
    out: List[Dict[str, str]] = []
    t, a, w, au = data["tasks"], data["approvals"], data["workload"], data["automation"]

    if t["overdue_rate"] >= 25:
        out.append({"severity": "CRITICAL", "text": f"{t['overdue']} of {t['active']} active tasks ({t['overdue_rate']}%) are past due.", "action": "Run the escalation ladder and re-plan the two oldest items this week."})
    elif t["overdue_rate"] > 0:
        out.append({"severity": "MEDIUM", "text": f"{t['overdue']} task(s) overdue out of {t['active']} active.", "action": "Ask for status updates on those items only - avoid blanket chasing."})
    if data["risk"]["high_risk_count"] >= max(3, int(t["active"] * 0.2)):
        out.append({"severity": "HIGH", "text": f"{data['risk']['high_risk_count']} tasks are in HIGH/CRITICAL risk bands; model expects ~{data['risk']['projected_misses']} misses.", "action": "Clear the top 3 drivers: they explain most of the risk."})
    if a["pending"] and a["breached_sla"] / max(1, a["pending"]) > 0.3:
        out.append({"severity": "HIGH", "text": f"{a['breached_sla']} of {a['pending']} pending approvals have breached their SLA.", "action": "Delegate approvals for the next 3 days or add a standing 15-minute review slot."})
    if w["spread"] > 3:
        out.append({"severity": "MEDIUM", "text": f"Workload spread is {w['spread']} weighted tasks between the lightest and heaviest faculty.", "action": "Move 1-2 items from the top of the load table to the bottom."})
    if au["deliveries_total"] and au["failed_or_retrying"]:
        out.append({"severity": "MEDIUM", "text": f"{au['failed_or_retrying']} notification delivery attempt(s) failed or are retrying.", "action": "Check channel credentials in Settings → Notifications."})
    if t["on_time_rate"] >= 90 and t["completed"]:
        out.append({"severity": "LOW", "text": f"On-time completion is {t['on_time_rate']}% across {t['completed']} closed tasks.", "action": "Stable pipeline - safe to raise throughput targets."})
    if not out:
        out.append({"severity": "LOW", "text": "No structural risks detected in this window.", "action": "Continue scheduled automation."})
    return out


def to_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""
    flat: List[Dict[str, Any]] = []
    for r in rows:
        item = {}
        for k, v in r.items():
            if isinstance(v, (list, dict)):
                item[k] = "; ".join(map(str, v)) if isinstance(v, list) else "; ".join(f"{kk}={vv}" for kk, vv in v.items())
            else:
                item[k] = v
        flat.append(item)
    cols: List[str] = []
    for r in flat:
        for k in r:
            if k not in cols:
                cols.append(k)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(flat)
    return buf.getvalue()


def department_rollup(db: Any, *, days: int = 90) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    depts = [dict(s.to_dict(), id=s.id) for s in db.collection("departments").stream()]
    for dept in depts or [{"id": None, "name": "Unassigned", "code": "—"}]:
        data = scorecard(db, department_id=dept.get("id"), days=days)
        data["insights"] = insights(data)
        rows.append(
            {
                "department_id": dept.get("id"),
                "department": dept.get("name"),
                "code": dept.get("code"),
                "active_tasks": data["tasks"]["active"],
                "completion_rate": data["tasks"]["completion_rate"],
                "on_time_rate": data["tasks"]["on_time_rate"],
                "overdue_rate": data["tasks"]["overdue_rate"],
                "high_risk_tasks": data["risk"]["high_risk_count"],
                "projected_misses": data["risk"]["projected_misses"],
                "approvals_pending": data["approvals"]["pending"],
                "approvals_breached": data["approvals"]["breached_sla"],
                "workload_balance_index": data["workload"]["balance_index"],
                "health_index": round(
                    data["tasks"]["on_time_rate"] * 0.4
                    + data["tasks"]["completion_rate"] * 0.25
                    + data["approvals"]["sla_compliance"] * 0.2
                    + data["workload"]["balance_index"] * 0.15,
                    1,
                ),
            }
        )
    rows.sort(key=lambda r: -r["health_index"])
    return rows
