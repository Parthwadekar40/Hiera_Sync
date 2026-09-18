"""Multi-stage approval engine: routing, SLA, delegation, escalation, tamper-evidence.

Business rules live here (not in the routers) so the same state machine serves the HTTP
API, the scheduler's SLA sweeps and the test-suite.

Audit integrity
---------------
Every decision appends to `doc["audit"]` with `hash = sha256(prev_hash + canonical_json(entry))`.
Any edit or deletion of a historical decision therefore breaks the chain, and
`verify_chain()` detects it - this is what makes the platform defensible for audit /
NAAC-style reviews where "who approved this and when" must not be deniable.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

APPROVER_ROLES = {"HOD": "HOD", "PRINCIPAL": "PRINCIPAL", "ADMIN": "PRINCIPAL", "HOD_OF_RECORD": "HOD"}

# kind -> workflow policy. Stages run in order; amount thresholds can add a stage.
POLICIES: Dict[str, Dict[str, Any]] = {
    "leave": {"stages": ["HOD"], "sla_hours": 48, "requires_note_on_reject": True, "evidence": ["leave_type", "from_date", "to_date"]},
    "no_objection": {"stages": ["HOD"], "sla_hours": 24, "requires_note_on_reject": True, "evidence": ["purpose"]},
    "event": {"stages": ["HOD", "PRINCIPAL"], "sla_hours": 72, "requires_note_on_reject": True, "evidence": ["venue", "date", "expected_attendees"]},
    "purchase": {"stages": ["HOD"], "sla_hours": 48, "amount_stage": {"PRINCIPAL": 50000}, "requires_note_on_reject": True, "evidence": ["item", "quantity", "vendor_quote"]},
    "budget": {"stages": ["HOD", "PRINCIPAL"], "sla_hours": 72, "requires_note_on_reject": True, "evidence": ["head", "amount", "justification"]},
    "outcome_approval": {"stages": ["HOD"], "sla_hours": 24, "requires_note_on_reject": True, "evidence": ["deliverable"]},
    "deadline_change": {"stages": ["HOD"], "sla_hours": 24, "requires_note_on_reject": True, "evidence": ["old_deadline", "new_deadline", "reason"]},
    "joining": {"stages": ["HOD", "PRINCIPAL"], "sla_hours": 120, "requires_note_on_reject": True, "evidence": ["department"]},
    "generic": {"stages": ["HOD"], "sla_hours": 48, "requires_note_on_reject": True, "evidence": []},
}

TERMINAL = {"APPROVED", "REJECTED", "CANCELLED", "WITHDRAWN"}


class ApprovalError(ValueError):
    def __init__(self, message: str, code: str = "invalid_transition"):
        super().__init__(message)
        self.code = code


@dataclass
class Policy:
    stages: List[str]
    sla_hours: float
    requires_note_on_reject: bool
    evidence: List[str]
    key: str = "generic"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.key,
            "stages": self.stages,
            "sla_hours": self.sla_hours,
            "requires_note_on_reject": self.requires_note_on_reject,
            "required_evidence": self.evidence,
        }


def policy_for(kind: str, amount: Optional[float] = None) -> Policy:
    raw = POLICIES.get((kind or "generic").lower(), POLICIES["generic"])
    stages = list(raw["stages"])
    if amount is not None and "amount_stage" in raw:
        for role, threshold in raw["amount_stage"].items():
            if float(amount) >= float(threshold) and role not in stages:
                stages.append(role)
    return Policy(
        stages=stages,
        sla_hours=float(raw.get("sla_hours", 48)),
        requires_note_on_reject=bool(raw.get("requires_note_on_reject", True)),
        evidence=list(raw.get("evidence", [])),
        key=(kind or "generic").lower(),
    )


# --------------------------------------------------------------------- hashing
def canonical(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def chain_hash(prev_hash: str, entry: Dict[str, Any]) -> str:
    payload = ((prev_hash or "GENESIS") + canonical(entry)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def verify_chain(doc: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Recompute the hash chain over recorded decisions; report the first divergence."""
    prev = "GENESIS"
    problems: List[str] = []
    for i, entry in enumerate(doc.get("audit", []) or []):
        # The digest covers every recorded field except the digest itself.
        body = {k: v for k, v in entry.items() if k != "hash"}
        expect = chain_hash(prev, body)
        got = entry.get("hash")
        if got != expect:
            problems.append(f"entry {i} hash mismatch (recorded {str(got)[:12]}…, expected {expect[:12]}…)")
            break
        prev = got or prev
    return (not problems), problems


