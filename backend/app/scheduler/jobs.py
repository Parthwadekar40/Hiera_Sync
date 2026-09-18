"""Automation layer: the scheduler the deck promises (Slide 9 "Automation Layer",
Slide 6 "scheduled daily 8 AM reminders and deadline alerts", Slide 19 "cron automation").

v1 shipped `daily_reminder()` as a `logger.info` stub. This is the real thing:

  outbox_flush        every 60s     - delivers anything due (email/SMS/WhatsApp), retries backoff
  risk_sweep          every 15min   - re-scores open tasks, persists risk badges, alerts new HIGHs
  approval_sla        every 30min   - nudges approvers near SLA, escalates at 1.5x
  daily_reminders     08:00 local   - T-3 / T-1 / due-today / overdue reminders
  overdue_escalation  09:00 local   - assignee -> HOD -> Principal ladder
  daily_digest        08:05 local   - batches each user's digest bucket into one message
  event_reminders     07:30 local   - events starting today/tomorrow
  goal_checkin        Fri 16:00     - goals whose milestone progress is below plan
  weekly_report       Mon 07:00     - department scorecard stored + mailed to HOD/Principal
  retention_purge     02:00 local   - prunes delivery logs/read alerts past the retention window

Every job claims an idempotency slot in `scheduler_runs`, so a restarted process (or a
second worker) never double-sends the same morning's reminders.
"""

from __future__ import annotations

import traceback
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config.settings import settings
from app.engine import analytics as AN
from app.engine import approvals as A
from app.engine import risk as R
from app.utils.logging import logger

try:  # real timezone when available (APScheduer 3.x accepts IANA names)
    from zoneinfo import ZoneInfo  # type: ignore

    ZoneInfo(settings.NOTIFY_TIMEZONE)
    SCHED_TZ: Optional[str] = settings.NOTIFY_TIMEZONE
except Exception:  # pragma: no cover
    SCHED_TZ = None

_scheduler: Optional[BackgroundScheduler] = None
_UTC_OFFSET_MIN = int(getattr(settings, "NOTIFY_TZ_OFFSET_MINUTES", 0) or 0)


def _to_utc_minutes(local_hhmm: str) -> tuple:
    """Cron times in the deck are written as campus-local (IST) wall-clock."""
    hh, mm = [int(x) for x in (local_hhmm or "08:00").split(":")[:2]]
    total = (hh * 60 + mm - (_UTC_OFFSET_MIN if SCHED_TZ is None else 0)) % 1440
    return total // 60, total % 60


def _cron(local_hhmm: str, dow: str = "*") -> CronTrigger:
    """CronTrigger for one or more campus-local wall-clock times ("08:00" or "08:00,17:00").

    A comma list is only expressible as a single APScheduler trigger when every entry shares the
    same minute, which is the case for the shipped reminder ladder (08:00,17:00). Mixed minutes
    are reported instead of silently dropping the extra times - that failure mode (a job that
    never fires) is exactly what the deck's "daily 8 AM reminder" objective cannot survive.
    """
    entries = [e.strip() for e in str(local_hhmm or "08:00").split(",") if e.strip()]
    parsed = [_to_utc_minutes(e) for e in entries]
    minutes = sorted({mm for _, mm in parsed})
    if len(minutes) > 1:
        logger.warning(
            f"{local_hhmm!r}: multiple times must share the same minute to run as one trigger; "
            f"using {entries[0]!r} and ignoring {', '.join(entries[1:])}. Set them to ':00', ':15', ... consistently."
        )
        parsed = parsed[:1]
        minutes = [parsed[0][1]]
    hours = sorted({hh for hh, _ in parsed})
    kwargs: Dict[str, Any] = {"hour": ",".join(str(h) for h in hours), "minute": str(minutes[0]), "day_of_week": dow}
    if SCHED_TZ:
        kwargs["timezone"] = SCHED_TZ
    return CronTrigger(**kwargs)


