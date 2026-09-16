from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Query
from google.cloud.firestore import Client
from app.database.session import get_db
from app.schemas.schemas import TaskCreate, TaskUpdate, TaskResponse, Subtask
from app.auth.permissions import get_current_active_user, check_role
from app.models.models import User, RoleEnum
from app.api.v1.notifications import trigger_notification

router = APIRouter()

DEFAULT_TASKS = [
    {
        "id": "tsk_1",
        "title": "AI Lab Maintenance",
        "assigned": "Mrs. Neha Gurnani",
        "deadline": "05 August 2026", # Intentionally past to test overdue/risk
        "priority": "High",
        "status": "In Progress",
        "progress": "75%",
        "created_at": "2026-08-01T10:00:00Z"
    },
    {
        "id": "tsk_2",
        "title": "Final Year Project Review",
        "assigned": "Dr. Animesh Tayal",
        "deadline": "10 August 2026",
        "priority": "Medium",
        "status": "Pending Approval",
        "progress": "50%",
        "created_at": "2026-08-01T10:00:00Z"
    },
    {
        "id": "tsk_3",
        "title": "Student Research Tracking",
        "assigned": "Dr. Bhushan Mahendra Manjre",
        "deadline": "15 August 2026",
        "priority": "Low",
        "status": "Completed",
        "progress": "100%",
        "created_at": "2026-08-01T10:00:00Z"
    }
]

def calculate_task_risk(task: Dict[str, Any], faculty_workload: int) -> Dict[str, Any]:
    """
    AI-assisted heuristic deadline risk engine.
    Calculates probability (0-100) of missing deadline.
    """
    if task.get("status") in ["Completed", "Awaiting Approval"]:
        task["risk_score"] = 0
        task["risk_level"] = "LOW"
        task["risk_factors"] = ["Task is already completed or awaiting approval."]
        return task

    risk_score = 0
    factors = []
    
    # Progress
    progress_str = task.get("progress", "0%")
    try:
        progress = int(progress_str.replace("%", ""))
    except ValueError:
        progress = 0

    # Deadline parsing
    deadline_str = task.get("deadline", "")
    days_left = 10  # default assumption if unparseable
    if deadline_str:
        try:
            # Try ISO format
            dt = datetime.fromisoformat(deadline_str.replace("Z", ""))
            days_left = (dt - datetime.utcnow()).days
        except ValueError:
            try:
                # Try "DD Month YYYY" format
                dt = datetime.strptime(deadline_str, "%d %B %Y")
                days_left = (dt - datetime.utcnow()).days
            except ValueError:
                try:
                    # Try YYYY-MM-DD
                    dt = datetime.strptime(deadline_str, "%Y-%m-%d")
                    days_left = (dt - datetime.utcnow()).days
                except ValueError:
                    pass

    # Rules
    if days_left < 0:
        risk_score += 90
        factors.append(f"Task is overdue by {abs(days_left)} days.")
    else:
        if days_left <= 2:
            risk_score += 50
            factors.append(f"Only {days_left} days remaining.")
        elif days_left <= 5:
            risk_score += 30
            factors.append(f"{days_left} days remaining.")
            
        # If low progress and little time
        if progress < 50 and days_left <= 3:
            risk_score += 25
            factors.append(f"Progress is only {progress}%.")

    # Priority modifier
    priority = task.get("priority", "Medium").lower()
    if priority == "high":
        risk_score += 15
        factors.append("High priority task leaves less margin for error.")
        
    # Workload
    if faculty_workload > 3:
        risk_score += 20
        factors.append(f"Faculty workload is high ({faculty_workload} active tasks).")

    # Estimate
    effort = task.get("estimated_effort", "")
    if effort:
        factors.append(f"Estimated effort: {effort}.")

    risk_score = min(max(risk_score, 5), 95)  # Cap between 5 and 95 unless completed
    
    if risk_score > 70:
        level = "HIGH"
    elif risk_score > 40:
        level = "MEDIUM"
    else:
        level = "LOW"
        
    if risk_score <= 40 and not factors:
        factors.append("Sufficient time and normal workload.")

    task["risk_score"] = risk_score
    task["risk_level"] = level
    task["risk_factors"] = factors
    return task

