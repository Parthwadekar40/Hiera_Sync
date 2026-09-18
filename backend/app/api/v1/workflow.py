"""Approvals v2 - the multi-stage workflow engine (Slide 15 + Slide 19).

Flow implemented exactly as specified:
  1. Faculty/Staff raises a request (with evidence/attachment reference)
  2. HOD evaluates -> approve to stage 2, or reject with a mandatory comment
  3. Principal reviews the HOD-approved request -> final approval or rejection
  4. On final approval the system auto-creates the task and notifies stakeholders

Additions beyond the deck (kept opt-in and documented): per-kind SLA timers with
escalation, delegation for out-of-office approvers, resubmission after rejection,
and a hash-chained audit trail whose integrity can be verified on demand.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.auth.rbac import can, matrix_table
from app.auth.permissions import get_current_active_user
from app.database.session import get_db
from app.db.compat import normalize_approval
from app.engine import approvals as A
from app.models.models import RoleEnum, User
from app.notify.engine import dispatch
from app.utils.logging import logger

router = APIRouter()


class RequestCreate(BaseModel):
    title: str
    kind: str = "generic"
    description: str = ""
    amount: Optional[float] = None
    priority: str = "Medium"
    evidence: Dict[str, Any] = Field(default_factory=dict)
    attachment_ids: List[str] = Field(default_factory=list)
    department_id: Optional[str] = None
    expected_completion: Optional[str] = None
    goal_id: Optional[str] = None


class Decision(BaseModel):
    decision: str  # APPROVE | REJECT
    note: str = ""


class Resubmit(BaseModel):
    note: str = ""
    evidence: Dict[str, Any] = Field(default_factory=dict)


class Delegate(BaseModel):
    to: str  # user id or email
    note: str = ""


def _now() -> datetime:
    return datetime.utcnow()


def _actor(user: User) -> Dict[str, Any]:
    return {"id": user.id, "name": user.name, "role": user.role.value}


def _approver_for(db: Any, stage: str, department_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """Find the concrete approver user for a stage (department HOD first, then role)."""
    role_needed = "HOD" if stage.upper() == "HOD" else "PRINCIPAL"
    users = [dict(s.to_dict(), id=s.id) for s in db.collection("users").stream()]
    if stage.upper() == "HOD" and department_id:
        dept = db.collection("departments").document(department_id).get()
        if dept.exists and dept.to_dict().get("hod_id"):
            hod_id = dept.to_dict()["hod_id"]
            for u in users:
                if u.get("id") == hod_id:
                    return u
    for u in users:
        if str(u.get("role", "")).upper() == role_needed and str(u.get("status", "ACTIVE")).upper() == "ACTIVE":
            return u
    return None


@router.get("/policies")
def policies(current_user: User = Depends(get_current_active_user)):
    """The routing table a reviewer asked for: which kind needs whose signature, and by when."""
    return {
        "stages": ["HOD", "PRINCIPAL"],
        "policies": [
            A.policy_for(kind, None).as_dict() for kind in sorted(A.POLICIES)
        ],
        "amount_escalation": {"purchase": {"PRINCIPAL": 50000}, "note": "purchases above the threshold gain a Principal stage"},
        "terminal_states": sorted(A.TERMINAL),
    }


@router.get("/rbac")
def rbac_matrix(current_user: User = Depends(get_current_active_user)):
    return {"roles": len(matrix_table()), "matrix": matrix_table()}


@router.get("/queue")
def my_queue(db: Any = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """The approver's inbox, ordered by SLA pressure."""
    queue = A.queue_for(db, {"id": current_user.id, "role": current_user.role.value}, now=_now())
    return {
        "role": current_user.role.value,
        "counts": queue["counts"],
        "items": [
            {
                "id": a.get("id"),
                "title": a.get("title"),
                "kind": a.get("kind"),
                "requester_name": a.get("requester_name") or a.get("requested"),
                "priority": a.get("priority"),
                "stage": a.get("stage"),
                "sla": a.get("sla"),
                "created_at": a.get("created_at"),
                "action_reason": a.get("action_reason"),
            }
            for a in queue["pending"]
        ],
    }