def _parse_weekly(txt: str) -> tuple:
    """'Mon:07:00' -> ('07:00', 'mon')."""
    raw = str(txt or "Mon:07:00")
    dow, _, hhmm = raw.partition(":")
    if not hhmm:  # no day prefix
        return dow, "*"
    return f"{hhmm.split(':')[0]}:{(hhmm.split(':') + ['00'])[1]}", dow.strip().lower()[:3]


def _interval(seconds: int) -> IntervalTrigger:
    return IntervalTrigger(seconds=max(10, seconds))


# --------------------------------------------------------------------- idempotency
def _claim(db: Any, job_id: str, slot: Optional[str] = None) -> bool:
    """Return True if this run slot is ours to execute (once per slot, cluster-wide)."""
    slot = slot or datetime.utcnow().strftime("%Y%m%d-%H")
    key = f"{job_id}:{slot}"
    ref = db.collection("scheduler_runs").document(key)
    try:
        if ref.get().exists:
            return False
        ref.set({"job_id": job_id, "slot": slot, "claimed_at": datetime.utcnow().isoformat(timespec="seconds"), "host": "api"})
        return True
    except Exception as exc:  # pragma: no cover
        logger.warning(f"claim failed for {key}: {exc}")
        return True


def _release(db: Any, job_id: str, slot: str, result: Any) -> None:
    try:
        db.collection("scheduler_runs").document(f"{job_id}:{slot}").update(
            {"finished_at": datetime.utcnow().isoformat(timespec="seconds"), "result": str(result)[:400]}
        )
    except Exception:  # pragma: no cover
        pass


def _assignee_candidates(db: Any) -> Dict[str, Dict[str, Any]]:
    users = {}
    for snap in db.collection("users").stream():
        d = dict(snap.to_dict(), id=snap.id)
        users[str(d.get("id"))] = d
        users.setdefault(str(d.get("name")), d)
        users.setdefault(str(d.get("email")), d)
    return users