@router.get("", response_model=List[TaskResponse])
def get_tasks(
    priority: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    assigned_to: Optional[str] = Query(None, alias="assigned"),
    db: Client = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    tasks_ref = db.collection('tasks')
    docs = list(tasks_ref.stream())
    tasks = []
    
    all_raw_tasks = [doc.to_dict() for doc in docs] if docs else DEFAULT_TASKS

    # Precompute faculty workload (count of active tasks per assignee)
    workload_map = {}
    for t in all_raw_tasks:
        if t.get("status") not in ["Completed", "Awaiting Approval"]:
            assignee = t.get("assigned_id") or t.get("assigned")
            if assignee:
                workload_map[assignee] = workload_map.get(assignee, 0) + 1

    for data in all_raw_tasks:
        # Secure isolation for faculty
        if current_user.role == RoleEnum.FACULTY:
            if data.get("assigned_id") != current_user.id and current_user.name.lower() not in data.get("assigned", "").lower():
                continue

        if priority and data.get("priority", "").lower() != priority.lower():
            continue
        if status_filter and data.get("status", "").lower() != status_filter.lower():
            continue
        if assigned_to and assigned_to.lower() not in data.get("assigned", "").lower():
            continue
            
        # Calculate dynamic risk
        assignee_key = data.get("assigned_id") or data.get("assigned")
        workload = workload_map.get(assignee_key, 0)
        data = calculate_task_risk(data, workload)
        
        # Trigger notifications for assigned user if applicable
        if data.get("assigned_id") and data.get("status") not in ["Completed", "Awaiting Approval"]:
            risk_score = data.get("risk_score", 0)
            if risk_score >= 80:
                trigger_notification(db, data["assigned_id"], "DEADLINE RISK", "Deadline Risk", f"Task '{data.get('title')}' is at high risk of delay.\nRisk: {risk_score}%", "/tasks", "High", "🔴")
                
            deadline_str = data.get("deadline", "")
            if deadline_str:
                try:
                    dt = None
                    if "T" in deadline_str or "Z" in deadline_str:
                        dt = datetime.fromisoformat(deadline_str.replace("Z", ""))
                    else:
                        try:
                            dt = datetime.strptime(deadline_str, "%d %B %Y")
                        except ValueError:
                            dt = datetime.strptime(deadline_str, "%Y-%m-%d")
                    if dt:
                        days_left = (dt - datetime.utcnow()).days
                        if days_left < 0:
                            trigger_notification(db, data["assigned_id"], "TASK OVERDUE", "Task Overdue", f"Task '{data.get('title')}' is {abs(days_left)} days overdue.", "/tasks", "High", "🔴")
                except Exception:
                    pass
        
        tasks.append(data)

    return tasks

@router.post("", response_model=TaskResponse)
def create_task(
    task: TaskCreate,
    db: Client = Depends(get_db),
    current_user: User = Depends(check_role([RoleEnum.ADMIN, RoleEnum.HOD]))
):
    task_id = str(uuid.uuid4())
    db_task = task.dict()
    db_task['id'] = task_id
    db_task['created_at'] = datetime.utcnow().isoformat()
    
    # Save to Firestore
    db.collection('tasks').document(task_id).set(db_task)
    
    # Audit Log
    db.collection('activity_logs').document().set({
        "user_id": current_user.id,
        "user_name": current_user.name,
        "action": f"Task Created: {task.title}",
        "category": "task",
        "details": f"New task '{task.title}' assigned to {task.assigned}",
        "timestamp": datetime.utcnow().isoformat()
    })
    
    if task.assigned_id:
        trigger_notification(
            db, 
            task.assigned_id, 
            "ASSIGNMENT", 
            "New Task Assigned", 
            f"New task assigned by HOD:\n{task.title}\nDeadline: {task.deadline or 'No Deadline'}", 
            "/tasks",
            task.priority,
            "🔵"
        )
        
    return db_task

@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: str,
    db: Client = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    doc_ref = db.collection('tasks').document(task_id)
    doc = doc_ref.get()
    
    data = None
    if not doc.exists:
        for t in DEFAULT_TASKS:
            if t["id"] == task_id:
                data = t
                break
        if not data:
            raise HTTPException(status_code=404, detail="Task not found")
    else:
        data = doc.to_dict()
        
    if current_user.role == RoleEnum.FACULTY:
        if data.get("assigned_id") != current_user.id and current_user.name.lower() not in data.get("assigned", "").lower():
            raise HTTPException(status_code=403, detail="Not authorized to view this task")
            
    # Quick dynamic risk calc (without full workload context)
    return calculate_task_risk(data, 1)

@router.put("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: str,
    task_update: TaskUpdate,
    db: Client = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    doc_ref = db.collection('tasks').document(task_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Task not found")
        
    existing_data = doc.to_dict()
    update_data = {k: v for k, v in task_update.dict(exclude_unset=True).items() if v is not None}
    
    if current_user.role == RoleEnum.FACULTY:
        if existing_data.get("assigned_id") != current_user.id and current_user.name.lower() not in existing_data.get("assigned", "").lower():
            raise HTTPException(status_code=403, detail="Not authorized to update this task")
            
        # FACULTY can update status, progress, and subtasks
        allowed_keys = {'status', 'progress', 'subtasks'}
        filtered_update = {k: v for k, v in update_data.items() if k in allowed_keys}
        
        # Merge subtasks properly so they can't overwrite titles
        if 'subtasks' in filtered_update:
            existing_subtasks = existing_data.get('subtasks', [])
            new_subtasks = filtered_update['subtasks']
            merged_subtasks = []
            
            # Map existing by ID
            ext_map = {st['id']: st for st in existing_subtasks}
            for new_st in new_subtasks:
                if new_st['id'] in ext_map:
                    merged_st = ext_map[new_st['id']].copy()
                    merged_st['completed'] = new_st.get('completed', False)
                    merged_subtasks.append(merged_st)
            
            filtered_update['subtasks'] = merged_subtasks
            
            # Auto-calculate progress
            if merged_subtasks:
                completed = sum(1 for st in merged_subtasks if st['completed'])
                prog_val = int((completed / len(merged_subtasks)) * 100)
                filtered_update['progress'] = f"{prog_val}%"
        
        # Handle auto-completion logic if require_approval is false
        if filtered_update.get("progress") == "100%" and existing_data.get("progress") != "100%":
            if existing_data.get("require_approval", False):
                filtered_update["status"] = "Awaiting Approval"
                trigger_notification(db, "department", "APPROVAL", "Approval Request", f"{existing_data.get('assigned')} submitted {existing_data.get('title')} for approval.", "/approvals", "High", "🟣")
            else:
                filtered_update["status"] = "Completed"
                
        doc_ref.update(filtered_update)
        return doc_ref.get().to_dict()
        
    # Admin/HOD can update anything
    # If they update subtasks, auto-calculate progress too
    if 'subtasks' in update_data:
        subs = update_data['subtasks']
        if subs:
            completed = sum(1 for st in subs if st['completed'])
            prog_val = int((completed / len(subs)) * 100)
            update_data['progress'] = f"{prog_val}%"
            if prog_val == 100:
                update_data['status'] = "Awaiting Approval" if update_data.get("require_approval", existing_data.get("require_approval", False)) else "Completed"
                if update_data['status'] == "Awaiting Approval":
                    trigger_notification(db, "department", "APPROVAL", "Approval Request", f"{existing_data.get('assigned')} submitted {existing_data.get('title')} for approval.", "/approvals", "High", "🟣")
            
    # Check status changes by HOD
    if "status" in update_data and update_data["status"] != existing_data.get("status"):
        new_status = update_data["status"]
        if new_status == "Completed" and existing_data.get("status") == "Awaiting Approval":
            # Approved
            if existing_data.get("assigned_id"):
                trigger_notification(db, existing_data.get("assigned_id"), "TASK APPROVED", "Task Approved", f"Your task '{existing_data.get('title')}' was approved by HOD.", "/tasks", "Low", "🟢")
        elif new_status != "Completed" and existing_data.get("status") == "Awaiting Approval":
            # Rejected / Revision
            if existing_data.get("assigned_id"):
                trigger_notification(db, existing_data.get("assigned_id"), "REVISION REQUIRED", "Revision Required", f"HOD requested changes to '{existing_data.get('title')}'.", "/tasks", "High", "🔴")

    doc_ref.update(update_data)
    return doc_ref.get().to_dict()

@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: str,
    db: Client = Depends(get_db),
    current_user: User = Depends(check_role([RoleEnum.ADMIN, RoleEnum.HOD]))
):
    doc_ref = db.collection('tasks').document(task_id)
    if not doc_ref.get().exists:
        raise HTTPException(status_code=404, detail="Task not found")
        
    doc_ref.delete()
    return None
