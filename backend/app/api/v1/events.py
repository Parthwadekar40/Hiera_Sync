from datetime import date, datetime, timedelta
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from google.cloud.firestore import Client

from app.auth.permissions import check_role, get_current_active_user
from app.database.session import get_db
from app.models.models import RoleEnum, User
from app.schemas.schemas import EventCreate, EventResponse, EventUpdate
from app.utils.dates import to_iso_date
from app.utils.logging import logger

router = APIRouter()

MANAGE_ROLES = [RoleEnum.ADMIN, RoleEnum.HOD]

SEED_TITLES = [
    ("Course File Verification — TYAIML", "Department Activity", "Mrs. Neha Gurnani"),
    ("Minor Project Internal Review", "Academic", "Dr. Animesh Tayal"),
    ("AI/ML Research Paper Discussion", "Research", "Dr. Bhushan Mahendra Manjre"),
    ("Faculty Coordination Meeting", "Meeting", "Ms. Sweta Arun Bokade"),
    ("Hands-on Workshop: LLM Fine-tuning", "Workshop", "Dr. Animesh Tayal"),
    ("Mid-Semester Assessment — SYAIML", "Academic", "Ms. Preeti Deshmukh"),
    ("Industry Visit — Nagpur AI Park", "Department Activity", "Mrs. Neha Gurnani"),
    ("Final Year Project Review — Phase 2", "Academic", "Dr. Bhushan Mahendra Manjre"),
]


def _default_events() -> List[dict]:
    """Sample activities spread across the current month.

    Dates are generated relative to today and stored as ISO (YYYY-MM-DD):
    hard-coded strings such as "05 August 2026" could not be parsed by the
    calendar component, so the department schedule always looked empty.
    """
    today = date.today()
    events = []
    for index, (title, activity_type, person) in enumerate(SEED_TITLES):
        day = today + timedelta(days=(index * 3) - 4)
        timed = index % 3 == 1
        events.append(
            {
                "id": f"evt_seed_{index + 1}",
                "title": title,
                "date": day.isoformat(),
                "type": activity_type,
                "person": person,
                "description": "Auto-seeded department activity — edit or delete it from the calendar.",
                "location": "Seminar Hall" if index % 2 == 0 else "AI Lab",
                "status": "Completed" if day < today else ("Assigned" if index % 4 == 0 else "Planned"),
                "priority": "High" if index % 3 == 0 else "Medium",
                "start_time": "10:00" if timed else None,
                "end_time": "13:00" if timed else None,
                "all_day": not timed,
                "notify_assignee": False,
                "creator_id": "system",
                "created_at": datetime.utcnow().isoformat(),
            }
        )
    return events


def _notify_assignee(db: Client, event: dict, actor: User) -> None:
    """Queue a reminder notification for the responsible faculty member."""
    person = (event.get("person") or "").strip()
    if not person:
        return

    user_id = "department"
    try:
        matches = list(
            db.collection("users").where("name", "==", person).limit(1).stream()
        )
        if matches:
            user_id = matches[0].to_dict().get("id") or matches[0].id
    except Exception as exc:  # naming mismatch or Firestore rules — stay department-wide
        logger.warning(f"Could not resolve faculty '{person}' for reminder: {exc}")

    when = to_iso_date(event.get("date"))
    time_text = f" at {event['start_time']}" if event.get("start_time") else ""
    notification = {
        "id": f"notif_{uuid.uuid4().hex[:8]}",
        "user_id": user_id,
        "title": f"New activity: {event.get('title', 'Untitled')}",
        "message": f"{when}{time_text} · {event.get('location') or 'Venue to be confirmed'} — assigned by {actor.name}",
        "type": "Calendar",
        "priority": event.get("priority") or "Medium",
        "target_route": "/calendar",
        "icon": "📅",
        "status": "New",
        "time": "Just now",
        "is_read": False,
        "created_at": datetime.utcnow().isoformat(),
    }
    db.collection("notifications").document(notification["id"]).set(notification)


