from typing import List, Optional
from datetime import datetime
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from google.cloud.firestore import Client
from app.database.session import get_db
from app.schemas.schemas import TaskRequestCreate, TaskRequestUpdate, TaskRequestResponse, TaskCreate
from app.auth.permissions import get_current_active_user, check_role
from app.models.models import User, RoleEnum
from app.api.v1.notifications import trigger_notification
from app.api.v1.tasks import create_task

router = APIRouter()

REVIEW_ROLES = [RoleEnum.ADMIN, RoleEnum.HOD]


def _task_from_request(req_data: dict, overrides: dict, current_user: User) -> TaskCreate:
    """Build the task an approved request turns into."""
    payload = {
        "title": req_data.get("title", "Untitled request"),
        "assigned": req_data.get("requester_name") or current_user.name,
        "assigned_id": req_data.get("requester_id"),
        "deadline": req_data.get("suggested_deadline") or datetime.utcnow().date().isoformat(),
        "priority": req_data.get("priority") or "Medium",
        "status": "Pending",
        "description": req_data.get("description"),
        "category": req_data.get("category") or "General",
        "estimated_effort": req_data.get("estimated_effort"),
    }
    payload.update({key: value for key, value in (overrides or {}).items() if value is not None})
    return TaskCreate(**payload)

@router.post("", response_model=TaskRequestResponse)
def create_task_request(
    request: TaskRequestCreate,
    db: Client = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    req_id = str(uuid.uuid4())
    db_req = request.dict()
    db_req['id'] = req_id
    db_req['requester_id'] = current_user.id
    db_req['requester_name'] = current_user.name
    db_req['status'] = "PENDING"
    db_req['created_at'] = datetime.utcnow().isoformat()
    db_req['reviewed_at'] = None
    db_req['reviewed_by'] = None
    db_req['rejection_reason'] = None
    db_req['created_task_id'] = None
    
    db.collection('task_requests').document(req_id).set(db_req)
    
    # Notify department that a new request is pending
    trigger_notification(
        db, 
        "department", 
        "TASK REQUEST", 
        "New Task Request", 
        f"{current_user.name} has requested a new task: {request.title}", 
        "/task-requests",
        "Medium",
        "🟡"
    )
    
    return db_req

@router.get("", response_model=List[TaskRequestResponse])
def get_task_requests(
    db: Client = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    requests_ref = db.collection('task_requests')
    if current_user.role not in REVIEW_ROLES:
        # Everyone else only sees the requests they raised
        docs = list(requests_ref.where('requester_id', '==', current_user.id).stream())
    else:
        # HODs see all
        docs = list(requests_ref.stream())
        
    return [doc.to_dict() for doc in docs]

@router.post("/{req_id}/approve")
def approve_task_request(
    req_id: str,
    task_data: dict,  # Receive the final task payload from the frontend form
    db: Client = Depends(get_db),
    current_user: User = Depends(check_role([RoleEnum.ADMIN, RoleEnum.HOD]))
):
    doc_ref = db.collection('task_requests').document(req_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Task Request not found")
        
    req_data = doc.to_dict()
    if req_data.get("status") != "PENDING":
        raise HTTPException(status_code=400, detail=f"Cannot approve request with status {req_data['status']}")
        
    # Optional override of the task that gets created (title/assignee/deadline...);
    # anything the reviewer does not send is taken from the request itself.
    task = _task_from_request(req_data, task_data or {}, current_user)
    created = create_task(task, db, current_user)

    doc_ref.update({
        "status": "APPROVED",
        "reviewed_at": datetime.utcnow().isoformat(),
        "reviewed_by": current_user.id,
        "created_task_id": created["id"],
    })
    trigger_notification(
        db,
        req_data.get("requester_id") or "department",
        "REQUEST APPROVED",
        "Task Request Approved",
        f"Your request '{req_data.get('title')}' was approved and a task was created.",
        "/tasks",
        "Medium",
        "✅",
    )
    return {"message": "Request approved", "task_id": created["id"],
            "request_id": req_id, "status": "APPROVED"}

@router.api_route("/{req_id}", methods=["PATCH", "PUT"], response_model=TaskRequestResponse)
def update_task_request(
    req_id: str,
    update_data: TaskRequestUpdate,
    db: Client = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    doc_ref = db.collection('task_requests').document(req_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Task Request not found")
        
    req_data = doc.to_dict()

    # Enforce RBAC: only the HOD desk decides; requesters may withdraw their own.
    is_reviewer = current_user.role in REVIEW_ROLES
    if not is_reviewer:
        if req_data.get('requester_id') != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to modify this request")
        # Teachers can only cancel their pending requests
        if update_data.status not in [None, "CANCELLED"]:
             raise HTTPException(status_code=403, detail="Only the HOD desk can approve or reject a request")
        if req_data.get("status") != "PENDING":
            raise HTTPException(status_code=400, detail="Only a pending request can be cancelled")
        
    update_dict = {k: v for k, v in update_data.dict(exclude_unset=True).items() if v is not None}
    
    if "status" in update_dict and update_dict["status"] != req_data.get("status"):
        update_dict["reviewed_at"] = datetime.utcnow().isoformat()
        update_dict["reviewed_by"] = current_user.id
        
        # Notifications
        if update_dict["status"] == "APPROVED":
            # Approving has to produce the task - the notification claimed a task
            # was created, but nothing ever created one unless the client called
            # /tasks itself first.
            if not update_dict.get("created_task_id") and not req_data.get("created_task_id"):
                task = _task_from_request(req_data, {}, current_user)
                created = create_task(task, db, current_user)
                update_dict["created_task_id"] = created["id"]

            trigger_notification(
                db, 
                req_data.get('requester_id') or "department", 
                "REQUEST APPROVED", 
                "Task Request Approved", 
                f"Your request '{req_data.get('title')}' was approved and a task was created.", 
                "/tasks",
                "Medium",
                "✅"
            )
        elif update_dict["status"] == "CANCELLED":
            trigger_notification(
                db,
                "department",
                "REQUEST WITHDRAWN",
                "Task Request Cancelled",
                f"{req_data.get('requester_name')} withdrew the request '{req_data.get('title')}'.",
                "/task-requests",
                "Low",
                "🚫"
            )
        elif update_dict["status"] == "REJECTED":
            reason = update_dict.get("rejection_reason", "No reason provided.")
            trigger_notification(
                db, 
                req_data['requester_id'], 
                "REQUEST REJECTED", 
                "Task Request Rejected", 
                f"Your request '{req_data.get('title')}' was rejected.\nReason: {reason}", 
                "/task-requests",
                "High",
                "❌"
            )

    doc_ref.update(update_dict)
    return doc_ref.get().to_dict()