@router.get("/")
def list_requests(
    status_filter: Optional[str] = Query(None, alias="status"),
    kind: Optional[str] = None,
    mine: bool = False,
    limit: int = Query(200, ge=1, le=1000),
    db: Any = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    rows: List[Dict[str, Any]] = []
    scope_is_limited = not can(current_user.role.value, "approve_hod")
    for snap in db.collection("approvals").stream():
        d = normalize_approval({**snap.to_dict(), "id": snap.id})
        if scope_is_limited and d.get("requester_id") != current_user.id:
            continue
        if mine and d.get("requester_id") != current_user.id:
            continue
        if status_filter and d.get("status") != status_filter.upper():
            continue
        if kind and (d.get("kind") or "").lower() != kind.lower():
            continue
        d["sla"] = A.evaluate_sla(d, _now())
        eligible, reason = A.can_act(d, current_user.role.value, current_user.id)
        d["can_act"] = eligible
        d["action_hint"] = reason
        rows.append(d)
    rows.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return {"count": len(rows), "items": rows[:limit]}


@router.post("/")
def create_request(
    payload: RequestCreate,
    db: Any = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Step 1 of the deck's workflow: raise the request, route it to the HOD stage."""
    rid = f"apr_{uuid.uuid4().hex[:12]}"
    dept_id = payload.department_id or current_user.department_id
    doc = A.new_request(
        title=payload.title,
        kind=payload.kind,
        requester_id=current_user.id,
        requester_name=current_user.name,
        department_id=dept_id,
        description=payload.description,
        amount=payload.amount,
        evidence={**payload.evidence, "attachments": payload.attachment_ids, "goal_id": payload.goal_id},
        priority=payload.priority,
        hod_id=(_approver_for(db, "HOD", dept_id) or {}).get("id"),
        principal_id=(_approver_for(db, "PRINCIPAL", dept_id) or {}).get("id"),
        now=_now(),
    )
    db.collection("approvals").document(rid).set({**doc, "requested": current_user.name, "assigned": current_user.name})

    hod = _approver_for(db, doc["stage"], dept_id)
    target = (hod or {}).get("id") or "department"
    facts = {
        "Type": doc["kind"],
        "Stage": doc["stage"],
        "SLA": f"{doc['sla_hours']:.0f}h",
        "Priority": doc["priority"],
    }
    if doc.get("amount"):
        facts["Amount"] = f"₹{doc['amount']:,.0f}"
    summary = dispatch(
        db,
        target=target,
        kind="approval_request",
        title=doc["title"],
        message=f"{current_user.name} submitted '{doc['title']}' for {doc['stage']} approval.",
        severity="HIGH",
        route="/approvals",
        facts=facts,
        meta={"approval_id": rid, "attachments": payload.attachment_ids},
        actor=_actor(current_user),
    )
    logger.info(f"Approval {rid} raised -> stage {doc['stage']} ({summary['queued']})")
    return {"id": rid, **doc, "delivery": summary}


@router.get("/{approval_id}")
def get_request(approval_id: str, db: Any = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    snap = db.collection("approvals").document(approval_id).get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Request not found")
    doc = normalize_approval({**snap.to_dict(), "id": approval_id})
    if doc.get("requester_id") != current_user.id and not can(current_user.role.value, "approve_hod"):
        raise HTTPException(status_code=403, detail="Not your request")
    doc["sla"] = A.evaluate_sla(doc, _now())
    eligible, reason = A.can_act(doc, current_user.role.value, current_user.id)
    doc["can_act"], doc["action_hint"] = eligible, reason
    ok, problems = A.verify_chain(doc)
    doc["audit_integrity"] = {"valid": ok, "problems": problems}
    return doc


@router.post("/{approval_id}/decide")
def decide(
    approval_id: str,
    payload: Decision,
    db: Any = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Steps 2-4: advance, finalize, and auto-instantiate the task on approval."""
    snap = db.collection("approvals").document(approval_id)
    raw = snap.get()
    if not raw.exists:
        raise HTTPException(status_code=404, detail="Request not found")
    doc = dict(raw.to_dict())
    doc.setdefault("id", approval_id)

    delegate_of = None
    if doc.get("delegated_to") and doc["delegated_to"] != current_user.id:
        raise HTTPException(status_code=403, detail="This request was delegated to another approver")
    if doc.get("delegated_to") == current_user.id:
        delegate_of = doc.get("delegated_from")

    try:
        updated = A.advance(
            doc,
            decision=payload.decision,
            actor_id=current_user.id,
            actor_role=current_user.role.value,
            actor_name=current_user.name,
            note=payload.note,
            delegate_of=delegate_of,
            now=_now(),
        )
    except A.ApprovalError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc), "code": exc.code})

    stage_done = (doc.get("stage") or "HOD").upper()
    if stage_done == "HOD":
        updated["hod_comment"] = payload.note or ("Approved by HOD" if payload.decision.upper() == "APPROVE" else payload.note)
    else:
        updated["principal_comment"] = payload.note or ("Approved by Principal" if payload.decision.upper() == "APPROVE" else payload.note)
    db.collection("approvals").document(approval_id).set(updated)

    requester = updated.get("requester_id")
    created_task = None
    if updated["status"] == "APPROVED":
        # ---- Slide 15 step 4: final approval instantiates the task + notifies stakeholders
        created_task = _instantiate_task(db, updated, current_user)
        dispatch(
            db,
            target=requester or "department",
            kind="approval_approved",
            title=updated["title"],
            message="Your request was approved at every stage. A delivery task has been created and the stakeholders notified.",
            severity="LOW",
            route="/tasks",
            facts={"Reference": approval_id, "Stages cleared": ", ".join(updated.get("stages", [])), "Note": updated.get("decision_note") or "-"},
            meta={"approval_id": approval_id, "task_id": (created_task or {}).get("id")},
        )
        dispatch(
            db,
            target="department",
            kind="ai_insight",
            title=f"Approved: {updated['title']}",
            message=f"{current_user.name} cleared '{updated['title']}'. Task '{(created_task or {}).get('title', '')}' is now tracked.",
            severity="LOW",
            route="/tasks",
            meta={"approval_id": approval_id},
        )
    elif updated["status"] == "REJECTED":
        dispatch(
            db,
            target=requester or "department",
            kind="approval_rejected",
            title=updated["title"],
            message=f"Rejected at {stage_done}. Reason: {payload.note or 'not supplied'}. You may correct and resubmit.",
            severity="MEDIUM",
            route="/approvals",
            facts={"Stage": stage_done, "Reviewed by": current_user.name},
            meta={"approval_id": approval_id},
        )
    else:
        nxt = _approver_for(db, updated["stage"], updated.get("department_id"))
        dispatch(
            db,
            target=(nxt or {}).get("id") or "department",
            kind="approval_request",
            title=updated["title"],
            message=f"HOD cleared '{updated['title']}' with the note: {payload.note or '-'} - awaiting your final decision.",
            severity="HIGH",
            route="/approvals",
            facts={"Stage": updated["stage"], "SLA": f"{updated['sla_hours']:.0f}h"},
            meta={"approval_id": approval_id, "advanced_from": stage_done},
            actor=_actor(current_user),
        )

    return {"id": approval_id, **normalize_approval(updated), "created_task": created_task}


def _instantiate_task(db: Any, approval: Dict[str, Any], actor: User) -> Dict[str, Any]:
    task_id = f"tsk_{uuid.uuid4().hex[:12]}"
    deadline = approval.get("expected_completion") or (
        (R_parse(approval.get("evidence", {}).get("expected_completion")) or (_now() + timedelta(days=14))).date().isoformat()
    )
    requester = approval.get("requester_id")
    requester_name = approval.get("requester_name") or approval.get("requested") or actor.name
    assignee_name = approval.get("assigned") or requester_name
    db.collection("tasks").document(task_id).set(
        {
            "id": task_id,
            "title": f"Execute: {approval['title']}",
            "description": approval.get("description", ""),
            "assigned": assignee_name,
            "assigned_id": requester,
            "assignee_id": requester,
            "creator_id": actor.id,
            "department_id": approval.get("department_id"),
            "deadline": deadline,
            "priority": approval.get("priority", "Medium"),
            "status": "Pending",
            "progress": "0%",
            "progress_pct": 0.0,
            "category": "Approval",
            "goal_id": (approval.get("evidence") or {}).get("goal_id"),
            "subtasks": [],
            "require_approval": True,
            "source": "approval_workflow",
            "approval_id": approval.get("id"),
            "created_at": _now().isoformat(timespec="seconds"),
            "updated_at": _now().isoformat(timespec="seconds"),
            "created_from_approval": approval.get("id"),
        }
    )
    db.collection("activity_logs").document(f"act_{uuid.uuid4().hex[:10]}").set(
        {
            "user_id": actor.id,
            "user_name": actor.name,
            "action": f"Task auto-created from approved request {approval.get('id')}",
            "category": "approval",
            "details": approval.get("title", ""),
            "timestamp": _now().isoformat(timespec="seconds"),
        }
    )
    if requester:
        dispatch(
            db,
            target=requester,
            kind="task_assigned",
            title=f"Execute: {approval['title']}",
            message=f"Auto-created from approved request. Deliver by {deadline}.",
            severity="MEDIUM",
            route="/tasks",
            facts={"Deadline": deadline, "Priority": approval.get("priority", "Medium"), "Requires approval": "Yes"},
            meta={"task_id": task_id, "approval_id": approval.get("id")},
        )
    return {"id": task_id, "title": f"Execute: {approval['title']}", "deadline": deadline}


def R_parse(value: Any):
    from app.db.store import parse_dt

    return parse_dt(value)


@router.post("/{approval_id}/resubmit")
def resubmit(approval_id: str, payload: Resubmit, db: Any = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    snap = db.collection("approvals").document(approval_id)
    raw = snap.get()
    if not raw.exists:
        raise HTTPException(status_code=404, detail="Request not found")
    doc = dict(raw.to_dict())
    if doc.get("requester_id") != current_user.id and not can(current_user.role.value, "assign_tasks"):
        raise HTTPException(status_code=403, detail="Only the requester may resubmit")
    try:
        updated = A.resubmit(doc, actor_id=current_user.id, actor_name=current_user.name, note=payload.note, evidence=payload.evidence, now=_now())
    except A.ApprovalError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc), "code": exc.code})
    snap.set(updated)
    hod = _approver_for(db, "HOD", updated.get("department_id"))
    dispatch(
        db,
        target=(hod or {}).get("id") or "department",
        kind="approval_request",
        title=updated["title"],
        message=f"{current_user.name} revised and resubmitted the request (attempt {updated['resubmissions'] + 1}).",
        severity="HIGH",
        route="/approvals",
        facts={"Revision note": payload.note or "-", "Attempt": updated["resubmissions"] + 1},
        meta={"approval_id": approval_id},
    )
    return {"id": approval_id, **updated}


@router.post("/{approval_id}/cancel")
def cancel(approval_id: str, note: str = Body("", embed=True), db: Any = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    snap = db.collection("approvals").document(approval_id)
    raw = snap.get()
    if not raw.exists:
        raise HTTPException(status_code=404, detail="Request not found")
    doc = dict(raw.to_dict())
    if doc.get("requester_id") != current_user.id and not can(current_user.role.value, "manage_system"):
        raise HTTPException(status_code=403, detail="Only the requester or an administrator may cancel")
    try:
        updated = A.cancel(doc, actor_id=current_user.id, actor_name=current_user.name, note=note, now=_now())
    except A.ApprovalError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc), "code": exc.code})
    snap.set(updated)
    return {"id": approval_id, **updated}


@router.post("/{approval_id}/delegate")
def delegate(approval_id: str, payload: Delegate, db: Any = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Out-of-office routing: hand the pending stage to a substitute approver."""
    snap = db.collection("approvals").document(approval_id)
    raw = snap.get()
    if not raw.exists:
        raise HTTPException(status_code=404, detail="Request not found")
    doc = dict(raw.to_dict())
    if not can(current_user.role.value, "approve_hod"):
        raise HTTPException(status_code=403, detail="Current approver only")
    target_user = None
    for u in db.collection("users").stream():
        ud = dict(u.to_dict(), id=u.id)
        if payload.to in (ud.get("id"), ud.get("email")):
            target_user = ud
            break
    if not target_user:
        raise HTTPException(status_code=404, detail="Delegate user not found (pass user id or email)")
    updated = A.delegate(doc, from_id=current_user.id, to_id=target_user["id"], to_name=target_user.get("name", ""), note=payload.note, now=_now())
    snap.set(updated)
    dispatch(
        db,
        target=target_user["id"],
        kind="approval_request",
        title=updated["title"],
        message=f"{current_user.name} delegated '{updated['title']}' to you while they are away.",
        severity="HIGH",
        route="/approvals",
        facts={"Stage": updated.get("stage"), "Note": payload.note or "-"},
        meta={"approval_id": approval_id, "delegated_from": current_user.id},
    )
    return {"id": approval_id, **updated}


@router.get("/{approval_id}/audit")
def audit(approval_id: str, db: Any = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    snap = db.collection("approvals").document(approval_id).get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Request not found")
    doc = snap.to_dict()
    ok, problems = A.verify_chain(doc)
    return {"approval_id": approval_id, "valid": ok, "problems": problems, "entries": doc.get("audit", [])}


@router.post("/verify")
def verify_all(db: Any = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Integrity sweep over every decision record (tamper evidence)."""
    checked, broken = 0, []
    for snap in db.collection("approvals").stream():
        doc = dict(snap.to_dict(), id=snap.id)
        ok, problems = A.verify_chain(doc)
        checked += 1
        if not ok:
            broken.append({"id": snap.id, "problems": problems})
    return {"checked": checked, "valid": checked - len(broken), "compromised": broken}


@router.get("/stats/funnel")
def funnel(db: Any = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Approval latency analytics - the 'days to hours' claim from Slide 20, measured."""
    now = _now()
    buckets = {"PENDING": 0, "APPROVED": 0, "REJECTED": 0, "CANCELLED": 0}
    hours_to_first: List[float] = []
    hours_total: List[float] = []
    breached = 0
    escalations = 0
    by_kind: Dict[str, int] = {}
    for snap in db.collection("approvals").stream():
        d = dict(snap.to_dict(), id=snap.id)
        status = (d.get("status") or "PENDING").upper()
        buckets[status] = buckets.get(status, 0) + 1
        by_kind[d.get("kind", "generic")] = by_kind.get(d.get("kind", "generic"), 0) + 1
        sla = A.evaluate_sla(d, now)
        breached += 1 if sla["breached"] and status == "PENDING" else 0
        escalations += int(d.get("escalation_count", 0) or 0)
        created = _parse(d.get("created_at"))
        decided = _parse(d.get("decided_at"))
        if created and decided:
            hours_total.append((decided - created).total_seconds() / 3600.0)
        first = d.get("audit", [{}])
        if created and len(first) > 1:
            acted = _parse(first[1].get("at")) if isinstance(first[1], dict) else None
            if acted:
                hours_to_first.append((acted - created).total_seconds() / 3600.0)
    return {
        "buckets": buckets,
        "pending_breaching_sla": breached,
        "escalation_events": escalations,
        "median_hours_to_decision": _median(hours_total),
        "median_hours_to_first_response": _median(hours_to_first),
        "by_kind": by_kind,
        "baseline_note": "Manual register baseline is 48-120h (Slide 4: 'requests stall for days')",
    }


def _parse(v: Any):
    from app.db.store import parse_dt

    return parse_dt(v)


def _median(vals: List[float]) -> Optional[float]:
    if not vals:
        return None
    vals = sorted(vals)
    mid = len(vals) // 2
    out = vals[mid] if len(vals) % 2 else (vals[mid - 1] + vals[mid]) / 2.0
    return round(out, 2)
