"""HieraSync Heuristic AI Risk Engine (v2).

Purpose
-------
Predict, *before* it happens, how likely a task is to miss its deadline - and say why in
language a Head of Department can act on.

Why heuristic instead of a black-box model
------------------------------------------
1. Data reality: a department generates tens-to-hundreds of task records a semester. An
   XGBoost/LSTM pipeline that needs 10^4-10^6 labelled rows would be trained on noise,
   and would silently over-fit. A rule-calibrated additive model is honest about that.
2. Explainability is a product requirement, not a nice-to-have: every factor reports its
   own contribution and evidence string, so `score -> reason -> action` is auditable
   (NAIC/AICTE-style review, faculty objections, principal escalations).
3. Determinism & cost: identical inputs give identical output, no GPU, no drift monitor;
   the model still learns from history because several factors are fed by live
   aggregates (assignee reliability, velocity, approval latency).

Design
------
risk = 100 * sigma-weighted sum_i ( w_i * s_i )   with s_i in [0,100] normalised sub-scores
     and w_i summing to 1.0 (weights overridable per department via `risk_weights`).

Eight orthogonal factors: schedule pressure, time urgency, stagnation/velocity,
assignee capacity, historical reliability, dependency/blocker state, scope complexity,
approval latency. A confidence value reflects feature completeness, and cold-start
assignees are shrunk toward the population prior instead of being punished or rewarded.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.db.store import parse_dt

# --------------------------------------------------------------------- configuration
# Calibration constants for the logit fusion. BASE_PRIOR < 0 because a department's base
# slip rate is well under 50%; EVIDENCE_GAIN scales how strongly agreed evidence moves the
# posterior (tuned on the benchmark corpus in app/engine/benchmarks.py).
BASE_PRIOR = -0.55
EVIDENCE_GAIN = 1.35
_EPS = 0.02


def _logit(p: float) -> float:
    p = max(_EPS, min(1 - _EPS, p))
    return math.log(p / (1 - p))


def _sigmoid(z: float) -> float:
    if z < -30:
        return 0.0
    if z > 30:
        return 1.0
    return 1.0 / (1.0 + math.exp(-z))


DEFAULT_WEIGHTS: Dict[str, float] = {
    "schedule_pressure": 0.24,
    "time_urgency": 0.20,
    "stagnation": 0.14,
    "capacity": 0.14,
    "reliability": 0.10,
    "dependency": 0.08,
    "complexity": 0.05,
    "approval_latency": 0.05,
}

# Slide 18 contract: LOW / MEDIUM / HIGH badges. `at_risk` preserves the
# critical tail (>=75) for escalation policy without inventing a 4th public level.
AT_RISK_CUTOFF = 75.0
BANDS = [(55, "HIGH"), (30, "MEDIUM"), (0, "LOW")]

FACTOR_LABELS = {
    "schedule_pressure": "Plan-vs-progress gap",
    "time_urgency": "Deadline proximity",
    "stagnation": "Activity stall",
    "capacity": "Assignee workload",
    "reliability": "Assignee track record",
    "dependency": "Blockers & dependencies",
    "complexity": "Scope & uncertainty",
    "approval_latency": "Approval wait time",
}

DONE_STATUSES = {"completed", "closed", "done", "verified", "awaiting approval", "pending approval"}
ACTIVE_STATUSES = {"", "todo", "pending", "in progress", "in_progress", "blocked", "revision requested", "started"}


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def progress_of(task: Dict[str, Any]) -> float:
    raw = task.get("progress", 0)
    if isinstance(raw, str):
        raw = raw.replace("%", "").strip() or "0"
    val = _f(raw, 0.0)
    return max(0.0, min(100.0, val))


def status_of(task: Dict[str, Any]) -> str:
    return str(task.get("status") or "TODO").strip().lower().replace("_", " ")


def is_closed(task: Dict[str, Any]) -> bool:
    return status_of(task) in DONE_STATUSES


def is_active(task: Dict[str, Any]) -> bool:
    return not is_closed(task)


def priority_weight(priority: Any) -> float:
    return {"urgent": 1.6, "critical": 1.6, "high": 1.3, "medium": 1.0, "moderate": 1.0, "low": 0.7}.get(
        str(priority or "medium").strip().lower(), 1.0
    )


def deadline_of(task: Dict[str, Any]) -> Optional[datetime]:
    for key in ("deadline", "due_date", "due", "end_date"):
        dt = parse_dt(task.get(key))
        if dt:
            return dt
    return None


def created_of(task: Dict[str, Any]) -> Optional[datetime]:
    for key in ("created_at", "assigned_at", "start_date"):
        dt = parse_dt(task.get(key))
        if dt:
            return dt
    return None


def updated_of(task: Dict[str, Any]) -> Optional[datetime]:
    for key in ("updated_at", "last_update_at", "progress_updated_at", "completed_at"):
        dt = parse_dt(task.get(key))
        if dt:
            return dt
    return None


# --------------------------------------------------------------------- context
@dataclass
class RiskContext:
    """Everything the engine needs, pre-aggregated in a single pass over the store."""

    now: datetime = field(default_factory=datetime.utcnow)
    workload: Dict[str, int] = field(default_factory=dict)          # assignee -> active tasks
    weighted_load: Dict[str, float] = field(default_factory=dict)   # assignee -> priority-weighted load
    capacity: Dict[str, float] = field(default_factory=dict)        # assignee -> concurrent task capacity
    reliability: Dict[str, float] = field(default_factory=dict)     # assignee -> historical on-time ratio
    reliability_n: Dict[str, int] = field(default_factory=dict)
    mean_reliability: float = 0.78
    median_approval_hours: float = 24.0
    overdue_share: float = 0.15                                     # department baseline badness
    weights: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))

    def workload_of(self, key: Optional[str]) -> int:
        return int(self.workload.get(key or "", 0))

    def capacity_of(self, key: Optional[str]) -> float:
        return float(self.capacity.get(key or "", self._default_capacity()))

    def _default_capacity(self) -> float:
        vals = list(self.capacity.values()) or [4.0]
        return round(sum(vals) / len(vals), 2)


def build_context(db: Any, *, tasks: Optional[List[Dict[str, Any]]] = None, users: Optional[Dict[str, Dict[str, Any]]] = None) -> RiskContext:
    """O(n) aggregate builder shared by the API, the scheduler sweeps and the tests."""
    if tasks is None:
        tasks = [s.to_dict() for s in db.collection("tasks").stream()] if db is not None else []
    ctx = RiskContext()
    if users is None and db is not None:
        users = {}
        for snap in db.collection("users").stream():
            d = snap.to_dict()
            d.setdefault("id", snap.id)
            users[str(d.get("id"))] = d
    users = users or {}

    done_counts: Dict[str, int] = {}
    ontime_counts: Dict[str, int] = {}
    approval_deltas: List[float] = []
    overdue = 0
    active_total = 0

    for t in tasks:
        assignee = str(t.get("assigned_id") or t.get("assignee_id") or t.get("assigned") or t.get("assignee") or "")
        if is_active(t):
            ctx.workload[assignee] = ctx.workload.get(assignee, 0) + 1
            ctx.weighted_load[assignee] = ctx.weighted_load.get(assignee, 0.0) + priority_weight(t.get("priority"))
            active_total += 1
            dl = deadline_of(t)
            if dl and dl < ctx.now:
                overdue += 1
        else:
            done_counts[assignee] = done_counts.get(assignee, 0) + 1
            dl, fin = deadline_of(t), parse_dt(t.get("completed_at")) or parse_dt(t.get("updated_at"))
            if dl and fin:
                if fin <= dl:
                    ontime_counts[assignee] = ontime_counts.get(assignee, 0) + 1
                approval_deltas.append(max(0.0, (fin - (created_of(t) or fin)).total_seconds() / 3600.0))

    # reliability with shrinkage toward the population mean (cold start safe)
    all_assignees = set(done_counts) | set(ctx.workload)
    pooled = 0.0
    for a in all_assignees:
        n = done_counts.get(a, 0)
        raw = (ontime_counts.get(a, 0) / n) if n else None
        if raw is None:
            ctx.reliability[a] = ctx.mean_reliability
            ctx.reliability_n[a] = 0
        else:
            shrunk = (n * raw + 4 * ctx.mean_reliability) / (n + 4)  # Beta(4,1)-style prior
            ctx.reliability[a] = max(0.05, min(1.0, shrunk))
            ctx.reliability_n[a] = n
            pooled += raw
    if all_assignees:
        ctx.mean_reliability = round(pooled / len(all_assignees), 3) or ctx.mean_reliability

    # capacity: role-aware default, refined by throughput over the observed window
    for a in all_assignees | set(users):
        user = users.get(a, {})
        base = {"HOD": 5, "PRINCIPAL": 3, "ADMIN": 4, "FACULTY": 4, "TEACHER": 4, "TA": 3, "STUDENT": 2, "STAFF": 3}.get(
            str(user.get("role", "")).upper(), 4
        )
        throughput = done_counts.get(a, 0)
        ctx.capacity[a] = round(base + min(2.0, throughput / 8.0), 2)

    if approval_deltas:
        approval_deltas.sort()
        ctx.median_approval_hours = round(approval_deltas[len(approval_deltas) // 2], 1) or 24.0
    ctx.overdue_share = round(overdue / active_total, 3) if active_total else 0.0

    # per-department weight overrides (governance knob, no redeploys)
    if db is not None:
        try:
            wdoc = db.collection("risk_weights").document("global").get()
            if wdoc.exists:
                payload = wdoc.to_dict().get("weights") or {}
                for k, v in payload.items():
                    if k in DEFAULT_WEIGHTS:
                        ctx.weights[k] = float(v)
        except Exception:  # pragma: no cover
            pass
    total = sum(ctx.weights.values()) or 1.0
    ctx.weights = {k: v / total for k, v in ctx.weights.items()}
    return ctx


# --------------------------------------------------------------------- factor scores
def _schedule_pressure(task: Dict[str, Any], ctx: RiskContext) -> Tuple[float, str]:
    """Gap between expected progress (time burned) and actual progress."""
    dl, created = deadline_of(task), created_of(task)
    progress = progress_of(task)
    if not dl:
        return 45.0, "No deadline recorded - progress cannot be validated against a plan."
    if not created:
        created = dl - timedelta(days=7)
    total_span = max(1.0, (dl - created).total_seconds() / 86400.0)
    elapsed = max(0.0, (ctx.now - created).total_seconds() / 86400.0)
    expected = min(100.0, 100.0 * (elapsed / total_span))
    gap = expected - progress
    if gap <= 0:
        return 0.0, f"On plan: {progress:.0f}% done vs {expected:.0f}% expected at day {elapsed:.0f}/{total_span:.0f}."
    score = min(100.0, gap * 1.6)
    return score, f"Behind plan by {gap:.0f} points ({progress:.0f}% done vs {expected:.0f}% expected by now)."


def _time_urgency(task: Dict[str, Any], ctx: RiskContext) -> Tuple[float, str]:
    dl = deadline_of(task)
    if not dl:
        return 30.0, "Deadline missing; treated as moderate urgency."
    days_left = (dl - ctx.now).total_seconds() / 86400.0
    remaining_work = max(0.0, 100.0 - progress_of(task)) / 100.0
    # Effort-normalised urgency: 2 days left is fine at 95% done, fatal at 10%.
    need_days = remaining_work * 4.0  # calibrated: a full task ≈ 4 focused working days
    if days_left < 0:
        score = min(100.0, 70.0 + abs(days_left) * 3.5)
        return score, f"Overdue by {abs(days_left):.0f} day(s)."
    ratio = (days_left + 0.25) / max(0.5, need_days)
    if ratio < 0.35:
        score = 92.0
    elif ratio < 0.7:
        score = 72.0
    elif ratio < 1.2:
        score = 48.0
    elif ratio < 2.0:
        score = 24.0
    else:
        score = 8.0
    return score, f"{days_left:.1f} day(s) left for ~{need_days:.1f} day(s) of remaining work (ratio {ratio:.2f})."


def _stagnation(task: Dict[str, Any], ctx: RiskContext) -> Tuple[float, str]:
    last = updated_of(task) or created_of(task)
    if not last:
        return 35.0, "No update history recorded for this task."
    idle = (ctx.now - last).total_seconds() / 86400.0
    dl = deadline_of(task)
    days_left = (dl - ctx.now).total_seconds() / 86400.0 if dl else 7.0
    allowed = max(1.0, min(6.0, days_left * 0.6))
    if idle <= allowed:
        return max(0.0, idle / max(1.0, allowed) * 20.0), f"Updated {idle:.1f} day(s) ago - within cadence."
    score = min(100.0, 30.0 + (idle - allowed) * 9.0)
    return score, f"No progress update for {idle:.1f} day(s) (expected every {allowed:.1f} day(s))."


def _capacity(task: Dict[str, Any], ctx: RiskContext) -> Tuple[float, str]:
    assignee = str(task.get("assigned_id") or task.get("assignee_id") or task.get("assigned") or "")
    if not assignee:
        return 40.0, "Task has no assignee - nobody is accountable for it yet."
    load = ctx.weighted_load.get(assignee, float(ctx.workload_of(assignee)))
    cap = max(1.0, ctx.capacity_of(assignee))
    ratio = load / cap
    if ratio <= 0.8:
        return max(0.0, ratio * 20.0), f"Assignee carrying {load:.1f} weighted task(s) vs capacity {cap:.1f}."
    score = min(100.0, 25.0 + (ratio - 0.8) * 75.0)
    return score, f"Assignee overload: {load:.1f} weighted task(s) against capacity {cap:.1f} ({ratio*100:.0f}% of capacity)."


def _reliability(task: Dict[str, Any], ctx: RiskContext) -> Tuple[float, str]:
    assignee = str(task.get("assigned_id") or task.get("assignee_id") or task.get("assigned") or "")
    rel = ctx.reliability.get(assignee, ctx.mean_reliability)
    n = ctx.reliability_n.get(assignee, 0)
    score = (1.0 - rel) * 100.0
    if n == 0:
        return min(score, 55.0), "No completion history for this assignee yet - using department average."
    return score, f"{rel*100:.0f}% of this assignee's last {n} task(s) finished on time."


def _dependency(task: Dict[str, Any], ctx: RiskContext, blockers: Optional[List[Dict[str, Any]]] = None) -> Tuple[float, str]:
    if blockers is None:
        blockers = task.get("blocked_by") or []
    blocked_open = [b for b in blockers if is_active(b)]
    subs = task.get("subtasks") or []
    subs_open = sum(1 for s in subs if not s.get("completed"))
    if task.get("blocked") or str(task.get("status", "")).lower() in ("blocked", "on hold"):
        return 95.0, "Task is explicitly marked blocked."
    if blocked_open:
        names = ", ".join(str(b.get("title", "blocker"))[:40] for b in blocked_open[:3])
        return min(100.0, 60.0 + 10.0 * len(blocked_open)), f"Waiting on {len(blocked_open)} unfinished prerequisite(s): {names}."
    if subs:
        share = subs_open / max(1, len(subs))
        dl = deadline_of(task)
        days_left = (dl - ctx.now).total_seconds() / 86400.0 if dl else 5.0
        if days_left < 3 and share > 0.4:
            return min(100.0, 40.0 + share * 40.0), f"{subs_open}/{len(subs)} subtasks still open with {days_left:.1f} day(s) left."
        return share * 30.0, f"{subs_open}/{len(subs)} subtasks open."
    return 0.0, "No open dependencies."


def _complexity(task: Dict[str, Any], ctx: RiskContext) -> Tuple[float, str]:
    subs = task.get("subtasks") or []
    desc = str(task.get("description") or "")
    notes: List[str] = []
    score = 0.0
    if len(subs) >= 6:
        score += 30.0
        notes.append(f"{len(subs)} subtasks")
    elif len(subs) >= 3:
        score += 15.0
        notes.append(f"{len(subs)} subtasks")
    if not task.get("estimated_effort") and not task.get("effort_hours"):
        score += 25.0
        notes.append("effort not estimated")
    if len(desc) < 25:
        score += 20.0
        notes.append("thin description")
    if task.get("is_recurring") or task.get("recurrence_pattern"):
        score += 10.0
        notes.append("recurring")
    if priority_weight(task.get("priority")) >= 1.5:
        score += 15.0
        notes.append("urgent priority")
    return min(100.0, score), ("Complexity drivers: " + ", ".join(notes) + ".") if notes else "Scope looks standard and well described."


def _approval_latency(task: Dict[str, Any], ctx: RiskContext) -> Tuple[float, str]:
    st = status_of(task)
    if st not in ("awaiting approval", "pending approval", "in review"):
        return 0.0, "Not currently queued for approval."
    waiting_hours = (ctx.now - (updated_of(task) or ctx.now)).total_seconds() / 3600.0
    med = max(1.0, ctx.median_approval_hours)
    ratio = waiting_hours / med
    if ratio <= 1.0:
        return min(35.0, ratio * 25.0), f"In approval queue for {waiting_hours:.0f}h (typical {med:.0f}h)."
    return min(100.0, 40.0 + ratio * 30.0), f"Approval queue time is {ratio:.1f}x the department norm ({waiting_hours:.0f}h vs {med:.0f}h)."


# --------------------------------------------------------------------- assessment
def band_for(score: float) -> str:
    for cutoff, label in BANDS:
        if score >= cutoff:
            return label
    return "LOW"


def is_at_risk(score: float) -> bool:
    """HIGH band and severe enough to justify escalation beyond a reminder."""
    return score >= AT_RISK_CUTOFF


def confidence_for(task: Dict[str, Any], ctx: RiskContext, factors: List[Dict[str, Any]]) -> float:
    """How much of the picture we could actually see (0.35 blind .. 0.97 rich)."""
    have = 0.34
    have += 0.16 if deadline_of(task) else 0.0
    have += 0.12 if created_of(task) else 0.0
    have += 0.12 if updated_of(task) else 0.0
    have += 0.10 if task.get("progress") not in (None, "") else 0.0
    have += 0.10 if (task.get("subtasks") or []) else 0.0
    a = str(task.get("assigned_id") or task.get("assignee_id") or task.get("assigned") or "")
    have += 0.13 if ctx.reliability_n.get(a, 0) > 0 else 0.0
    have += 0.06 if task.get("estimated_effort") or task.get("effort_hours") else 0.0
    spread = 1.0 - (max(f["sub_score"] for f in factors) - min(f["sub_score"] for f in factors)) / 100.0 if factors else 1.0
    return round(max(0.35, min(0.97, have * (0.9 + 0.1 * spread))), 2)


def assess(
    task: Dict[str, Any],
    ctx: Optional[RiskContext] = None,
    *,
    blockers: Optional[List[Dict[str, Any]]] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Score one task. Returns a JSON-safe assessment with per-factor evidence."""
    ctx = ctx or RiskContext()
    if now:
        ctx.now = now

    if is_closed(task):
        completed_late = False
        dl = deadline_of(task)
        fin = parse_dt(task.get("completed_at")) or updated_of(task)
        if dl and fin and fin > dl:
            completed_late = True
        return {
            "task_id": task.get("id"),
            "risk_score": 0.0,
            "risk_level": "CLOSED",
            "confidence": 0.95,
            "delay_probability": 0.0,
            "factors": [],
            "drivers": [],
            "explanation": "Task is completed or awaiting approval; risk scoring is suspended."
            + (" Note: it closed after its deadline." if completed_late else ""),
            "recommendations": ["Consider archiving this task from the active board."] if not completed_late else ["Log the reason for late closure in the review note."],
            "eta_days": None,
            "projected_completion": None,
            "days_left": (dl - ctx.now).total_seconds() / 86400.0 if dl else None,
            "completed_late": completed_late,
        }

    raw: List[Tuple[str, float, str]] = [
        ("schedule_pressure", *_schedule_pressure(task, ctx)),
        ("time_urgency", *_time_urgency(task, ctx)),
        ("stagnation", *_stagnation(task, ctx)),
        ("capacity", *_capacity(task, ctx)),
        ("reliability", *_reliability(task, ctx)),
        ("dependency", *_dependency(task, ctx, blockers)),
        ("complexity", *_complexity(task, ctx)),
        ("approval_latency", *_approval_latency(task, ctx)),
    ]

    factors: List[Dict[str, Any]] = []
    total = 0.0
    # Logit (evidence) fusion, as in credit-scorecard models: each factor contributes
    # signed evidence log(p/(1-p)) instead of a linear slice, so a confident signal moves
    # the score much more than a marginal one, and the displayed 0-100 score is exactly
    # 100x the delay probability. `BASE_PRIOR` encodes "most tasks do finish".
    z = BASE_PRIOR
    for key, sub, evidence in raw:
        weight = ctx.weights.get(key, 0.0)
        contribution = sub * weight
        total += contribution
        z += weight * _logit(0.03 + 0.94 * (sub / 100.0)) * EVIDENCE_GAIN
        factors.append(
            {
                "key": key,
                "label": FACTOR_LABELS.get(key, key),
                "sub_score": round(sub, 1),
                "weight": round(weight, 4),
                "contribution": round(contribution, 1),
                "share_of_risk": 0.0,  # filled below
                "evidence": evidence,
            }
        )

    p_delay = _sigmoid(z)
    # Score stays human-facing (0-100) and monotone in the probability, so a 62 always
    # means ~62% modelled slip chance - no "what does this number mean?" in a review.
    score = max(1.0, min(99.0, 100.0 * p_delay))
    delay_p = round(p_delay, 3)
    for fct in factors:
        fct["share_of_risk"] = round((fct["contribution"] / score) * 100.0, 1) if score else 0.0
    drivers = sorted(factors, key=lambda f: f["contribution"], reverse=True)[:3]

    eta_days = projected_eta(task, ctx)
    recos = recommendations(task, ctx, factors, eta_days)
    return {
        "task_id": task.get("id"),
        "risk_score": round(score, 1),
        "risk_level": band_for(score),
        "linear_score": round(total, 1),
        "evidence_logit": round(z, 3),
        "at_risk": is_at_risk(score),
        "escalation_severity": "CRITICAL" if is_at_risk(score) else band_for(score),
        "delay_probability": delay_p,
        "confidence": confidence_for(task, ctx, factors),
        "factors": factors,
        "drivers": [d["label"] for d in drivers],
        "top_drivers": drivers,
        "explanation": build_explanation(task, drivers, score),
        "recommendations": recos,
        "eta_days": eta_days,
        "projected_completion": (ctx.now + timedelta(days=eta_days)).date().isoformat() if eta_days is not None else None,
        "days_left": ((deadline_of(task) - ctx.now).total_seconds() / 86400.0) if deadline_of(task) else None,
        "overdue_by_days": max(0.0, (ctx.now - deadline_of(task)).total_seconds() / 86400.0) if deadline_of(task) else 0.0,
        "weights_used": ctx.weights,
    }


