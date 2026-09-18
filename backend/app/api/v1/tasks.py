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
from app.engine import risk as R
from app.db.compat import normalize_task

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

def _lightweight_context(task: Dict[str, Any], faculty_workload: int) -> R.RiskContext:
    """Standalone scoring when no shared context is supplied (v1 call sites)."""
    ctx = R.RiskContext()
    key = str(task.get("assigned_id") or task.get("assigned") or "")
    load = float(faculty_workload or 0)
    ctx.workload[key] = int(load)
    ctx.weighted_load[key] = load * R.priority_weight(task.get("priority"))
    ctx.capacity[key] = 4.0
    return ctx


def calculate_task_risk(task: Dict[str, Any], faculty_workload: int = 0, ctx: Optional[R.RiskContext] = None) -> Dict[str, Any]:
    """Heuristic AI deadline-risk engine (0-100, LOW/MEDIUM/HIGH).

    Delegates to app.engine.risk (8 weighted, explainable factors) and writes the
    fields the v1 UI reads: risk_score, risk_level, risk_factors - plus the
    explanation, drivers, delay probability and recommended action from v2.
    """
    assessment = R.assess(task, ctx or _lightweight_context(task, faculty_workload))
    task["risk_score"] = assessment["risk_score"]
    task["risk_level"] = assessment["risk_level"]
    strong = [f["evidence"] for f in assessment["factors"] if f["sub_score"] >= 12]
    task["risk_factors"] = strong or [assessment["explanation"]]
    task["risk_drivers"] = assessment["drivers"]
    task["risk_explanation"] = assessment["explanation"]
    task["delay_probability"] = assessment["delay_probability"]
    task["risk_confidence"] = assessment["confidence"]
    task["risk_projected_completion"] = assessment["projected_completion"]
    task["risk_recommended_action"] = (assessment["recommendations"] or [None])[0]
    task["risk_assessment"] = assessment
    return task


@router.get("/", response_model=List[TaskResponse])
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

    shared_ctx = R.build_context(db, tasks=all_raw_tasks)

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
        data = calculate_task_risk(data, workload, ctx=shared_ctx)
        data = normalize_task(data, assessment=data.get("risk_assessment"))
        
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

@router.post("/", response_model=TaskResponse)
def create_task(
    task: TaskCreate,
    db: Client = Depends(get_db),
    current_user: User = Depends(check_role([RoleEnum.ADMIN, RoleEnum.HOD]))
):
    task_id = str(uuid.uuid4())
    db_task = task.dict()
    db_task['id'] = task_id
    db_task['created_at'] = datetime.utcnow().isoformat()
    
    # Save to Firestore (with the initial risk assessment persisted for badges)
    db_task = normalize_task(db_task, assessment=R.assess(db_task, R.build_context(db, tasks=[db_task])))
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
    
    initial_risk = float(db_task.get("risk_score") or 0)
    if initial_risk >= 55 and task.assigned_id:
        trigger_notification(
            db,
            task.assigned_id,
            "DEADLINE RISK",
            "Assigned task already at risk",
            f"'{task.title}' was created with a risk score of {initial_risk:.0f}/100 "
            f"({db_task.get('risk_level')}).\n{db_task.get('risk_explanation', '')}",
            "/tasks",
            "High",
            "🟠",
        )

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
