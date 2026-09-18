from typing import List, Optional
from datetime import datetime
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from google.cloud.firestore import Client
from app.database.session import get_db
from app.schemas.schemas import NotificationCreate, NotificationResponse, UnreadCountResponse
from app.auth.permissions import get_current_active_user
from app.models.models import User

router = APIRouter()

DEFAULT_NOTIFICATIONS = [
    {
        "id": "notif_1",
        "title": "New Task Assigned",
        "message": "AI Lab Maintenance task assigned to Mrs. Neha Gurnani",
        "time": "10 minutes ago",
        "type": "Task",
        "priority": "High",
        "target_route": "/tasks",
        "icon": "📋",
        "status": "New",
        "is_read": False,
        "created_at": "2026-08-02T22:35:00Z"
    },
    {
        "id": "notif_2",
        "title": "Approval Pending",
        "message": "Final Year Project Review approval is waiting for review",
        "time": "1 hour ago",
        "type": "Approval",
        "priority": "High",
        "target_route": "/approvals",
        "icon": "✅",
        "status": "Pending",
        "is_read": False,
        "created_at": "2026-08-02T21:45:00Z"
    },
    {
        "id": "notif_3",
        "title": "Deadline Reminder",
        "message": "Machine Learning Workshop deadline is near",
        "time": "Today",
        "type": "Calendar",
        "priority": "Medium",
        "target_route": "/calendar",
        "icon": "⏰",
        "status": "Important",
        "is_read": False,
        "created_at": "2026-08-02T18:00:00Z"
    },
    {
        "id": "notif_4",
        "title": "Faculty Activity Update",
        "message": "Dr. Bhushan Mahendra Manjre updated research tracking status",
        "time": "Today",
        "type": "Employees",
        "priority": "Low",
        "target_route": "/employees",
        "icon": "👨‍🏫",
        "status": "Updated",
        "is_read": True,
        "created_at": "2026-08-02T15:30:00Z"
    },
    {
        "id": "notif_5",
        "title": "AI Recommendation",
        "message": "HieraSync AI suggested completing pending approvals first",
        "time": "Today",
        "type": "AI",
        "priority": "Medium",
        "target_route": "/ai",
        "icon": "🤖",
        "status": "AI Alert",
        "is_read": True,
        "created_at": "2026-08-02T12:00:00Z"
    }
]

@router.get("/", response_model=List[NotificationResponse])
def get_notifications(
    db: Client = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    notifs_ref = db.collection('notifications')
    docs = list(notifs_ref.where('user_id', 'in', [current_user.id, 'department']).stream())
    notifications = []
    if docs:
        for doc in docs:
            notifications.append(doc.to_dict())
    else:
        notifications = DEFAULT_NOTIFICATIONS
    return notifications

@router.get("/unread-count", response_model=UnreadCountResponse)
def get_unread_count(
    db: Client = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    notifs_ref = db.collection('notifications')
    docs = list(notifs_ref.where('user_id', 'in', [current_user.id, 'department']).stream())
    if docs:
        unread = sum(1 for d in docs if not d.to_dict().get("is_read", False))
    else:
        unread = sum(1 for d in DEFAULT_NOTIFICATIONS if not d.get("is_read", False))
    return {"unread_count": unread}

@router.post("/", response_model=NotificationResponse)
def create_notification(
    notification: NotificationCreate,
    db: Client = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    notif_id = f"notif_{uuid.uuid4().hex[:8]}"
    db_notif = notification.dict()
    db_notif["id"] = notif_id
    db_notif["user_id"] = current_user.id
    db_notif["created_at"] = datetime.utcnow().isoformat()
    if not db_notif.get("time"):
        db_notif["time"] = "Just now"
    
    db.collection('notifications').document(notif_id).set(db_notif)
    return db_notif

@router.put("/{notification_id}/read", response_model=NotificationResponse)
def mark_read(
    notification_id: str,
    db: Client = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    doc_ref = db.collection('notifications').document(notification_id)
    doc = doc_ref.get()
    if not doc.exists:
        for n in DEFAULT_NOTIFICATIONS:
            if n["id"] == notification_id:
                n["is_read"] = True
                n["status"] = "Read"
                return n
        raise HTTPException(status_code=404, detail="Notification not found")
    
    doc_ref.update({"is_read": True, "status": "Read"})
    return doc_ref.get().to_dict()

@router.put("/{notification_id}/unread", response_model=NotificationResponse)
def mark_unread(
    notification_id: str,
    db: Client = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    doc_ref = db.collection('notifications').document(notification_id)
    doc = doc_ref.get()
    if not doc.exists:
        for n in DEFAULT_NOTIFICATIONS:
            if n["id"] == notification_id:
                n["is_read"] = False
                n["status"] = "Unread"
                return n
        raise HTTPException(status_code=404, detail="Notification not found")
    
    doc_ref.update({"is_read": False, "status": "Unread"})
    return doc_ref.get().to_dict()

@router.put("/read-all")
def mark_all_read(
    db: Client = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    notifs_ref = db.collection('notifications')
    docs = list(notifs_ref.where('user_id', 'in', [current_user.id, 'department']).stream())
    if docs:
        for doc in docs:
            doc.reference.update({"is_read": True, "status": "Read"})
    else:
        for n in DEFAULT_NOTIFICATIONS:
            n["is_read"] = True
            n["status"] = "Read"
    return {"message": "All notifications marked as read."}

@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notification(
    notification_id: str,
    db: Client = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    doc_ref = db.collection('notifications').document(notification_id)
    if doc_ref.get().exists:
        doc_ref.delete()
        return None
    
    # Check default notifications
    global DEFAULT_NOTIFICATIONS
    for i, n in enumerate(DEFAULT_NOTIFICATIONS):
        if n["id"] == notification_id:
            DEFAULT_NOTIFICATIONS.pop(i)
            return None
            
    raise HTTPException(status_code=404, detail="Notification not found")

def trigger_notification(
    db: Client,
    user_id: str,
    notif_type: str,
    title: str,
    message: str,
    target_route: str = "/tasks",
    priority: str = "Medium",
    icon: str = "🔔"
):
    """Legacy entry point kept for the existing routers.

    It now delegates to the multi-channel engine, so every v1 call site
    (tasks, join requests, approvals, goals) transparently gains in-app +
    e-mail + SMS + WhatsApp fan-out, duplicate suppression, quiet hours and
    retry/backoff without any change to its signature.
    """
    from app.notify.engine import trigger_notification as _engine_trigger

    return _engine_trigger(db, user_id, notif_type, title, message, target_route, priority, icon)
