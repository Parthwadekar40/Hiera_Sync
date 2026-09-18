"""Comparative evaluation harness: heuristic engine vs. alternative predictors.

The project claim is "better than the models reported in the literature". A claim needs a
measurement, so this module ships the experiment itself:

  baselines compared
    1. deadline_only      - red/amber/green on calendar distance (classic ERP behaviour)
    2. progress_gap       - expected-minus-actual progress threshold (MS-Project style)
    3. static_priority    - the declared priority field alone (what most colleges use)
    4. logistic_regression - trained by gradient descent on the same features (sklearn-free)
    5. random_forest_lite  - depth-limited CART ensemble trained on the same features
  ours
    6. hierasync_heuristic - the weighted multi-factor engine in risk.py

Metrics: ROC-AUC, PR-AUC, precision/recall/F1 at the operating threshold, Brier score and
calibration error. Ground truth comes from `synthetic_corpus`, a generative model whose
outcome depends on the same observable signals plus noise and unobservable shocks - so no
method (including ours) can score 1.000, which keeps the comparison honest.

Run:  python -m app.engine.benchmarks --tasks 600 --out ../docs/benchmark_results.json
"""

from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.engine import risk as R

FEATURES = [
    "days_left_norm",
    "progress",
    "expected_progress",
    "idle_days_norm",
    "workload_norm",
    "reliability",
    "priority",
    "subtasks_open",
    "blocker_count",
    "has_estimate",
]


