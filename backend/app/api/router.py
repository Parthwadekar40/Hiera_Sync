from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.events import router as events_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.approvals import router as approvals_router
from app.api.v1.ai import router as ai_router
from app.api.v1.files import router as files_router
from app.api.v1.reports import router as reports_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.settings import router as settings_router
from app.api.v1.search import router as search_router
from app.api.v1.test import router as test_router
from app.api.v1.departments import router as departments_router
from app.api.v1.join import router as join_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.requests import router as requests_router
from app.api.v1.comments import router as comments_router
from app.api.v1.attachments import router as attachments_router
from app.api.v1.goals import router as goals_router
from app.api.v1.risk import router as risk_router
from app.api.v1.workflow import router as workflow_router
from app.api.v1.metrics import router as metrics_router
from app.api.v1.channels import router as channels_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(events_router, prefix="/events", tags=["events"])
api_router.include_router(tasks_router, prefix="/tasks", tags=["tasks"])
api_router.include_router(approvals_router, prefix="/approvals", tags=["approvals"])
api_router.include_router(ai_router, prefix="/ai", tags=["ai"])
api_router.include_router(files_router, prefix="/files", tags=["files"])
api_router.include_router(reports_router, prefix="/reports", tags=["reports"])
api_router.include_router(notifications_router, prefix="/notifications", tags=["notifications"])
api_router.include_router(settings_router, prefix="/settings", tags=["settings"])
api_router.include_router(search_router, prefix="/search", tags=["search"])
api_router.include_router(departments_router, prefix="/departments", tags=["departments"])
api_router.include_router(join_router, prefix="/join", tags=["join"])
api_router.include_router(analytics_router, prefix="/analytics", tags=["analytics"])
api_router.include_router(requests_router, prefix="/task-requests", tags=["requests"])
api_router.include_router(comments_router, prefix="/comments", tags=["comments"])
api_router.include_router(attachments_router, prefix="/attachments", tags=["attachments"])
api_router.include_router(goals_router, prefix="/goals", tags=["goals"])
api_router.include_router(risk_router, prefix="/risk", tags=["risk-engine"])
api_router.include_router(workflow_router, prefix="/workflow", tags=["workflow"])
api_router.include_router(metrics_router, prefix="/metrics", tags=["metrics"])
api_router.include_router(channels_router, prefix="/channels", tags=["channels"])
api_router.include_router(test_router)