# --------------------------------------------------------------------- construction
def new_request(
    *,
    title: str,
    kind: str,
    requester_id: str,
    requester_name: str = "",
    department_id: Optional[str] = None,
    description: str = "",
    amount: Optional[float] = None,
    evidence: Optional[Dict[str, Any]] = None,
    priority: str = "Medium",
    hod_id: Optional[str] = None,
    principal_id: Optional[str] = None,
    related_task_id: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    now = now or datetime.utcnow()
    policy = policy_for(kind, amount)
    missing = [k for k in policy.evidence if not (evidence or {}).get(k) and not (evidence or {}).get(k.replace("_", ""))]
    doc: Dict[str, Any] = {
        "title": title,
        "kind": policy.key,
        "description": description,
        "requester_id": requester_id,
        "requester_name": requester_name,
        "department_id": department_id,
        "amount": float(amount) if amount is not None else None,
        "evidence": evidence or {},
        "priority": priority,
        "status": "PENDING",
        "stage_index": 0,
        "stage": policy.stages[0],
        "stages": policy.stages,
        "sla_hours": policy.sla_hours,
        "approver_role": policy.stages[0],
        "hod_id": hod_id,
        "principal_id": principal_id,
        "related_task_id": related_task_id,
        "created_at": now.isoformat(timespec="seconds"),
        "updated_at": now.isoformat(timespec="seconds"),
        "stage_entered_at": now.isoformat(timespec="seconds"),
        "due_at": (now + timedelta(hours=policy.sla_hours)).isoformat(timespec="seconds"),
        "escalation_count": 0,
        "decision": None,
        "decision_note": None,
        "decided_by": None,
        "decided_at": None,
        "resubmissions": 0,
        "audit": [],
        "missing_evidence": missing,
        "workflow_version": "v2",
    }
    doc["audit"] = []
    _append_audit(
        doc,
        {
            "action": "SUBMITTED",
            "actor_id": requester_id,
            "actor_name": requester_name,
            "at": doc["created_at"],
            "stage": policy.stages[0],
            "note": f"{policy.key} request raised ({' -> '.join(policy.stages)})",
        },
    )
    return doc


# --------------------------------------------------------------------- transitions
def _append_audit(doc: Dict[str, Any], entry: Dict[str, Any]) -> None:
    audit = doc.setdefault("audit", [])
    prev = audit[-1].get("hash") if audit else "GENESIS"
    entry["seq"] = len(audit)
    entry["prev_hash"] = prev
    entry["hash"] = chain_hash(prev or "GENESIS", entry)
    audit.append(entry)


def advance(
    doc: Dict[str, Any],
    *,
    decision: str,
    actor_id: str,
    actor_role: str,
    actor_name: str = "",
    note: str = "",
    delegate_of: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Approve/reject at the current stage. Raises ApprovalError on any invalid move."""
    now = now or datetime.utcnow()
    decision = (decision or "").upper()
    status = (doc.get("status") or "PENDING").upper()
    if status in TERMINAL:
        raise ApprovalError(f"Request is already {status.lower()}", "already_decided")
    if decision not in ("APPROVE", "REJECT"):
        raise ApprovalError("decision must be APPROVE or REJECT", "bad_decision")

    stages = doc.get("stages") or policy_for(doc.get("kind", "generic"), doc.get("amount")).stages
    idx = int(doc.get("stage_index", 0))
    current_stage = (doc.get("stage") or stages[idx]).upper()
    actor_stage = APPROVER_ROLES.get((actor_role or "").upper(), (actor_role or "").upper())

    if actor_stage != current_stage and (actor_role or "").upper() != "ADMIN":
        raise ApprovalError(
            f"Stage mismatch: this request is with {current_stage}, not {actor_stage or actor_role}.",
            "wrong_stage",
        )
    if decision == "REJECT":
        policy = policy_for(doc.get("kind", "generic"), doc.get("amount"))
        if policy.requires_note_on_reject and not (note or "").strip():
            raise ApprovalError("A rejection reason is required for this request type.", "note_required")

    at = now.isoformat(timespec="seconds")
    entry: Dict[str, Any] = {
        "action": decision,
        "stage": current_stage,
        "actor_id": actor_id,
        "actor_name": actor_name,
        "note": note or "",
        "at": at,
    }
    if delegate_of:
        entry["on_behalf_of"] = delegate_of

    sla = evaluate_sla(doc, now)
    entry["hours_in_stage"] = sla["hours_waiting"]

    if decision == "REJECT":
        doc.update(
            {
                "status": "REJECTED",
                "decision": "REJECTED",
                "decision_note": note,
                "decided_by": actor_id,
                "decided_at": at,
                "updated_at": at,
                "closed_at": at,
            }
        )
        entry["note"] = note
        _append_audit(doc, entry)
        return doc

    if idx + 1 < len(stages):
        nxt = stages[idx + 1]
        doc.update(
            {
                "stage_index": idx + 1,
                "stage": nxt,
                "approver_role": nxt,
                "status": "PENDING",
                "stage_entered_at": at,
                "updated_at": at,
                "due_at": (now + timedelta(hours=float(doc.get("sla_hours") or 48))).isoformat(timespec="seconds"),
            }
        )
        entry["advances_to"] = nxt
        _append_audit(doc, entry)
        return doc

    doc.update(
        {
            "status": "APPROVED",
            "decision": "APPROVED",
            "decision_note": note or "Approved at final stage",
            "decided_by": actor_id,
            "decided_at": at,
            "updated_at": at,
            "closed_at": at,
        }
    )
    _append_audit(doc, entry)
    return doc


def resubmit(doc: Dict[str, Any], *, actor_id: str, actor_name: str = "", note: str = "", evidence: Optional[Dict[str, Any]] = None, now: Optional[datetime] = None) -> Dict[str, Any]:
    """A rejected request may be corrected and resubmitted by its requester."""
    now = now or datetime.utcnow()
    if (doc.get("status") or "").upper() != "REJECTED":
        raise ApprovalError("Only rejected requests can be resubmitted.", "not_rejected")
    at = now.isoformat(timespec="seconds")
    stages = doc.get("stages") or ["HOD"]
    doc.update(
        {
            "status": "PENDING",
            "stage": stages[0],
            "stage_index": 0,
            "approver_role": stages[0],
            "decision": None,
            "decision_note": None,
            "decided_by": None,
            "decided_at": None,
            "closed_at": None,
            "resubmissions": int(doc.get("resubmissions", 0)) + 1,
            "updated_at": at,
            "stage_entered_at": at,
            "due_at": (now + timedelta(hours=float(doc.get("sla_hours") or 48))).isoformat(timespec="seconds"),
            "evidence": {**(doc.get("evidence") or {}), **(evidence or {})},
        }
    )
    _append_audit(doc, {"action": "RESUBMITTED", "stage": stages[0], "actor_id": actor_id, "actor_name": actor_name, "note": note, "at": at})
    return doc


def cancel(doc: Dict[str, Any], *, actor_id: str, actor_name: str = "", note: str = "", now: Optional[datetime] = None) -> Dict[str, Any]:
    now = now or datetime.utcnow()
    at = now.isoformat(timespec="seconds")
    if (doc.get("status") or "").upper() in ("APPROVED", "REJECTED"):
        raise ApprovalError("Decided requests cannot be cancelled.", "already_decided")
    doc.update({"status": "CANCELLED", "decision": "CANCELLED", "decision_note": note, "updated_at": at, "closed_at": at, "decided_by": actor_id})
    _append_audit(doc, {"action": "CANCELLED", "stage": doc.get("stage"), "actor_id": actor_id, "actor_name": actor_name, "note": note, "at": at})
    return doc


def delegate(doc: Dict[str, Any], *, from_id: str, to_id: str, to_name: str, note: str = "", now: Optional[datetime] = None) -> Dict[str, Any]:
    """Reassign the pending stage to a delegate (out-of-office, committee substitution)."""
    now = now or datetime.utcnow()
    at = now.isoformat(timespec="seconds")
    if (doc.get("status") or "").upper() in TERMINAL:
        raise ApprovalError("Nothing to delegate on a closed request.", "already_decided")
    doc.update({"delegated_to": to_id, "delegated_from": from_id, "updated_at": at})
    _append_audit(doc, {"action": "DELEGATED", "stage": doc.get("stage"), "actor_id": from_id, "to": to_id, "note": note, "at": at})
    return doc


# --------------------------------------------------------------------- SLA / escalation
def evaluate_sla(doc: Dict[str, Any], now: Optional[datetime] = None) -> Dict[str, Any]:
    now = now or datetime.utcnow()
    if (doc.get("status") or "").upper() in TERMINAL:
        return {"state": "closed", "hours_waiting": 0.0, "sla_hours": float(doc.get("sla_hours") or 0), "breached": False, "escalate": False, "percent_consumed": 0.0}
    started = _parse(doc.get("stage_entered_at") or doc.get("created_at"))
    hours = (now - started).total_seconds() / 3600.0 if started else 0.0
    sla = float(doc.get("sla_hours") or 48)
    overdue_ratio = hours / sla if sla else 0.0
    return {
        "state": "breached" if hours > sla else ("due_soon" if hours > sla * 0.75 else "within_sla"),
        "hours_waiting": round(hours, 1),
        "sla_hours": sla,
        "hours_remaining": round(max(0.0, sla - hours), 1),
        "percent_consumed": round(min(150.0, overdue_ratio * 100.0), 1),
        "breached": hours > sla,
        "escalate": hours > sla * 1.5,  # breach once, escalate once - never spam
        "due_at": doc.get("due_at"),
    }


def escalation_target(doc: Dict[str, Any]) -> Tuple[str, str]:
    """Where a breached request goes: HOD stage -> Principal, Principal stage -> ADMIN."""
    stage = (doc.get("stage") or "HOD").upper()
    if stage == "HOD":
        return ("role:PRINCIPAL", "PRINCIPAL")
    return ("role:ADMIN", "ADMIN")


def _parse(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", ""))
    except ValueError:  # pragma: no cover
        return None


def can_act(doc: Dict[str, Any], role: str, user_id: str) -> Tuple[bool, str]:
    status = (doc.get("status") or "").upper()
    if status in TERMINAL:
        return False, "This request is already closed."
    if role == "ADMIN":
        return True, "Administrator override"
    stage = (doc.get("stage") or "").upper()
    if doc.get("delegated_to") and doc.get("delegated_to") != user_id:
        return False, "Delegated to another approver."
    if APPROVER_ROLES.get(role, role) == stage:
        return True, f"Current stage is {stage}"
    return False, f"Waiting on {stage}."


def queue_for(db: Any, user: Dict[str, Any], *, now: Optional[datetime] = None) -> Dict[str, Any]:
    """The approver's inbox with SLA state - the query that used to be hand-rolled in UI."""
    now = now or datetime.utcnow()
    role = (user.get("role") or "").upper()
    rows: List[Dict[str, Any]] = []
    for snap in db.collection("approvals").stream():
        d = snap.to_dict()
        d.setdefault("id", snap.id)
        if (d.get("status") or "").upper() in TERMINAL:
            continue
        eligible, reason = can_act(d, role, user.get("id", ""))
        if not eligible:
            continue
        d["sla"] = evaluate_sla(d, now)
        d["action_reason"] = reason
        rows.append(d)
    rows.sort(key=lambda x: (-(x["sla"]["percent_consumed"]), (x.get("priority") or "Medium")))
    return {
        "pending": rows,
        "counts": {
            "total": len(rows),
            "breached": sum(1 for r in rows if r["sla"]["breached"]),
            "due_soon": sum(1 for r in rows if r["sla"]["state"] == "due_soon"),
        },
    }
