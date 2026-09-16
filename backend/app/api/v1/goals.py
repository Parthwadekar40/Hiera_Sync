import uuid
from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from google.cloud.firestore import Client
from app.database.session import get_db
from app.schemas.schemas import (
    DepartmentGoalCreate, DepartmentGoalUpdate, DepartmentGoalResponse,
    GoalMilestoneCreate, GoalMilestoneUpdate, GoalMilestoneResponse
)
from app.auth.permissions import get_current_active_user, check_role
from app.models.models import User, RoleEnum

router = APIRouter()

@router.get("", response_model=List[DepartmentGoalResponse])
def get_goals(
    db: Client = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    goals_ref = db.collection('department_goals')
    docs = list(goals_ref.stream())
    
    goals = []
    for doc in docs:
        goal_data = doc.to_dict()
        # Fetch milestones
        m_ref = db.collection('goal_milestones').where('goal_id', '==', goal_data['id'])
        m_docs = list(m_ref.stream())
        milestones = [m.to_dict() for m in m_docs]
        milestones.sort(key=lambda x: x.get('order', 0))
        goal_data['milestones'] = milestones
        goals.append(goal_data)
        
    return goals

@router.post("", response_model=DepartmentGoalResponse)
def create_goal(
    goal: DepartmentGoalCreate,
    db: Client = Depends(get_db),
    current_user: User = Depends(check_role([RoleEnum.ADMIN, RoleEnum.HOD]))
):
    goal_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    
    db_goal = goal.dict()
    db_goal['id'] = goal_id
    db_goal['owner_id'] = current_user.id
    db_goal['created_at'] = now
    db_goal['updated_at'] = now
    db_goal['status'] = "NOT_STARTED"
    
    db.collection('department_goals').document(goal_id).set(db_goal)
    db_goal['milestones'] = []
    return db_goal

@router.get("/{goal_id}", response_model=DepartmentGoalResponse)
def get_goal(
    goal_id: str,
    db: Client = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    doc_ref = db.collection('department_goals').document(goal_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Goal not found")
        
    goal_data = doc.to_dict()
    
    m_ref = db.collection('goal_milestones').where('goal_id', '==', goal_id)
    m_docs = list(m_ref.stream())
    milestones = [m.to_dict() for m in m_docs]
    milestones.sort(key=lambda x: x.get('order', 0))
    goal_data['milestones'] = milestones
    
    return goal_data

@router.patch("/{goal_id}", response_model=DepartmentGoalResponse)
def update_goal(
    goal_id: str,
    update_data: DepartmentGoalUpdate,
    db: Client = Depends(get_db),
    current_user: User = Depends(check_role([RoleEnum.ADMIN, RoleEnum.HOD]))
):
    doc_ref = db.collection('department_goals').document(goal_id)
    if not doc_ref.get().exists:
        raise HTTPException(status_code=404, detail="Goal not found")
        
    update_dict = {k: v for k, v in update_data.dict(exclude_unset=True).items() if v is not None}
    update_dict['updated_at'] = datetime.utcnow().isoformat()
    
    doc_ref.update(update_dict)
    return get_goal(goal_id, db, current_user)

@router.delete("/{goal_id}")
def delete_goal(
    goal_id: str,
    db: Client = Depends(get_db),
    current_user: User = Depends(check_role([RoleEnum.ADMIN, RoleEnum.HOD]))
):
    doc_ref = db.collection('department_goals').document(goal_id)
    if not doc_ref.get().exists:
        raise HTTPException(status_code=404, detail="Goal not found")
        
    # Delete milestones
    m_ref = db.collection('goal_milestones').where('goal_id', '==', goal_id)
    for m in m_ref.stream():
        db.collection('goal_milestones').document(m.id).delete()
        
    doc_ref.delete()
    return {"message": "Goal deleted successfully"}

# Milestones
@router.post("/{goal_id}/milestones", response_model=GoalMilestoneResponse)
def create_milestone(
    goal_id: str,
    milestone: GoalMilestoneCreate,
    db: Client = Depends(get_db),
    current_user: User = Depends(check_role([RoleEnum.ADMIN, RoleEnum.HOD]))
):
    doc_ref = db.collection('department_goals').document(goal_id)
    if not doc_ref.get().exists:
        raise HTTPException(status_code=404, detail="Goal not found")
        
    m_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    
    db_m = milestone.dict()
    db_m['id'] = m_id
    db_m['goal_id'] = goal_id
    db_m['created_at'] = now
    db_m['updated_at'] = now
    db_m['completed_at'] = None
    db_m['status'] = milestone.status or "PENDING"
    
    db.collection('goal_milestones').document(m_id).set(db_m)
    return db_m

@router.patch("/{goal_id}/milestones/{milestone_id}", response_model=GoalMilestoneResponse)
def update_milestone(
    goal_id: str,
    milestone_id: str,
    update_data: GoalMilestoneUpdate,
    db: Client = Depends(get_db),
    current_user: User = Depends(check_role([RoleEnum.ADMIN, RoleEnum.HOD]))
):
    doc_ref = db.collection('goal_milestones').document(milestone_id)
    doc = doc_ref.get()
    if not doc.exists or doc.to_dict().get('goal_id') != goal_id:
        raise HTTPException(status_code=404, detail="Milestone not found")
        
    update_dict = {k: v for k, v in update_data.dict(exclude_unset=True).items() if v is not None}
    update_dict['updated_at'] = datetime.utcnow().isoformat()
    
    if update_dict.get('status') == "COMPLETED" and doc.to_dict().get('status') != "COMPLETED":
        update_dict['completed_at'] = datetime.utcnow().isoformat()
    elif update_dict.get('status') in ["PENDING", "IN_PROGRESS"]:
        update_dict['completed_at'] = None
        
    doc_ref.update(update_dict)
    return doc_ref.get().to_dict()

@router.delete("/{goal_id}/milestones/{milestone_id}")
def delete_milestone(
    goal_id: str,
    milestone_id: str,
    db: Client = Depends(get_db),
    current_user: User = Depends(check_role([RoleEnum.ADMIN, RoleEnum.HOD]))
):
    doc_ref = db.collection('goal_milestones').document(milestone_id)
    doc = doc_ref.get()
    if not doc.exists or doc.to_dict().get('goal_id') != goal_id:
        raise HTTPException(status_code=404, detail="Milestone not found")
        
    doc_ref.delete()
    return {"message": "Milestone deleted successfully"}
