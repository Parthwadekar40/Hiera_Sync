from typing import List, Optional
from datetime import datetime
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from google.cloud.firestore import Client
from app.database.session import get_db
from app.schemas.schemas import ApprovalCreate, ApprovalUpdate, ApprovalResponse
from app.auth.permissions import get_current_active_user
from app.models.models import User

router = APIRouter()

DEFAULT_APPROVALS = [
    {
        "id": "app_1",
        "title": "Final Year Project Review",
        "requested": "AIML Final Year Students",
        "assigned": "Dr. Animesh Tayal",
        "priority": "High",
        "status": "Pending",
        "created_at": "2026-08-01T10:00:00Z"
    },
    {
        "id": "app_2",
        "title": "AI Lab Equipment Request",
        "requested": "AI Lab Coordinator",
        "assigned": "Mrs. Neha Gurnani",
        "priority": "Medium",
        "status": "Pending",
        "created_at": "2026-08-01T10:00:00Z"
    },
    {
        "id": "app_3",
        "title": "Machine Learning Workshop Approval",
        "requested": "AIML Student Club",
        "assigned": "Ms. Sweta Arun Bokade",
        "priority": "Low",
        "status": "Approved",
        "created_at": "2026-08-01T10:00:00Z"
    },
    {
        "id": "app_4",
        "title": "Research Paper Submission Review",
        "requested": "Student Research Team",
        "assigned": "Dr. Bhushan Mahendra Manjre",
        "priority": "High",
        "status": "Pending",
        "created_at": "2026-08-01T10:00:00Z"
    }
]

@router.get("/", response_model=List[ApprovalResponse])
def get_approvals(
    db: Client = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    approvals_ref = db.collection('approvals')
    docs = list(approvals_ref.stream())
    approvals = []
    if docs:
        for doc in docs:
            row = dict(doc.to_dict())
            # v2 stores canonical uppercase states; this page expects v1 casing.
            status = str(row.get("status") or "PENDING").upper()
            row["status"] = {"PENDING": "Pending", "APPROVED": "Approved", "REJECTED": "Rejected", "CANCELLED": "Cancelled"}.get(status, row.get("status", "Pending"))
            row.setdefault("requested", row.get("requester_name"))
            row.setdefault("assigned", row.get("requester_name"))
            row.setdefault("comments", row.get("decision_note") or row.get("hod_comment"))
            row["stage"] = row.get("stage") or row.get("current_stage")
            approvals.append(row)
    else:
        approvals = DEFAULT_APPROVALS
    return approvals

@router.post("/", response_model=ApprovalResponse)
def create_approval(
    approval: ApprovalCreate,
    db: Client = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    approval_id = str(uuid.uuid4())
    db_approval = approval.dict()
    db_approval['id'] = approval_id
    db_approval['created_at'] = datetime.utcnow().isoformat()
    
    db.collection('approvals').document(approval_id).set(db_approval)
    return db_approval

@router.put("/{approval_id}/approve", response_model=ApprovalResponse)
def approve_request(
    approval_id: str,
    db: Client = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    doc_ref = db.collection('approvals').document(approval_id)
    doc = doc_ref.get()
    
    if not doc.exists:
        for a in DEFAULT_APPROVALS:
            if a["id"] == approval_id:
                a["status"] = "Approved"
                a["reviewed_at"] = datetime.utcnow().isoformat()
                return a
        raise HTTPException(status_code=404, detail="Approval request not found")
        
    doc_ref.update({
        "status": "Approved",
        "reviewed_at": datetime.utcnow().isoformat()
    })
    return doc_ref.get().to_dict()

@router.put("/{approval_id}/reject", response_model=ApprovalResponse)
def reject_request(
    approval_id: str,
    db: Client = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    doc_ref = db.collection('approvals').document(approval_id)
    doc = doc_ref.get()
    
    if not doc.exists:
        for a in DEFAULT_APPROVALS:
            if a["id"] == approval_id:
                a["status"] = "Rejected"
                a["reviewed_at"] = datetime.utcnow().isoformat()
                return a
        raise HTTPException(status_code=404, detail="Approval request not found")
        
    doc_ref.update({
        "status": "Rejected",
        "reviewed_at": datetime.utcnow().isoformat()
    })
    return doc_ref.get().to_dict()

@router.delete("/{approval_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_approval(
    approval_id: str,
    db: Client = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    doc_ref = db.collection('approvals').document(approval_id)
    if not doc_ref.get().exists:
        raise HTTPException(status_code=404, detail="Approval request not found")
        
    doc_ref.delete()
    return None

