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
    if current_user.role == RoleEnum.FACULTY:
        # Teachers see their own requests
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
    if req_data['status'] != "PENDING":
        raise HTTPException(status_code=400, detail=f"Cannot approve request with status {req_data['status']}")
        
    # We create the task via tasks.py logic or manually here. 
    # The frontend will prefill the Create Task form and send us the final task object.
    # But wait, the simplest way is to manually do what `create_task` does here, or the frontend 
    # just calls `/tasks` directly and then calls `/task-requests/{req_id}` with PATCH to mark approved.
    # The prompt specifically says "When HOD clicks [Approve & Create Task]... Open the existing Create Task form with the request information pre-filled. After HOD confirms task creation: 1. Create the actual Task... 2. Set TaskRequest.status = APPROVED..."
    
    # So the HOD workflow will be:
    # 1. HOD clicks Approve
    # 2. Frontend opens modal prefilled
    # 3. Frontend POST /tasks (creates task)
    # 4. Frontend PATCH /task-requests/{req_id} { status: 'APPROVED', created_task_id: '...' }
    # Let's provide a PATCH route to handle this cleanly.
    raise HTTPException(status_code=400, detail="Use PATCH /task-requests/{req_id} instead")

@router.patch("/{req_id}", response_model=TaskRequestResponse)
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
    
    # Enforce RBAC
    if current_user.role == RoleEnum.FACULTY:
        if req_data['requester_id'] != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to modify this request")
        # Teachers can only cancel their pending requests
        if update_data.status not in [None, "CANCELLED"]:
             raise HTTPException(status_code=403, detail="Teachers can only cancel requests")
    else:
        # HOD can approve or reject
        pass
        
    update_dict = {k: v for k, v in update_data.dict(exclude_unset=True).items() if v is not None}
    
    if "status" in update_dict and update_dict["status"] != req_data.get("status"):
        update_dict["reviewed_at"] = datetime.utcnow().isoformat()
        update_dict["reviewed_by"] = current_user.id
        
        # Notifications
        if update_dict["status"] == "APPROVED":
            trigger_notification(
                db, 
                req_data['requester_id'], 
                "REQUEST APPROVED", 
                "Task Request Approved", 
                f"Your request '{req_data.get('title')}' was approved and a task was created.", 
                "/tasks",
                "Medium",
                "✅"
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