def projected_eta(task: Dict[str, Any], ctx: RiskContext) -> Optional[float]:
    """Forecast days-to-completion from observed velocity, floored by remaining effort."""
    dl, created, updated = deadline_of(task), created_of(task), updated_of(task)
    progress = progress_of(task)
    remaining_work = max(0.0, 100.0 - progress) / 100.0 * 4.0  # 4 focused days per full task
    if created and updated and updated > created and progress > 0:
        days_active = max(0.5, (updated - created).total_seconds() / 86400.0)
        velocity = progress / days_active  # progress points per calendar day
        if velocity > 0.1:
            return round((100.0 - progress) / velocity, 2)
    a = str(task.get("assigned_id") or task.get("assignee_id") or task.get("assigned") or "")
    overload = ctx.weighted_load.get(a, 0.0) / max(1.0, ctx.capacity_of(a))
    return round(remaining_work * 4.0 * max(1.0, overload), 2)


def build_explanation(task: Dict[str, Any], drivers: List[Dict[str, Any]], score: float) -> str:
    bits = [str(task.get("title") or "This task")]
    for d in drivers:
        if d["sub_score"] >= 12:
            bits.append(d["evidence"].rstrip("."))
    band = band_for(score)
    tail = {
        "HIGH": "Deadline is likely to slip - intervene this week." if is_at_risk(score) else "Needs attention this week.",
        "MEDIUM": "Monitor and confirm the next update date.",
        "LOW": "On track.",
    }[band]
    return f"{'; '.join(bits)}. Risk {score:.0f}/100 ({band}). {tail}"


