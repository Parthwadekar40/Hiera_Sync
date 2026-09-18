"""Role-Based Access Control - the permission matrix from Slide 13, encoded as data.

v1 enforced permissions with inline `check_role([...])` lists scattered across 17 routers,
which makes the matrix impossible to review in one place. This module is the single
authoritative table; routers depend on `require(perm)` instead of hand-listing roles, and
`/alerts/rbac` renders the exact matrix for the report appendix.

Deck contract (Slide 13):
  Principal/Admin : assign, approve HOD-stage, approve Principal-stage, full-institute analytics, manage system
  HOD             : assign, approve stage 1, no stage 2, department analytics, no system management
  Faculty         : subtasks only, no approvals, self-load analytics only
  TA/Lab Assistant: none of the above; self tasks only
  Staff/Student/Rep: events only
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from fastapi import Depends, HTTPException, status

from app.auth.permissions import get_current_active_user
from app.models.models import RoleEnum, User

ALL_ROLES = [r.value for r in RoleEnum]

# --- capability names used by the routers
CAPABILITIES = [
    "assign_tasks",
    "approve_hod",
    "approve_principal",
    "view_analytics",
    "manage_system",
    "manage_users",
    "create_events",
    "update_subtasks",
    "update_own_task",
    "review_join_requests",
    "link_goals",
    "export_reports",
    "configure_notifications",
    "override_risk_weights",
    "chat_with_ai",
    "run_automation",
]

_ANALYTICS = {"full_institute", "department", "self", "none"}

MATRIX: Dict[str, Dict[str, Any]] = {
    "ADMIN": {
        "run_automation": True,
        "assign_tasks": True,
        "approve_hod": True,
        "approve_principal": True,
        "view_analytics": "full_institute",
        "manage_system": True,
        "manage_users": True,
        "create_events": True,
        "update_subtasks": True,
        "update_own_task": True,
        "review_join_requests": True,
        "link_goals": True,
        "export_reports": True,
        "configure_notifications": True,
        "override_risk_weights": True,
        "chat_with_ai": True,
    },
    "PRINCIPAL": {
        "run_automation": True,
        "assign_tasks": True,
        "approve_hod": True,
        "approve_principal": True,
        "view_analytics": "full_institute",
        "manage_system": True,
        "manage_users": True,
        "create_events": True,
        "update_subtasks": True,
        "update_own_task": True,
        "review_join_requests": True,
        "link_goals": True,
        "export_reports": True,
        "configure_notifications": True,
        "override_risk_weights": True,
        "chat_with_ai": True,
    },
    "HOD": {
        "run_automation": True,
        "assign_tasks": True,
        "approve_hod": True,
        "approve_principal": False,
        "view_analytics": "department",
        "manage_system": False,
        "manage_users": True,          # may manage own department roster
        "create_events": True,
        "update_subtasks": True,
        "update_own_task": True,
        "review_join_requests": True,
        "link_goals": True,
        "export_reports": True,
        "configure_notifications": False,
        "override_risk_weights": False,
        "chat_with_ai": True,
    },
    "FACULTY": {
        "run_automation": False,
        "assign_tasks": False,
        "approve_hod": False,
        "approve_principal": False,
        "view_analytics": "self",
        "manage_system": False,
        "manage_users": False,
        "create_events": False,
        "update_subtasks": True,       # deck: "Subtasks"
        "update_own_task": True,
        "review_join_requests": False,
        "link_goals": False,
        "export_reports": False,
        "configure_notifications": True,  # own preferences only
        "override_risk_weights": False,
        "chat_with_ai": True,
    },
    "TEACHER": "FACULTY",
    "TA": {
        "assign_tasks": False,
        "approve_hod": False,
        "approve_principal": False,
        "view_analytics": "none",
        "manage_system": False,
        "manage_users": False,
        "create_events": False,
        "update_subtasks": True,
        "update_own_task": True,
        "review_join_requests": False,
        "link_goals": False,
        "export_reports": False,
        "configure_notifications": True,
        "override_risk_weights": False,
        "chat_with_ai": True,
    },
    "LAB_ASSISTANT": "TA",
    "STAFF": {
        "assign_tasks": False,
        "approve_hod": False,
        "approve_principal": False,
        "view_analytics": "none",
        "manage_system": False,
        "manage_users": False,
        "create_events": True,
        "update_subtasks": True,
        "update_own_task": True,
        "review_join_requests": False,
        "link_goals": False,
        "export_reports": False,
        "configure_notifications": True,
        "override_risk_weights": False,
        "chat_with_ai": True,
    },
    "STUDENT": {
        "assign_tasks": False,
        "approve_hod": False,
        "approve_principal": False,
        "view_analytics": "none",
        "manage_system": False,
        "manage_users": False,
        "create_events": False,
        "update_subtasks": True,
        "update_own_task": True,
        "review_join_requests": False,
        "link_goals": False,
        "export_reports": False,
        "configure_notifications": True,
        "override_risk_weights": False,
        "chat_with_ai": True,
    },
    "STUDENT_REP": {
        "assign_tasks": False,
        "approve_hod": False,
        "approve_principal": False,
        "view_analytics": "none",
        "manage_system": False,
        "manage_users": False,
        "create_events": True,   # deck: events only -> may propose/organise events
        "update_subtasks": True,
        "update_own_task": True,
        "review_join_requests": False,
        "link_goals": False,
        "export_reports": False,
        "configure_notifications": True,
        "override_risk_weights": False,
        "chat_with_ai": True,
    },
}


def _resolve(role: str) -> Dict[str, Any]:
    row = MATRIX.get((role or "").upper(), {})
    depth = 0
    while isinstance(row, str) and depth < 3:  # aliases: TEACHER -> FACULTY
        row = MATRIX.get(row, {})
        depth += 1
    return row or MATRIX["STUDENT"]


def can(role: str, capability: str) -> bool:
    row = _resolve(role)
    val = row.get(capability, False)
    return bool(val) if not isinstance(val, str) else True


def analytics_scope(role: str) -> str:
    return str(_resolve(role).get("view_analytics", "none"))


def visible_tasks(role: str, department_id: Optional[str], tasks: List[Dict[str, Any]], user_id: str) -> List[Dict[str, Any]]:
    """Row-level visibility: self / department / institute, driven by the same matrix."""
    scope = analytics_scope(role)
    if scope in ("full_institute",):
        return tasks
    if scope == "department":
        return [t for t in tasks if not t.get("department_id") or t.get("department_id") == department_id or _mine(t, user_id, role)]
    return [t for t in tasks if _mine(t, user_id, role)]


def _mine(task: Dict[str, Any], user_id: str, role: str) -> bool:
    owner = str(task.get("assigned_id") or task.get("assignee_id") or task.get("created_id") or "")
    return owner == user_id or str(task.get("creator_id") or "") == user_id


def require(capability: str):
    """FastAPI dependency factory: `Depends(require("assign_tasks"))`."""

    def _checker(current_user: User = Depends(get_current_active_user)) -> User:
        if not can(current_user.role.value, capability):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "message": f"Role {current_user.role.value} is not permitted to {capability}.",
                    "capability": capability,
                    "role": current_user.role.value,
                    "matrix_reference": "docs/05_RBAC_MATRIX.md (Slide 13)",
                },
            )
        return current_user

    return _checker


def matrix_table() -> List[Dict[str, Any]]:
    """Rendered as the RBAC appendix table; keeps code and documentation identical."""
    rows = []
    for role in ["PRINCIPAL", "ADMIN", "HOD", "FACULTY", "TEACHER", "TA", "LAB_ASSISTANT", "STAFF", "STUDENT", "STUDENT_REP"]:
        row = _resolve(role)
        rows.append(
            {
                "role": role,
                "assign_tasks": _mark(row.get("assign_tasks")),
                "approve_hod": _mark(row.get("approve_hod")),
                "approve_principal": _mark(row.get("approve_principal")),
                "view_analytics": row.get("view_analytics", "none"),
                "manage_system": _mark(row.get("manage_system")),
                "create_events": _mark(row.get("create_events")),
                "update_subtasks": _mark(row.get("update_subtasks")),
                "export_reports": _mark(row.get("export_reports")),
                "configure_notifications": _mark(row.get("configure_notifications")),
                "override_risk_weights": _mark(row.get("override_risk_weights")),
            }
        )
    return rows


def _mark(value: Any) -> str:
    if isinstance(value, str):
        return value
    return "Yes" if value else "No"


def roles_for(capability: str) -> Set[str]:
    return {r for r in MATRIX if isinstance(MATRIX[r], dict) and can(r, capability)}
