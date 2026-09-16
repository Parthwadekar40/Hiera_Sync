from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from google.cloud.firestore import Client
from app.database.session import get_db
from app.schemas.schemas import GlobalSearchResponse, SearchResultItem
from app.auth.permissions import get_current_active_user
from app.models.models import User

router = APIRouter()

SUGGESTIONS = [
    {"id": "sug_1", "title": "AI Lab Maintenance", "type": "task"},
    {"id": "sug_2", "title": "Final Year Project Review", "type": "task"},
    {"id": "sug_3", "title": "Student Research Tracking", "type": "task"},
    {"id": "sug_4", "title": "Machine Learning Workshop", "type": "event"},
    {"id": "sug_5", "title": "Cyber Security Seminar", "type": "event"},
    {"id": "sug_6", "title": "Faculty Profile", "type": "faculty"},
    {"id": "sug_7", "title": "Notifications", "type": "notification"}
]

@router.get("", response_model=GlobalSearchResponse)
def global_search(
    q: Optional[str] = Query(None),
    db: Client = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if not q or len(q.strip()) == 0:
        return {"query": "", "results": SUGGESTIONS}

    query_str = q.strip().lower()
    results: List[SearchResultItem] = []

    # 1. Search Users / Faculty
    users_ref = db.collection('users')
    for u in users_ref.stream():
        data = u.to_dict()
        name = data.get("name", "")
        if query_str in name.lower():
            results.append(SearchResultItem(id=u.id, title=f"Faculty: {name}", type="faculty"))

    # 2. Search Tasks
    tasks_ref = db.collection('tasks')
    for t in tasks_ref.stream():
        data = t.to_dict()
        title = data.get("title", "")
        if query_str in title.lower():
            results.append(SearchResultItem(id=t.id, title=f"Task: {title}", type="task"))

    # 3. Search Events
    events_ref = db.collection('events')
    for e in events_ref.stream():
        data = e.to_dict()
        title = data.get("title", "")
        if query_str in title.lower():
            results.append(SearchResultItem(id=e.id, title=f"Event: {title}", type="event"))

    # Fallback to static suggestions if Firestore results are empty
    if not results:
        for item in SUGGESTIONS:
            if query_str in item["title"].lower():
                results.append(SearchResultItem(id=item["id"], title=item["title"], type=item["type"]))

    return {"query": q, "results": results}