@router.get("", response_model=List[EventResponse])
def get_events(
    date_from: Optional[str] = Query(None, description="Inclusive ISO start date"),
    date_to: Optional[str] = Query(None, description="Inclusive ISO end date"),
    type: Optional[str] = Query(None, description="Filter by activity type"),
    person: Optional[str] = Query(None, description="Filter by responsible faculty"),
    db: Client = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    collection = db.collection("events")
    docs = list(collection.stream())

    if docs:
        events = [doc.to_dict() for doc in docs]
    else:
        # First run on an empty collection: persist the samples so their ids are
        # real documents and can be edited or deleted from the UI.
        events = _default_events()
        try:
            for event in events:
                collection.document(event["id"]).set(event)
        except Exception as exc:
            logger.warning(f"Could not seed sample events (read-only fallback): {exc}")

    if type:
        events = [event for event in events if event.get("type") == type]
    if person:
        events = [event for event in events if event.get("person") == person]
    if date_from:
        start = to_iso_date(date_from)
        events = [event for event in events if to_iso_date(event.get("date")) >= start]
    if date_to:
        end = to_iso_date(date_to)
        events = [event for event in events if to_iso_date(event.get("date")) <= end]

    events.sort(key=lambda event: to_iso_date(event.get("date")))
    return events


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
def create_event(
    event: EventCreate,
    db: Client = Depends(get_db),
    current_user: User = Depends(check_role(MANAGE_ROLES)),
):
    event_id = str(uuid.uuid4())
    db_event = event.model_dump()
    db_event["id"] = event_id
    db_event["creator_id"] = current_user.id
    db_event["created_at"] = datetime.utcnow().isoformat()
    notify = db_event.pop("notify_assignee", False)

    if not db_event["all_day"] and db_event.get("start_time") and db_event.get("end_time"):
        if db_event["end_time"] <= db_event["start_time"]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="End time must be after the start time.",
            )

    db.collection("events").document(event_id).set(db_event)

    if notify:
        try:
            _notify_assignee(db, db_event, current_user)
        except Exception as exc:
            logger.warning(f"Activity created but reminder could not be queued: {exc}")

    return {**db_event, "notify_assignee": notify}


@router.get("/{event_id}", response_model=EventResponse)
def get_event(
    event_id: str,
    db: Client = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    doc = db.collection("events").document(event_id).get()
    if doc.exists:
        return doc.to_dict()

    for event in _default_events():
        if event["id"] == event_id:
            return event

    raise HTTPException(status_code=404, detail="Event not found")


CLEARABLE = {"description", "location", "start_time", "end_time"}


@router.put("/{event_id}", response_model=EventResponse)
def update_event(
    event_id: str,
    event_update: EventUpdate,
    db: Client = Depends(get_db),
    current_user: User = Depends(check_role(MANAGE_ROLES)),
):
    """Edit an activity. Restricted to the HOD desk, matching the UI."""
    doc_ref = db.collection("events").document(event_id)

    # Reschedule attempts on seeded data write the document into existence so the
    # change survives a page reload instead of silently reverting.
    if not doc_ref.get().exists:
        raise HTTPException(status_code=404, detail="Event not found")

    updates = {
        key: value
        for key, value in event_update.model_dump(exclude_unset=True).items()
        if value is not None or key in CLEARABLE
    }
    if not updates:
        return doc_ref.get().to_dict()

    doc_ref.update(updates)
    return doc_ref.get().to_dict()


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(
    event_id: str,
    db: Client = Depends(get_db),
    current_user: User = Depends(check_role(MANAGE_ROLES)),
):
    """Delete an activity. Restricted to the HOD desk — it used to accept any
    signed-in user, which let faculty wipe department activities."""
    doc_ref = db.collection("events").document(event_id)
    if not doc_ref.get().exists:
        raise HTTPException(status_code=404, detail="Event not found")

    doc_ref.delete()
    return None


@router.post("/{event_id}/remind", response_model=dict)
def remind_assignee(
    event_id: str,
    db: Client = Depends(get_db),
    current_user: User = Depends(check_role(MANAGE_ROLES)),
):
    """Send the assigned faculty a reminder notification for this activity."""
    doc_ref = db.collection("events").document(event_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Event not found")

    event = doc.to_dict()
    if not event.get("person"):
        raise HTTPException(status_code=400, detail="This activity has no responsible faculty.")

    _notify_assignee(db, event, current_user)
    return {"message": f"Reminder queued for {event['person']}."}