def recommendations(task: Dict[str, Any], ctx: RiskContext, factors: List[Dict[str, Any]], eta_days: Optional[float]) -> List[str]:
    by_key = {f["key"]: f for f in factors}
    out: List[str] = []
    dl = deadline_of(task)
    days_left = (dl - ctx.now).total_seconds() / 86400.0 if dl else None

    if eta_days is not None and days_left is not None and eta_days > max(0.5, days_left):
        out.append(
            f"Projected finish in ~{eta_days:.1f} day(s) vs {max(0.0, days_left):.1f} day(s) of slack: "
            "re-scope now (split deliverable) or raise a deadline-change approval."
        )
    if by_key.get("capacity", {}).get("sub_score", 0) > 55:
        alt = least_loaded_assignee(ctx, exclude=str(task.get("assigned_id") or task.get("assigned") or ""))
        out.append(f"Rebalance: assignee is saturated." + (f" Next best fit: {alt}." if alt else ""))
    if by_key.get("stagnation", {}).get("sub_score", 0) > 55:
        out.append("Request a 3-line status update today and switch to daily check-ins until progress moves.")
    if by_key.get("dependency", {}).get("sub_score", 0) > 55:
        out.append("Escalate the blocking prerequisite to its owner's HOD; this task cannot recover on its own.")
    if by_key.get("complexity", {}).get("sub_score", 0) > 55:
        out.append("Add an effort estimate and break the work into verifiable subtasks (risk model is under-informed).")
    if by_key.get("approval_latency", {}).get("sub_score", 0) > 45:
        out.append("Chase the pending approval - queue time is above the department norm.")
    if by_key.get("reliability", {}).get("sub_score", 0) > 62:
        out.append("Pair with a co-assignee: recent on-time rate for this assignee is weak.")
    if not out:
        out.append("Keep the current plan; auto-reminders before the deadline are already scheduled.")
    return out[:5]


