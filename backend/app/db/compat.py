"""Field-name harmonisation between the deck's Firestore schema (Slide 14) and v1 code.

The presentation specifies `tasks.progress_pct / assignee_id / risk_score / goal_id`,
`approvals.hod_comment / principal_comment / stage`, `events.event_type / organizer_id`.
The shipped v1 routers read `progress` ("75%"), `assigned_id`, `type`, `person`. Rather
than break 13 existing UI pages, every document is stored with **both** spellings kept in
sync by these normalizers, so:
  * analytics/exports and new endpoints use the canonical schema names,
  * legacy pages keep working untouched,
  * switching to Firestore later is a no-op (identical document shape).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional


def _progress_str(value: Any) -> str:
    if isinstance(value, str):
        raw = value.replace("%", "").strip() or "0"
        return f"{max(0, min(100, int(float(raw) if raw.replace('.', '', 1).isdigit() else 0)))}%"
    try:
        return f"{max(0, min(100, int(float(value or 0))))}%"
    except (TypeError, ValueError):
        return "0%"


def _progress_pct(value: Any) -> float:
    return float(_progress_str(value).rstrip("%"))


def normalize_task(doc: Dict[str, Any], *, assessment: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    out = dict(doc or {})
    pct = _progress_pct(out.get("progress_pct", out.get("progress")))
    out["progress_pct"] = pct
    out["progress"] = f"{int(pct)}%"

    # assignee aliases (deck: assignee_id ; v1 UI: assigned_id + assigned name)
    assignee_id = out.get("assignee_id") or out.get("assigned_id")
    if assignee_id:
        out["assignee_id"] = assignee_id
        out["assigned_id"] = assignee_id
    if out.get("assignee") and not out.get("assigned"):
        out["assigned"] = out["assignee"]

    # deadline aliases (deck: deadline ; model: due_date)
    if out.get("due_date") and not out.get("deadline"):
        out["deadline"] = out["due_date"]
    if out.get("deadline") and not out.get("due_date"):
        out["due_date"] = out["deadline"]

    out.setdefault("goal_id", out.get("goal"))
    out.setdefault("subtasks", [])
    out.setdefault("status", "TODO")

    if assessment:
        out["risk_score"] = assessment.get("risk_score", 0)
        out["risk_level"] = assessment.get("risk_level", "LOW")
        out["risk_factors"] = [f.get("evidence", "") for f in assessment.get("factors", []) if f.get("sub_score", 0) >= 12]
        out["risk_drivers"] = assessment.get("drivers", [])
        out["delay_probability"] = assessment.get("delay_probability", 0)
        out["risk_explanation"] = assessment.get("explanation", "")
        out["risk_recommended_action"] = (assessment.get("recommendations") or [""])[0]
        out["risk_projected_completion"] = assessment.get("projected_completion")
        out["risk_assessed_at"] = datetime.utcnow().isoformat(timespec="seconds")
    return out


def normalize_event(doc: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(doc or {})
    out["event_type"] = out.get("event_type") or out.get("type") or "Academic"
    out["type"] = out["event_type"]
    out["organizer_id"] = out.get("organizer_id") or out.get("person_id") or out.get("creator_id")
    if out.get("person") and not out.get("organizer"):
        out["organizer"] = out["person"]
    out.setdefault("reminded_at", None)
    return out


def normalize_approval(doc: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(doc or {})
    # v1 UI reads hod_comment / principal_comment; engine v2 writes the audit chain.
    audit = out.get("audit") or []
    for entry in audit:
        action = (entry.get("action") or "").upper()
        stage = (entry.get("stage") or "").upper()
        note = entry.get("note") or ""
        if stage == "HOD" and action in ("APPROVE", "REJECT", "DELEGATED"):
            out.setdefault("hod_comment", note or ("Approved" if action == "APPROVE" else "Declined"))
        if stage == "PRINCIPAL" and action in ("APPROVE", "REJECT"):
            out.setdefault("principal_comment", note or ("Approved" if action == "APPROVE" else "Declined"))
    out["current_stage"] = out.get("stage") or out.get("current_stage") or "HOD_STAGE"
    out["status"] = (out.get("status") or "PENDING").upper()
    return out


def normalize_user(doc: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(doc or {})
    out["department_id"] = out.get("department_id")
    out.setdefault("status", "ACTIVE")
    out.setdefault("role", "FACULTY")
    return out


def task_row(doc: Dict[str, Any], assessment: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Public API shape for a task list item (canonical + legacy aliases + risk)."""
    return normalize_task(doc, assessment=assessment)