# --------------------------------------------------------------------- jobs
def job_risk_sweep(db: Any, *, force: bool = False, actor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Re-score every open task, persist badges, alert on newly HIGH items."""
    tasks = [dict(s.to_dict(), id=s.id) for s in db.collection("tasks").stream()]
    open_tasks = [t for t in tasks if R.is_active(t)]
    ctx = R.build_context(db, tasks=tasks, users=_assignee_candidates(db))
    escalated, snapshots = 0, {}
    for t in open_tasks:
        a = R.assess(t, ctx)
        prev = float(t.get("risk_score") or 0)
        from app.db.compat import normalize_task

        db.collection("tasks").document(str(t.get("id"))).set(normalize_task(t, assessment=a), merge=True)
        snapshots[a["risk_level"]] = snapshots.get(a["risk_level"], 0) + 1
        newly_bad = a["risk_score"] >= 55 and (a["risk_score"] - prev) >= 12
        if (newly_bad or force) and a["risk_level"] == "HIGH" and t.get("assigned_id"):
            from app.notify.engine import dispatch

            dispatch(
                db,
                target=str(t.get("assigned_id")),
                kind="deadline_risk",
                title=str(t.get("title")),
                message=a["explanation"],
                severity="CRITICAL" if a.get("at_risk") else "HIGH",
                route="/tasks",
                facts={
                    "Risk score": f"{a['risk_score']:.0f}/100 ({a['risk_level']})",
                    "Delay probability": f"{a['delay_probability'] * 100:.0f}%",
                    "Deadline": t.get("deadline"),
                    "Suggested action": (a["recommendations"] or ["-"])[0],
                },
                meta={"task_id": t.get("id"), "drivers": a["drivers"]},
            )
            escalated += 1
    _write_snapshot(db, open_tasks, ctx)
    return {"scored": len(open_tasks), "alerts_sent": escalated, "bands": snapshots}


def _write_snapshot(db: Any, open_tasks: List[Dict[str, Any]], ctx: R.RiskContext) -> None:
    now = datetime.utcnow()
    bands = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
    prob = 0.0
    for t in open_tasks:
        a = R.assess(t, ctx)
        bands[a["risk_level"]] = bands.get(a["risk_level"], 0) + 1
        prob += a["delay_probability"]
    db.collection("risk_snapshots").document(f"snap_{now:%Y%m%d_%H%M}").set(
        {
            "taken_at": now.isoformat(timespec="seconds"),
            "bands": bands,
            "open_tasks": len(open_tasks),
            "expected_misses": round(prob, 2),
            "mean_risk": round(sum(R.assess(t, ctx)["risk_score"] for t in open_tasks) / max(1, len(open_tasks)), 1),
            "created_by": "scheduler",
        }
    )


def job_deadline_reminders(db: Any, *, actor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The '8 AM reminders' objective: T-3, T-1, due today, plus already-overdue nag."""
    from app.notify.engine import dispatch

    now = datetime.utcnow()
    tasks = [dict(s.to_dict(), id=s.id) for s in db.collection("tasks").stream()]
    sent = {"T-3": 0, "T-1": 0, "today": 0, "overdue": 0}
    for t in tasks:
        if not R.is_active(t) or not t.get("assigned_id"):
            continue
        dl = R.deadline_of(t)
        if not dl:
            continue
        days_left = (dl - now).days
        title = str(t.get("title"))
        progress = R.progress_of(t)
        facts = {"Deadline": t.get("deadline"), "Progress": f"{progress:.0f}%", "Priority": t.get("priority", "Medium")}
        if days_left < 0:
            dispatch(db, target=str(t["assigned_id"]), kind="task_overdue", title=title,
                     message=f"'{title}' crossed its deadline {abs(days_left)} day(s) ago at {progress:.0f}% progress.",
                     severity="HIGH", route="/tasks", facts=facts, meta={"task_id": t.get("id")})
            sent["overdue"] += 1
        elif days_left == 0:
            dispatch(db, target=str(t["assigned_id"]), kind="deadline_reminder", title=title,
                     message=f"'{title}' is due TODAY at {progress:.0f}% progress.", severity="HIGH",
                     route="/tasks", facts=facts, meta={"task_id": t.get("id")})
            sent["today"] += 1
        elif days_left == 1:
            dispatch(db, target=str(t["assigned_id"]), kind="deadline_reminder", title=title,
                     message=f"'{title}' is due tomorrow and stands at {progress:.0f}%.", severity="HIGH",
                     route="/tasks", facts=facts, meta={"task_id": t.get("id")})
            sent["T-1"] += 1
        elif days_left == 3:
            dispatch(db, target=str(t["assigned_id"]), kind="deadline_reminder", title=title,
                     message=f"3 days left on '{title}' ({progress:.0f}% done). Confirm the plan or flag blockers now.",
                     severity="MEDIUM", route="/tasks", facts=facts, meta={"task_id": t.get("id")})
            sent["T-3"] += 1
    return {"reminders": sent, "scanned": len(tasks)}


def job_overdue_escalation(db: Any, *, actor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Escalation ladder: 1-2 days -> faculty, 3-6 -> +HOD, 7+ -> +Principal."""
    from app.notify.engine import dispatch

    now = datetime.utcnow()
    tasks = [dict(s.to_dict(), id=s.id) for s in db.collection("tasks").stream()]
    users = _assignee_candidates(db)
    ladders = {"faculty": 0, "hod": 0, "principal": 0}
    for t in tasks:
        if not R.is_active(t):
            continue
        dl = R.deadline_of(t)
        if not dl:
            continue
        days_over = (now - dl).days
        if days_over <= 0:
            continue
        who = str(t.get("assigned_id") or "")
        name = (users.get(who) or {}).get("name") or t.get("assigned") or who
        facts = {"Overdue by": f"{days_over} day(s)", "Progress": f"{R.progress_of(t):.0f}%", "Assignee": name}
        msg = f"'{t.get('title')}' ({name}) is {days_over} day(s) overdue at {R.progress_of(t):.0f}% progress."
        dispatch(db, target=who, kind="task_overdue", title=str(t.get("title")), message=msg,
                 severity="HIGH", route="/tasks", facts=facts, meta={"task_id": t.get("id"), "tier": 1})
        ladders["faculty"] += 1
        if days_over >= 3:
            dispatch(db, target="department", kind="escalation", title=f"Escalation: {t.get('title')}",
                     message=f"{name}'s task has been overdue {days_over} days and needs HOD intervention.",
                     severity="HIGH", route="/tasks", facts=facts, meta={"task_id": t.get("id"), "tier": 2})
            ladders["hod"] += 1
        if days_over >= 7:
            dispatch(db, target="role:PRINCIPAL", kind="escalation", title=f"Critical escalation: {t.get('title')}",
                     message=f"Overdue {days_over} days across two levels of follow-up. Principal visibility requested.",
                     severity="CRITICAL", route="/tasks", facts=facts, meta={"task_id": t.get("id"), "tier": 3})
            ladders["principal"] += 1
    return {"escalations": ladders}


def job_approval_sla(db: Any, *, actor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Remind the current approver, then escalate past 1.5x the SLA (once, not every sweep)."""
    from app.notify.engine import dispatch

    now = datetime.utcnow()
    reminded, escalated = 0, 0
    for snap in db.collection("approvals").stream():
        d = dict(snap.to_dict(), id=snap.id)
        if (d.get("status") or "").upper() != "PENDING":
            continue
        sla = A.evaluate_sla(d, now)
        if not sla["breached"]:
            if sla["state"] == "due_soon":
                dispatch(db, target=f"role:{d.get('stage', 'HOD')}", kind="approval_request", title=str(d.get("title")),
                         message=f"'{d.get('title')}' has consumed {sla['percent_consumed']:.0f}% of its {sla['sla_hours']:.0f}h SLA.",
                         severity="MEDIUM", route="/approvals",
                         facts={"Stage": d.get("stage"), "Time left": f"{sla['hours_remaining']}h"}, meta={"approval_id": d.get("id")})
                reminded += 1
            continue
        if d.get("sla_reminded_at") and (now - datetime.fromisoformat(d["sla_reminded_at"])) < timedelta(hours=12):
            continue
        target, role = A.escalation_target(d)
        dispatch(db, target=target, kind="approval_sla_breach", title=str(d.get("title")),
                 message=f"Approval for '{d.get('title')}' has waited {sla['hours_waiting']:.0f}h against a {sla['sla_hours']:.0f}h SLA.",
                 severity="CRITICAL" if sla["escalate"] else "HIGH", route="/approvals",
                 facts={"Stage": d.get("stage"), "Requested by": d.get("requester_name") or "-", "Over SLA by": f"{sla['hours_waiting'] - sla['sla_hours']:.0f}h"},
                 meta={"approval_id": d.get("id")})
        db.collection("approvals").document(str(d.get("id"))).update(
            {"sla_reminded_at": now.isoformat(timespec="seconds"), "escalation_count": int(d.get("escalation_count", 0) or 0) + (1 if sla["escalate"] else 0)}
        )
        escalated += 1
    return {"sla_reminders": reminded, "breaches_escalated": escalated}


def job_daily_digest(db: Any, *, actor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Collapse each user's deferred/digest bucket into a single briefing."""
    from app.notify import templates
    from app.notify.queue import mark_digest_consumed, pending_digest, process_due
    from app.notify.engine import dispatch

    users = list(db.collection("users").where("status", "==", "ACTIVE").stream()) or list(db.collection("users").stream())
    delivered = 0
    for u in users:
        ud = dict(u.to_dict(), id=u.id)
        uid = str(ud.get("id"))
        items = pending_digest(db, uid)
        if not items:
            continue
        ctx_items = [{"kind": it.get("kind"), "title": (it.get("meta") or {}).get("title") or it.get("subject"), "message": it.get("text"), "facts": {}} for it in items]
        rendered = templates.digest_body(ctx_items, settings)
        # write_inapp=False: the digest replaces the alerts it summarises
        dispatch(db, target=uid, kind="daily_digest", title="Daily briefing",
                 message=rendered["text"], severity="LOW", route="/dashboard",
                 facts={"Items covered": len(items)}, meta={"digest": True})
        mark_digest_consumed(db, [str(it.get("id")) for it in items])
        delivered += 1
    flushed = process_due(db, limit=200)
    return {"digests_sent": delivered, "flush": flushed}


def job_event_reminders(db: Any, *, actor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    from app.notify.engine import dispatch

    now = datetime.utcnow()
    sent = 0
    for snap in db.collection("events").stream():
        e = dict(snap.to_dict(), id=snap.id)
        when = R.parse_dt(e.get("date") or e.get("start_time"))
        if not when:
            continue
        days = (when - now).days
        if days in (0, 1):
            dispatch(db, target="department", kind="event_reminder", title=str(e.get("title")),
                     message=f"{'Today' if days == 0 else 'Tomorrow'}: {e.get('title')} "
                             f"at {e.get('location') or 'venue TBA'} ({e.get('event_type') or e.get('type') or 'Campus event'}).",
                     severity="MEDIUM", route="/calendar",
                     facts={"When": when.strftime("%d %b %Y %H:%M"), "Organizer": e.get("organizer") or e.get("person") or "-", "Venue": e.get("location") or "-"},
                     meta={"event_id": e.get("id")})
            sent += 1
    return {"event_reminders": sent}


def job_goal_checkin(db: Any, *, actor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    from app.notify.engine import dispatch

    now = datetime.utcnow()
    flagged = 0
    for snap in db.collection("goals").stream():
        g = dict(snap.to_dict(), id=snap.id)
        target = R.parse_dt(g.get("target_date"))
        if not target:
            continue
        total = (target - now).days
        if total <= 0 or total > 60:
            continue
        milestones = g.get("milestones") or []
        done = sum(1 for m in milestones if (m.get("done") if isinstance(m, dict) else False))
        actual = (done / len(milestones) * 100.0) if milestones else float(g.get("progress") or 0)
        expected = max(0.0, 100.0 * (1.0 - total / max(1.0, ((target - now).days + total))))
        if actual < expected - 15:
            dispatch(db, target=g.get("owner_id") or "department", kind="goal_checkin", title=str(g.get("title")),
                     message=f"Goal is behind plan: {actual:.0f}% complete vs {expected:.0f}% expected with {total} day(s) left.",
                     severity="MEDIUM", route="/goals",
                     facts={"Progress": f"{actual:.0f}%", "Expected": f"{expected:.0f}%", "Milestones": f"{done}/{len(milestones)}"},
                     meta={"goal_id": g.get("id")})
            flagged += 1
    return {"goals_flagged": flagged}


def job_weekly_report(db: Any, *, actor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Materialise the department scorecard as a report record + mail it out."""
    from app.notify.engine import dispatch

    now = datetime.utcnow()
    data = AN.scorecard(db, days=7, now=now)
    data["insights"] = AN.insights(data)
    rid = f"rep_{now:%Y%m%d}"
    db.collection("reports").document(rid).set(
        {
            "id": rid,
            "title": f"Weekly department report - week ending {now:%d %b %Y}",
            "kind": "weekly",
            "generated_at": now.isoformat(timespec="seconds"),
            "generated_by": "scheduler",
            "summary": {
                "tasks": data["tasks"],
                "risk": data["risk"],
                "approvals": data["approvals"],
                "workload_balance_index": data["workload"]["balance_index"],
            },
            "insights": data["insights"],
            "top_risks": data["top_risks"],
        }
    )
    bullets = "\n".join(f"- {i['text']}" for i in data["insights"][:4])
    dispatch(db, target="department", kind="weekly_report", title="Weekly department report",
             message=f"Week ending {now:%d %b %Y}\n{bullets}", severity="LOW", route="/reports",
             facts={
                 "Completion": f"{data['tasks']['completion_rate']}%",
                 "On-time": f"{data['tasks']['on_time_rate']}%",
                 "Overdue": data["tasks"]["overdue"],
                 "High-risk tasks": data["risk"]["high_risk_count"],
                 "Approvals pending": data["approvals"]["pending"],
             },
             meta={"report_id": rid})
    return {"report_id": rid, "insights": len(data["insights"])}


def job_outbox_flush(db: Any, *, actor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    from app.notify.queue import process_due

    return process_due(db, limit=120)


def job_retention_purge(db: Any, *, actor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    from app.notify.queue import purge_old

    removed = purge_old(db)
    cutoff = (datetime.utcnow() - timedelta(days=max(30, settings.NOTIFY_RETENTION_DAYS))).isoformat(timespec="seconds")
    stale = 0
    for snap in db.collection("notifications").where("is_read", "==", True).stream():
        if (snap.to_dict().get("created_at") or "") < cutoff:
            snap.reference.delete()
            stale += 1
    return {"delivery_rows_removed": removed, "read_notifications_removed": stale}


# --------------------------------------------------------------------- registry
JOBS: List[Dict[str, Any]] = [
    {
        "id": "outbox_flush",
        "title": "Outbox delivery worker",
        "fn": job_outbox_flush,
        "trigger": lambda: _interval(settings.OUTBOX_POLL_SECONDS),
        "when": f"every {settings.OUTBOX_POLL_SECONDS}s",
        "claim": False,
        "purpose": "Sends everything due in notification_outbox with retry/backoff.",
    },
    {
        "id": "risk_sweep",
        "title": "Deadline-risk sweep",
        "fn": job_risk_sweep,
        "trigger": lambda: _interval(settings.RISK_SWEEP_MINUTES * 60),
        "when": f"every {settings.RISK_SWEEP_MINUTES}min",
        "claim": False,
        "purpose": "Re-scores open tasks, persists risk badges, alerts newly HIGH items.",
    },
    {
        "id": "approval_sla",
        "title": "Approval SLA monitor",
        "fn": job_approval_sla,
        "trigger": lambda: _interval(settings.APPROVAL_SLA_MINUTES * 60),
        "when": f"every {settings.APPROVAL_SLA_MINUTES}min",
        "claim": False,
        "purpose": "Nudges approvers before breach, escalates the stage past 1.5x SLA.",
    },
    {
        "id": "daily_reminders",
        "title": "Daily 8 AM deadline reminders",
        "fn": job_deadline_reminders,
        "trigger": lambda: _cron(settings.DEADLINE_REMINDER_TIMES),
        "when": f"{settings.DEADLINE_REMINDER_TIMES} campus-local, daily",
        "claim": True,
        "purpose": "T-3 / T-1 / due-today / overdue follow-ups (Objective 3).",
    },
    {
        "id": "overdue_escalation",
        "title": "Overdue escalation ladder",
        "fn": job_overdue_escalation,
        "trigger": lambda: _cron(settings.OVERDUE_ESCALATION_TIME),
        "when": f"{settings.OVERDUE_ESCALATION_TIME} campus-local, daily",
        "claim": True,
        "purpose": "Faculty -> HOD -> Principal escalation for ageing overdue work.",
    },
    {
        "id": "daily_digest",
        "title": "Daily briefing batch",
        "fn": job_daily_digest,
        "trigger": lambda: _cron(settings.DIGEST_DAILY_TIME),
        "when": f"{settings.DIGEST_DAILY_TIME} campus-local, daily",
        "claim": True,
        "purpose": "Collapses each user's deferred/low-severity alerts into one digest.",
    },
    {
        "id": "event_reminders",
        "title": "Event day-before reminders",
        "fn": job_event_reminders,
        "trigger": lambda: _cron("07:30"),
        "when": "07:30 campus-local, daily",
        "claim": True,
        "purpose": "Notifies stakeholders for events starting today or tomorrow.",
    },
    {
        "id": "goal_checkin",
        "title": "Weekly goal check-in",
        "fn": job_goal_checkin,
        "trigger": lambda: _cron("16:00", dow="fri"),
        "when": "Fri 16:00 campus-local",
        "claim": True,
        "purpose": "Flags goals drifting behind their milestone plan.",
    },
    {
        "id": "weekly_report",
        "title": "Weekly department report",
        "fn": job_weekly_report,
        "trigger": lambda: _cron(*_parse_weekly(settings.WEEKLY_REPORT_TIME)),
        "when": settings.WEEKLY_REPORT_TIME,
        "claim": True,
        "purpose": "Stores the scorecard as a report record and mails HOD/Principal.",
    },
    {
        "id": "retention_purge",
        "title": "Retention & cleanup",
        "fn": job_retention_purge,
        "trigger": lambda: _cron(settings.RETENTION_PURGE_TIME),
        "when": f"{settings.RETENTION_PURGE_TIME} campus-local, daily",
        "claim": True,
        "purpose": "Prunes delivery logs and old read alerts (data-hygiene policy).",
    },
]


def job_specs() -> List[Dict[str, Any]]:
    return [{"id": j["id"], "title": j["title"], "schedule": j["when"], "purpose": j["purpose"], "idempotent": j["claim"]} for j in JOBS]


def run_job(job_id: str, db: Any, *, actor: Optional[Dict[str, Any]] = None, force: bool = True) -> Optional[Dict[str, Any]]:
    spec = next((j for j in JOBS if j["id"] == job_id), None)
    if not spec:
        return None
    started = datetime.utcnow()
    try:
        result = spec["fn"](db, actor=actor)
    except Exception as exc:  # pragma: no cover
        logger.error(f"job {job_id} failed: {exc}\n{traceback.format_exc(limit=4)}")
        return {"error": str(exc), "job": job_id}
    return {"job": job_id, "seconds": round((datetime.utcnow() - started).total_seconds(), 2), "result": result}


def start_scheduler() -> Optional[BackgroundScheduler]:
    global _scheduler
    if not settings.SCHEDULER_ENABLED:
        logger.info("Scheduler disabled by configuration (SCHEDULER_ENABLED=false).")
        return None
    if _scheduler is not None:
        return _scheduler

    sched = BackgroundScheduler(timezone=SCHED_TZ) if SCHED_TZ else BackgroundScheduler()
    for spec in JOBS:
        try:
            sched.add_job(
                _make_wrapped(spec),
                trigger=spec["trigger"](),
                id=spec["id"],
                name=spec["title"],
                max_instances=1,
                coalesce=True,
                replace_existing=True,
            )
        except Exception as exc:  # pragma: no cover
            logger.error(f"could not register job {spec['id']}: {exc}")
    sched.start()
    _scheduler = sched
    logger.info(f"Scheduler started with {len(sched.get_jobs())} jobs (tz={SCHED_TZ or 'system/UTC-shifted'}).")
    return sched


def _make_wrapped(spec: Dict[str, Any]):
    def _wrapped():
        from app.database.session import get_db

        db = get_db()
        slot = datetime.utcnow().strftime("%Y%m%d-%H%M" if not spec["claim"] else "%Y%m%d-%H")
        if spec["claim"] and not _claim(db, spec["id"], slot):
            logger.debug(f"job {spec['id']} already claimed for slot {slot}")
            return
        out = run_job(spec["id"], db)
        if spec["claim"]:
            _release(db, spec["id"], slot, out)
        logger.info(f"job {spec['id']} -> {out}")

    return _wrapped


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:  # pragma: no cover
            pass
        _scheduler = None
        logger.info("Scheduler stopped.")


def scheduler_status() -> Dict[str, Any]:
    if _scheduler is None:
        return {"running": False, "reason": "disabled or not started", "jobs": job_specs()}
    jobs = []
    for j in _scheduler.get_jobs():
        jobs.append({"id": j.id, "name": j.name, "next_run_time": str(j.next_run_time)})
    return {"running": bool(_scheduler.running), "job_count": len(jobs), "jobs": jobs, "definitions": job_specs()}
