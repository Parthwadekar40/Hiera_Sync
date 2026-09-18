"""Closed-loop weight calibration for the heuristic risk engine.

The engine is an additive model over eight interpretable factors, so "learning" means
fitting *weights*, not fitting an opaque function. Coordinate descent on ROC-AUC over the
institution's own labelled history (tasks that finished on time vs. late) gives us:

* data efficiency - converges on ~40-80 labelled rows, where gradient-trained trees and
  logistic models are still variance-dominated;
* interpretability preserved - every weight is a human-inspectable number, and the
  resulting profile is diffable for governance ("why did AIML score differently from
  Civil?");
* no drift catastrophe - re-run once a term (`POST /api/v1/risk/calibrate`) and the
  persisted profile lands in `risk_weights/global`, read back by `build_context()`.
"""

from __future__ import annotations

import copy
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.engine import risk as R

FACTOR_KEYS = list(R.DEFAULT_WEIGHTS.keys())


def _auc(y: List[int], s: List[float]) -> float:
    from app.engine.benchmarks import roc_auc

    return roc_auc(y, s)


def score_tasks_with_weights(tasks: List[Dict[str, Any]], ctx: R.RiskContext, weights: Dict[str, float]) -> List[float]:
    trial_ctx = copy.copy(ctx)
    total = sum(weights.values()) or 1.0
    trial_ctx.weights = {k: weights.get(k, 0.0) / total for k in FACTOR_KEYS}
    return [R.assess(t, trial_ctx)["risk_score"] for t in tasks]


def sub_scores(tasks: List[Dict[str, Any]], ctx: R.RiskContext) -> List[Dict[str, float]]:
    """One assessment pass, cached, so each weight trial is cheap linear algebra."""
    out: List[Dict[str, float]] = []
    for t in tasks:
        a = R.assess(t, ctx)
        out.append({f["key"]: f["sub_score"] for f in a.get("factors", [])})
    return out


def calibration_auc(matrix: List[Dict[str, float]], y: List[int], weights: Dict[str, float]) -> float:
    scores: List[float] = []
    for row in matrix:
        scores.append(sum(w * row.get(k, 0.0) for k, w in weights.items()))
    return _auc(y, scores)


def coordinate_descent(
    tasks: List[Dict[str, Any]],
    ctx: R.RiskContext,
    labels: List[int],
    *,
    rounds: int = 3,
    step: float = 0.06,
    min_weight: float = 0.0,
    max_weight: float = 0.45,
) -> Tuple[Dict[str, float], Dict[str, Any]]:
    """Greedy ±step search on each factor weight, maximising ROC-AUC on the labels."""
    weights = dict(R.DEFAULT_WEIGHTS)
    matrix = sub_scores(tasks, ctx)
    start = calibration_auc(matrix, labels, weights)
    best = start
    history = [{"round": 0, "auc": round(start, 4), "changed": None}]

    for r in range(1, rounds + 1):
        improved = False
        for key in FACTOR_KEYS:
            for delta in (step, -step, step * 2, -step * 2):
                cand = dict(weights)
                cand[key] = max(min_weight, min(max_weight, cand[key] + delta))
                if abs(cand[key] - weights[key]) < 1e-9:
                    continue
                score = calibration_auc(matrix, labels, cand)
                if score > best + 1e-5:
                    best, weights[key], improved = score, cand[key], True
        history.append({"round": r, "auc": round(best, 4), "changed": improved})
        if not improved:
            break

    total = sum(weights.values()) or 1.0
    normalised = {k: round(v / total, 4) for k, v in weights.items()}
    return normalised, {
        "auc_before": round(start, 4),
        "auc_after": round(best, 4),
        "gain": round(best - start, 4),
        "samples": len(labels),
        "positive_rate": round(sum(labels) / max(1, len(labels)), 3),
        "history": history,
        "weights": normalised,
    }


def labelled_history(tasks: List[Dict[str, Any]], now: Optional[datetime] = None) -> Tuple[List[Dict[str, Any]], List[int]]:
    """Derive supervision from closed tasks: late completion == positive (a 'miss')."""
    rows, labels = [], []
    for t in tasks:
        if not R.is_closed(t):
            continue
        dl = R.deadline_of(t)
        fin = None
        for key in ("completed_at", "updated_at", "closed_at"):
            fin = R.parse_dt(t.get(key))
            if fin:
                break
        if not dl or not fin:
            continue
        row = dict(t)
        row["created_at"] = row.get("created_at") or row.get("assigned_at")
        rows.append(row)
        labels.append(1 if fin > dl else 0)
    return rows, labels


def calibrate_db(db: Any, *, persist: bool = True, rounds: int = 3) -> Dict[str, Any]:
    """Calibrate from whatever the institution has already recorded, and persist it."""
    tasks = [s.to_dict() for s in db.collection("tasks").stream()]
    ctx = R.build_context(db, tasks=tasks)
    rows, labels = labelled_history(tasks, ctx.now)
    if len(rows) < 12:
        return {
            "persisted": False,
            "reason": f"insufficient labelled history ({len(rows)} closed tasks with both deadline and completion; need >= 12)",
            "samples": len(rows),
            "weights": ctx.weights,
        }
    weights, report = coordinate_descent(rows, ctx, labels, rounds=rounds)
    if persist:
        db.collection("risk_weights").document("global").set(
            {
                "weights": weights,
                "samples": report["samples"],
                "auc_before": report["auc_before"],
                "auc_after": report["auc_after"],
                "gain": report["gain"],
                "calibrated_at": datetime.utcnow().isoformat(timespec="seconds"),
                "engine": "hierasync-heuristic-v2",
            }
        )
    return {"persisted": persist, **report}