def least_loaded_assignee(ctx: RiskContext, exclude: str = "") -> Optional[str]:
    best: Optional[str] = None
    best_ratio = 1e9
    for a, load in ctx.weighted_load.items():
        if not a or a == exclude:
            continue
        ratio = load / max(1.0, ctx.capacity_of(a))
        if ratio < best_ratio:
            best_ratio, best = ratio, a
    return best if best_ratio < 0.75 else None


def score_tasks(tasks: List[Dict[str, Any]], ctx: RiskContext, *, blockers_map: Optional[Dict[str, List[Dict[str, Any]]]] = None) -> List[Dict[str, Any]]:
    return [assess(t, ctx, blockers=(blockers_map or {}).get(str(t.get("id")))) for t in tasks]


def what_if(task: Dict[str, Any], ctx: RiskContext, overrides: Dict[str, Any]) -> Dict[str, Any]:
    """Live simulator used by the UI: 'what if I move the deadline / reassign / add a subtask?'."""
    trial = dict(task)
    trial.update({k: v for k, v in (overrides or {}).items() if k in {"deadline", "progress", "priority", "assigned", "assigned_id", "status", "subtasks", "description", "estimated_effort"}})
    before = assess(task, ctx)
    after = assess(trial, ctx)
    return {
        "before": {k: before[k] for k in ("risk_score", "risk_level", "delay_probability")},
        "after": {k: after[k] for k in ("risk_score", "risk_level", "delay_probability", "recommendations", "top_drivers")},
        "delta": round(after["risk_score"] - before["risk_score"], 1),
        "verdict": (
            "improves" if after["risk_score"] < before["risk_score"] - 2 else "worsens" if after["risk_score"] > before["risk_score"] + 2 else "neutral"
        ),
        "task_id": task.get("id"),
    }