# --------------------------------------------------------------------- corpus generator
def synthetic_corpus(n: int = 600, seed: int = 7, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Generate labelled tasks: each row has observable fields and a latent delay label."""
    rnd = random.Random(seed)
    now = now or datetime.utcnow()
    rows: List[Dict[str, Any]] = []
    for i in range(n):
        span = rnd.choice([2, 3, 5, 7, 10, 14, 21])
        created = now - timedelta(days=int(span * rnd.uniform(0.2, 1.6)))
        deadline = created + timedelta(days=span)
        elapsed = max(0.0, (now - created).total_seconds() / 86400.0)
        expected = min(1.0, elapsed / max(1.0, span))
        priority = rnd.choices(["Low", "Medium", "High", "Urgent"], weights=[2, 5, 4, 1])[0]
        reliability = rnd.uniform(0.45, 0.98)
        workload = rnd.randint(0, 8)
        idle = max(0.0, elapsed - rnd.uniform(0.0, elapsed) * reliability)
        has_estimate = rnd.random() > 0.4
        blockers = rnd.choices([0, 1, 2, 3], weights=[7, 3, 1, 1])[0]
        subtasks = rnd.randint(0, 8)
        subtasks_open = rnd.randint(0, subtasks) if subtasks else 0

        # progress drifts toward expected according to reliability, then saturates
        progress = max(0.0, min(100.0, 100.0 * expected * rnd.uniform(0.35, 1.15) * (0.55 + 0.55 * reliability) - subtasks_open * 2.0))
        if expected > 0.97 and progress < 99:
            progress = min(100.0, progress + rnd.uniform(0, 45))

        # latent delay propensity, plus an unobservable shock -> irreducible error
        logit = (
            -2.15
            + 3.1 * max(0.0, expected - progress / 100.0)
            + 1.7 * (1.0 - reliability)
            + 0.55 * min(3.0, workload / 3.0)
            + 0.45 * min(2.0, idle / max(1.0, span * 0.35))
            + 0.25 * blockers
            + (0.5 if priority in ("High", "Urgent") else 0.0)
            - 0.35 * (1.0 if has_estimate else 0.0)
            - 1.1 * max(0.0, (deadline - now).total_seconds() / 86400.0 / max(1.0, span))
            + rnd.gauss(0, 0.85)
        )
        p_true = 1.0 / (1.0 + math.exp(-logit))
        late = 1 if rnd.random() < p_true else 0

        assignee = f"fac_{i % 12}"
        rows.append(
            {
                "id": f"syn_{i:04d}",
                "title": f"Synthetic deliverable {i}",
                "description": "x" * rnd.choice([8, 40, 120, 300]),
                "status": rnd.choices(["In Progress", "TODO", "Blocked", "Completed"], weights=[6, 2, 1, 3])[0],
                "priority": priority,
                "deadline": deadline.date().isoformat(),
                "created_at": created.isoformat(timespec="seconds"),
                "updated_at": (now - timedelta(days=idle)).isoformat(timespec="seconds"),
                "progress": f"{progress:.0f}%",
                "assigned_id": assignee,
                "assigned": assignee,
                "estimated_effort": "16h" if has_estimate else "",
                "blockers": blockers,
                "blocked_by": [
                    {"id": f"dep_{i}_{b}", "title": f"Prerequisite {b} for {i}", "status": "In Progress"}
                    for b in range(blockers)
                ],
                "subtasks": [{"id": f"s{j}", "title": f"st {j}", "completed": j >= subtasks_open} for j in range(subtasks)],
                "label": late,
                "p_true": round(p_true, 4),
            }
        )
    return rows


def build_context(rows: List[Dict[str, Any]], now: Optional[datetime] = None) -> R.RiskContext:
    ctx = R.RiskContext()
    ctx.now = now or datetime.utcnow()
    users = {}
    for r in rows:
        a = r["assigned_id"]
        users.setdefault(a, {"id": a, "role": "FACULTY"})
    ctx = R.build_context(None, tasks=rows, users=users)
    return ctx


def feature_vector(task: Dict[str, Any], ctx: R.RiskContext) -> List[float]:
    dl, created, updated = R.deadline_of(task), R.created_of(task), R.updated_of(task)
    now = ctx.now
    span = max(1.0, (dl - created).total_seconds() / 86400.0) if dl and created else 7.0
    days_left = (dl - now).total_seconds() / 86400.0 if dl else 5.0
    elapsed = max(0.0, (now - created).total_seconds() / 86400.0) if created else span / 2
    progress = R.progress_of(task) / 100.0
    idle = (now - updated).total_seconds() / 86400.0 if updated else 3.0
    a = str(task.get("assigned_id") or task.get("assigned") or "")
    subs_open = sum(1 for s in (task.get("subtasks") or []) if not s.get("completed"))
    return [
        max(-1.0, min(1.0, days_left / span)),
        progress,
        min(1.0, elapsed / span),
        min(1.0, idle / max(1.0, span * 0.5)),
        min(1.5, ctx.weighted_load.get(a, 0.0) / max(1.0, ctx.capacity_of(a))),
        ctx.reliability.get(a, ctx.mean_reliability),
        {0.7: 0.0, 1.0: 0.33, 1.3: 0.66, 1.6: 1.0}.get(R.priority_weight(task.get("priority")), 0.33),
        min(1.0, subs_open / 6.0),
        min(1.0, (len(task.get("blocked_by") or []) + (2 if str(task.get("status", "")).lower() == "blocked" else 0)) / 3.0),
        1.0 if (task.get("estimated_effort") or task.get("effort_hours")) else 0.0,
    ]


# --------------------------------------------------------------------- baseline models
def deadline_only(task: Dict[str, Any], ctx: R.RiskContext) -> float:
    """Red/amber/green on calendar distance only - what most campus ERPs do."""
    dl = R.deadline_of(task)
    if not dl:
        return 0.5
    days = (dl - ctx.now).total_seconds() / 86400.0
    if days < 0:
        return 0.95
    if days <= 1:
        return 0.70
    if days <= 4:
        return 0.40
    if days <= 9:
        return 0.20
    return 0.05


def progress_gap(task: Dict[str, Any], ctx: R.RiskContext) -> float:
    dl, created = R.deadline_of(task), R.created_of(task)
    if not dl:
        return 0.5
    span = max(1.0, (dl - (created or dl - timedelta(days=7))).total_seconds() / 86400.0)
    elapsed = max(0.0, (ctx.now - (created or dl)).total_seconds() / 86400.0)
    gap = max(0.0, min(1.0, elapsed / span - R.progress_of(task) / 100.0))
    return min(1.0, gap * 1.8)


def static_priority(task: Dict[str, Any], ctx: R.RiskContext) -> float:
    return {"Low": 0.15, "Medium": 0.35, "High": 0.65, "Urgent": 0.85}.get(str(task.get("priority", "Medium")), 0.35)


class LogisticRegression:
    """Full-batch GD with L2 and standardisation - dependency-free, deterministic."""

    def __init__(self, lr: float = 0.35, epochs: int = 600, l2: float = 1e-3, seed: int = 3):
        self.lr, self.epochs, self.l2, self.seed = lr, epochs, l2, seed
        self.w: List[float] = []
        self.b: float = 0.0
        self.mu: List[float] = []
        self.sd: List[float] = []

    def _std(self, X: List[List[float]]) -> List[List[float]]:
        if not self.mu:
            d = len(X[0])
            self.mu = [sum(row[i] for row in X) / len(X) for i in range(d)]
            self.sd = [max(1e-6, math.sqrt(sum((row[i] - self.mu[i]) ** 2 for row in X) / len(X))) for i in range(d)]
        return [[(row[i] - self.mu[i]) / self.sd[i] for i in range(len(row))] for row in X]

    @staticmethod
    def _sig(z: float) -> float:
        if z < -35:
            return 0.0
        if z > 35:
            return 1.0
        return 1.0 / (1.0 + math.exp(-z))

    def fit(self, X: List[List[float]], y: List[int]) -> "LogisticRegression":
        Xs = self._std(X)
        d, n = len(Xs[0]), len(Xs)
        self.w = [0.0] * d
        self.b = 0.0
        for _ in range(self.epochs):
            grad_w = [0.0] * d
            grad_b = 0.0
            for row, label in zip(Xs, y):
                err = self._sig(sum(wi * xi for wi, xi in zip(self.w, row)) + self.b) - label
                for i in range(d):
                    grad_w[i] += err * row[i]
                grad_b += err
            self.w = [wi - self.lr * (grad_w[i] / n + self.l2 * wi) for i, wi in enumerate(self.w)]
            self.b -= self.lr * grad_b / n
        return self

    def predict_proba(self, X: List[List[float]]) -> List[float]:
        Xs = self._std(X)
        return [self._sig(sum(wi * xi for wi, xi in zip(self.w, row)) + self.b) for row in Xs]


class RandomForestLite:
    """Ensemble of depth-limited CART trees trained on bootstrap samples + feature bags."""

    def __init__(self, trees: int = 12, depth: int = 4, seed: int = 5, features_per_split: int = 4):
        self.trees, self.depth, self.seed, self.k = trees, depth, seed, features_per_split

    @staticmethod
    def _gini(labels: List[int]) -> float:
        if not labels:
            return 0.0
        p = sum(labels) / len(labels)
        return 1.0 - p * p - (1 - p) * (1 - p)

    def _best_split(self, X: List[List[float]], y: List[int], cols: List[int]) -> Optional[Tuple[int, float]]:
        best, best_gain = None, 1e-9
        parent = self._gini(y)
        for c in cols:
            vals = sorted({row[c] for row in X})
            if len(vals) > 13:  # quantile-binned candidate cuts keep the tree fit O(n·k)
                vals = [vals[int(i * (len(vals) - 1) / 12)] for i in range(13)]
            for lo, hi in zip(vals, vals[1:]):
                thr = (lo + hi) / 2.0
                ly = [lab for row, lab in zip(X, y) if row[c] <= thr]
                ry = [lab for row, lab in zip(X, y) if row[c] > thr]
                if not ly or len(ry) == 0:
                    continue
                gain = parent - (len(ly) * self._gini(ly) + len(ry) * self._gini(ry)) / len(y)
                if gain > best_gain:
                    best_gain, best = gain, (c, thr)
        return best

    def _grow(self, X: List[List[float]], y: List[int], depth: int, cols: List[int]) -> Dict[str, Any]:
        if depth <= 0 or len(set(y)) < 2 or len(y) < 12:
            rate = sum(y) / len(y) if y else 0.5
            return {"leaf": round(rate, 4)}
        split = self._best_split(X, y, cols)
        if not split:
            return {"leaf": round(sum(y) / len(y), 4)}
        c, thr = split
        lx, ly, rx, ry = [], [], [], []
        for row, lab in zip(X, y):
            (lx if row[c] <= thr else rx).append(row)
            (ly if row[c] <= thr else ry).append(lab)
        if not lx or not rx:
            return {"leaf": round(sum(y) / len(y), 4)}
        return {
            "col": c,
            "thr": thr,
            "left": self._grow(lx, ly, depth - 1, cols),
            "right": self._grow(rx, ry, depth - 1, cols),
        }

    def fit(self, X: List[List[float]], y: List[int]) -> "RandomForestLite":
        rnd = random.Random(self.seed)
        self.models = []
        d = len(X[0])
        for _ in range(self.trees):
            idx = [rnd.randrange(len(X)) for _ in range(len(X))]
            bx = [X[i] for i in idx]
            by = [y[i] for i in idx]
            cols = rnd.sample(range(d), min(self.k, d))
            self.models.append(self._grow(bx, by, self.depth, cols))
        return self

    def _pred(self, node: Dict[str, Any], row: List[float]) -> float:
        if "leaf" in node:
            return node["leaf"]
        return self._pred(node["left"] if row[node["col"]] <= node["thr"] else node["right"], row)

    def predict_proba(self, X: List[List[float]]) -> List[float]:
        return [sum(self._pred(t, row) for t in self.models) / len(self.models) for row in X]


# --------------------------------------------------------------------- metrics
def roc_auc(y: List[int], scores: List[float]) -> float:
    pairs = sorted(zip(scores, y))
    ranks: List[float] = []
    i = 0
    while i < len(pairs):
        j = i
        while j + 1 < len(pairs) and pairs[j + 1][0] == pairs[i][0]:
            j += 1
        avg = (i + j) / 2.0 + 1
        ranks.extend([avg] * (j - i + 1))
        i = j + 1
    pos = sum(y)
    neg = len(y) - pos
    if pos == 0 or neg == 0:
        return 0.5
    sum_pos = sum(r for r, (_, lab) in zip(ranks, pairs) if lab == 1)
    return (sum_pos - pos * (pos + 1) / 2.0) / (pos * neg)


def average_precision(y: List[int], scores: List[float]) -> float:
    order = sorted(range(len(y)), key=lambda i: -scores[i])
    total_pos = max(1, sum(y))
    hits, ap = 0, 0.0
    for rank, idx in enumerate(order, start=1):
        if y[idx]:
            hits += 1
            ap += hits / rank
    return ap / total_pos


def confusion_at(y: List[int], probs: List[float], thr: float = 0.5) -> Dict[str, float]:
    tp = sum(1 for a, p in zip(y, probs) if a == 1 and p >= thr)
    fp = sum(1 for a, p in zip(y, probs) if a == 0 and p >= thr)
    fn = sum(1 for a, p in zip(y, probs) if a == 1 and p < thr)
    tn = sum(1 for a, p in zip(y, probs) if a == 0 and p < thr)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    n = max(1, len(y))
    brier = sum((p - a) ** 2 for p, a in zip(probs, y)) / n
    ece = 0.0
    for lo in [i / 10 for i in range(10)]:
        bucket = [(p, a) for p, a in zip(probs, y) if lo <= p < lo + 0.1]
        if bucket:
            conf = sum(p for p, _ in bucket) / len(bucket)
            acc = sum(a for _, a in bucket) / len(bucket)
            ece += abs(conf - acc) * len(bucket) / n
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": round(prec, 3), "recall": round(rec, 3), "f1": round(f1, 3), "brier": round(brier, 4), "ece": round(ece, 4), "base_rate": round(sum(y) / n, 3), "flag_rate": round((tp + fp) / n, 3)}


def thresholds(y: List[int], probs: List[float]) -> Dict[str, float]:
    """Score at the operating point that matters for triage: top-decile alerting."""
    order = sorted(range(len(y)), key=lambda i: -probs[i])
    k = max(1, int(len(y) * 0.2))
    top = order[:k]
    hit = sum(y[i] for i in top) / k
    return {"top_20pct_precision": round(hit, 3)}


# --------------------------------------------------------------------- experiment
def evaluate(n: int = 600, seed: int = 7, train_frac: float = 0.6, verbose: bool = True) -> Dict[str, Any]:
    rows = synthetic_corpus(n=n, seed=seed)
    now = datetime.utcnow()
    ctx = build_context(rows, now)

    X = [feature_vector(t, ctx) for t in rows]
    y = [int(t["label"]) for t in rows]
    split = int(len(rows) * train_frac)
    Xtr, ytr, Xte, yte = X[:split], y[:split], X[split:], y[split:]
    te_rows = rows[split:]

    ours: List[float] = []
    for t in rows[split:]:
        a = R.assess(t, ctx, now=now)
        ours.append(a["risk_score"] / 100.0)

    lr = LogisticRegression().fit(Xtr, ytr)
    rf = RandomForestLite().fit(Xtr, ytr)

    scorers: Dict[str, Callable[[Dict[str, Any], R.RiskContext], float]] = {
        "deadline_only (classic ERP)": deadline_only,
        "progress_gap (MS-Project style)": progress_gap,
        "static_priority (manual triage)": static_priority,
    }
    results: Dict[str, Any] = {}
    y_te = y[split:]
    for name, fn in scorers.items():
        scores = [fn(t, ctx) for t in te_rows]
        results[name] = _pack(y_te, scores)
    results["logistic_regression (this data)"] = _pack(y_te, lr.predict_proba(Xte))
    results["random_forest_lite (this data)"] = _pack(y_te, rf.predict_proba(Xte))
    results["HieraSync heuristic risk engine"] = _pack(y_te, ours)

    # --- weight calibration fitted on the TRAINING labels only, then evaluated on test
    from app.engine.calibrate import coordinate_descent

    cal_weights, cal_info = coordinate_descent(rows[:split], ctx, y[:split], rounds=3)
    import copy as _copy

    ctx_cal = _copy.copy(ctx)
    tot = sum(cal_weights.values()) or 1.0
    ctx_cal.weights = {k: cal_weights.get(k, 0.0) / tot for k in cal_weights}
    cal_scores = [R.assess(t, ctx_cal, now=now)["risk_score"] / 100.0 for t in te_rows]
    results["HieraSync heuristic + calibrated weights"] = _pack(y_te, cal_scores)
    summary_extra = {"calibration": cal_info}

    ranked = sorted(results.items(), key=lambda kv: kv[1]["roc_auc"], reverse=True)
    summary = {
        "experiment": {
            "samples": len(rows),
            "train": split,
            "test": len(te_rows),
            "positive_rate": round(sum(y_te) / max(1, len(y_te)), 3),
            "seed": seed,
            "features": FEATURES,
        },
        "results": results,
        "ranking": [{"model": k, "roc_auc": v["roc_auc"]} for k, v in ranked],
        "best": ranked[0][0],
        "our_rank": next(i + 1 for i, (k, _) in enumerate(ranked) if k.startswith("HieraSync")),
        "delta_vs_best_ml": round(results["HieraSync heuristic risk engine"]["roc_auc"] - max(results["logistic_regression (this data)"]["roc_auc"], results["random_forest_lite (this data)"]["roc_auc"]), 4),
        "lr_coefficients": {FEATURES[i]: round(w, 3) for i, w in enumerate(lr.w)},
        **summary_extra,
        "sample_efficiency_sweep": _sweep(seed=seed),
    }
    if verbose:
        print(json.dumps(summary, indent=2))
    return summary


def _quantile_threshold(scores: List[float], q: float = 0.8) -> float:
    ordered = sorted(scores)
    if not ordered:
        return 0.5
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


def _pack(y: List[int], scores: List[float]) -> Dict[str, Any]:
    """Ranking metrics (threshold-free) + accuracy at 0.5 + accuracy at an equal alert budget.

    Threshold-free metrics are what the comparison must be judged on: a calibration step is
    monotone, so it changes AUC/PR-AUC not at all, but would wreck a fixed-0.5 F1. Reporting
    both operating points keeps the table honest about that.
    """
    budget = _quantile_threshold(scores)
    return {
        "roc_auc": round(roc_auc(y, scores), 4),
        "pr_auc": round(average_precision(y, scores), 4),
        **confusion_at(y, scores),
        "f1_at_alert_budget": confusion_at(y, scores, thr=budget)["f1"],
        "precision_at_alert_budget": confusion_at(y, scores, thr=budget)["precision"],
        **thresholds(y, scores),
    }


def _sweep(seed: int = 7) -> Dict[str, Dict[str, float]]:
    """AUC vs training-set size: where a trained model needs data we do not have."""
    from app.engine.calibrate import coordinate_descent
    import copy as _copy

    out: Dict[str, Dict[str, float]] = {}
    for n in (60, 120, 240, 480, 960):
        rows = synthetic_corpus(n=n, seed=seed)
        now = datetime.utcnow()
        ctx = build_context(rows, now)
        split = max(20, int(n * 0.6))
        y = [int(r["label"]) for r in rows]
        X = [feature_vector(t, ctx) for t in rows]
        te = list(range(split, len(rows)))
        yte = y[split:]
        if len(yte) < 12 or sum(yte) == 0:
            continue
        scores: Dict[str, List[float]] = {
            "hiera_sync": [R.assess(rows[i], ctx, now=now)["risk_score"] / 100.0 for i in te],
            "deadline_only": [deadline_only(rows[i], ctx) for i in te],
        }
        try:
            lr = LogisticRegression().fit(X[:split], y[:split])
            scores["logistic_regression"] = lr.predict_proba(X[split:])
            rf = RandomForestLite().fit(X[:split], y[:split])
            scores["random_forest_lite"] = rf.predict_proba(X[split:])
            cw, _ = coordinate_descent(rows[:split], ctx, y[:split], rounds=2)
            c2 = _copy.copy(ctx)
            tot = sum(cw.values()) or 1.0
            c2.weights = {k: cw.get(k, 0.0) / tot for k in cw}
            scores["hiera_sync_calibrated"] = [R.assess(rows[i], c2, now=now)["risk_score"] / 100.0 for i in te]
        except Exception:  # pragma: no cover - defensive for tiny splits
            pass
        out[f"n={n}"] = {k: round(roc_auc(yte, v), 3) for k, v in scores.items()}
    return out


def main() -> None:  # pragma: no cover - CLI
    ap = argparse.ArgumentParser(description="Benchmark the HieraSync risk engine against baselines")
    ap.add_argument("--tasks", type=int, default=600)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    summary = evaluate(n=args.tasks, seed=args.seed, verbose=False)
    text = json.dumps(summary, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"wrote {args.out}")
    print(text)


if __name__ == "__main__":  # pragma: no cover
    main()
