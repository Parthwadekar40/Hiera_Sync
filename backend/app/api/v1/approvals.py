import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from google.cloud.firestore import Client

from app.auth.permissions import check_role, get_current_active_user
from app.database.session import get_db
from app.models.models import RoleEnum, User
from app.schemas.schemas import ApprovalCreate, ApprovalResponse, ApprovalUpdate
from app.utils.logging import logger

router = APIRouter()

REVIEW_ROLES = [RoleEnum.ADMIN, RoleEnum.HOD]

DECISIONS = {"Approved", "Rejected", "Pending"}


def _default_approvals() -> List[dict]:
    """Sample queue for a fresh collection (never mutated in place)."""
    now = datetime.utcnow().isoformat()
    seeds = [
        ("Final Year Project Review Panel", "AIML Final Year Students", "Dr. Animesh Tayal", "High", "Pending"),
        ("AI Lab Equipment Request", "AI Lab Coordinator", "Mrs. Neha Gurnani", "Medium", "Pending"),
        ("Machine Learning Workshop Budget", "AIML Student Club", "Ms. Sweta Arun Bokade", "Low", "Approved"),
        ("Research Paper Submission — IEEE Conference", "Student Research Team", "Dr. Bhushan Mahendra Manjre", "High", "Pending"),
        ("Industry Visit — Nagpur AI Park", "TYAIML Class Representative", "Mrs. Neha Gurnani", "Medium", "Rejected"),
    ]
    return [
        {
            "id": f"app_seed_{index + 1}",
            "title": title,
            "requested": requested,
            "assigned": assigned,
            "priority": priority,
            "status": state,
            "comments": None,
            "created_at": now,
            "reviewed_at": now if state != "Pending" else None,
        }
        for index, (title, requested, assigned, priority, state) in enumerate(seeds)
    ]


def _notify_requester(db: Client, approval: dict, decision: str, actor: User) -> None:
    """Tell the requester what happened, when we can resolve them by name."""
    requester = (approval.get("requested") or "").strip()
    if not requester:
        return

    try:
        matches = list(db.collection("users").where("name", "==", requester).limit(1).stream())
    except Exception as exc:
        logger.warning(f"Could not look up requester '{requester}': {exc}")
        return

    if not matches:
        return

    user_id = matches[0].to_dict().get("id") or matches[0].id
    approved = decision == "Approved"
    notification = {
        "id": f"notif_{uuid.uuid4().hex[:8]}",
        "user_id": user_id,
        "title": f"Request {decision.lower()}: {approval.get('title', 'Untitled')}",
        "message": approval.get("comments")
        or f"{actor.name} {decision.lower()} this request on {datetime.utcnow().date().isoformat()}.",
        "type": "Approval",
        "priority": approval.get("priority") or "Medium",
        "target_route": "/approvals",
        "icon": "✅" if approved else "↩",
        "status": "New",
        "time": "Just now",
        "is_read": False,
        "created_at": datetime.utcnow().isoformat(),
    }
    db.collection("notifications").document(notification["id"]).set(notification)


@router.get("/", response_model=List[ApprovalResponse])
def get_approvals(
    status_filter: Optional[str] = None,
    db: Client = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    collection = db.collection("approvals")
    docs = list(collection.stream())

    if docs:
        approvals = [doc.to_dict() for doc in docs]
    else:
        approvals = _default_approvals()
        try:
            for approval in approvals:
                collection.document(approval["id"]).set(approval)
        except Exception as exc:
            logger.warning(f"Could not seed sample approvals (read-only fallback): {exc}")

    if status_filter:
        approvals = [
            approval
            for approval in approvals
            if (approval.get("status") or "Pending") == status_filter
        ]

    approvals.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    return approvals


@router.post("/", response_model=ApprovalResponse, status_code=status.HTTP_201_CREATED)
def create_approval(
    approval: ApprovalCreate,
    db: Client = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    approval_id = str(uuid.uuid4())
    db_approval = approval.model_dump()
    db_approval["id"] = approval_id
    db_approval["status"] = "Pending"
    db_approval["created_at"] = datetime.utcnow().isoformat()

    db.collection("approvals").document(approval_id).set(db_approval)
    return db_approval


@router.put("/{approval_id}", response_model=ApprovalResponse)
def update_approval(
    approval_id: str,
    payload: ApprovalUpdate,
    db: Client = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update the note (or status) on a request. Only the HOD desk may change
    the decision itself; requesters may annotate their own pending request."""
    doc_ref = db.collection("approvals").document(approval_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Approval request not found")

    current = doc.to_dict()
    updates = {
        key: value
        for key, value in payload.model_dump(exclude_unset=True).items()
        if value is not None
    }

    changing_decision = updates.get("status") and updates["status"] != current.get("status")
    if changing_decision and current_user.role not in REVIEW_ROLES:
        raise HTTPException(status_code=403, detail="Only HOD / Admin can change a decision")

    owner_name = (current.get("requested") or "").strip()
    is_owner = current_user.role not in REVIEW_ROLES and owner_name.lower() == (current_user.name or "").lower()
    if not changing_decision and not is_owner and current_user.role not in REVIEW_ROLES:
        raise HTTPException(status_code=403, detail="You cannot edit this request")

    if not updates:
        return current

    doc_ref.update(updates)
    return doc_ref.get().to_dict()


def _decide(approval_id: str, decision: str, db: Client, current_user: User) -> dict:
    doc_ref = db.collection("approvals").document(approval_id)
    doc = doc_ref.get()

    if not doc.exists:
        for seed in _default_approvals():
            if seed["id"] == approval_id:
                seed.update({"status": decision, "reviewed_at": datetime.utcnow().isoformat()})
                return seed
        raise HTTPException(status_code=404, detail="Approval request not found")

    current = doc.to_dict()
    if current.get("status") == decision:
        return current

    doc_ref.update({"status": decision, "reviewed_at": datetime.utcnow().isoformat()})
    updated = doc_ref.get().to_dict()

    try:
        _notify_requester(db, updated, decision, current_user)
    except Exception as exc:
        logger.warning(f"Decision saved but the requester notification failed: {exc}")

    return updated


@router.put("/{approval_id}/approve", response_model=ApprovalResponse)
def approve_request(
    approval_id: str,
    db: Client = Depends(get_db),
    current_user: User = Depends(check_role(REVIEW_ROLES)),
):
    return _decide(approval_id, "Approved", db, current_user)


@router.put("/{approval_id}/reject", response_model=ApprovalResponse)
def reject_request(
    approval_id: str,
    db: Client = Depends(get_db),
    current_user: User = Depends(check_role(REVIEW_ROLES)),
):
    return _decide(approval_id, "Rejected", db, current_user)


@router.delete("/{approval_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_approval(
    approval_id: str,
    db: Client = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Withdraw a request: the requester may remove their own pending request,
    the HOD desk may remove any."""
    doc_ref = db.collection("approvals").document(approval_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Approval request not found")

    current = doc.to_dict()
    is_owner = (current.get("requested") or "").strip().lower() == (current_user.name or "").lower()
    if current_user.role not in REVIEW_ROLES and not (is_owner and current.get("status") == "Pending"):
        raise HTTPException(
            status_code=403,
            detail="Only the requester (while pending) or the HOD desk can remove this request",
        )

    doc_ref.delete()
    return None
