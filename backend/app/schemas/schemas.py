from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Dict, List, Optional
from datetime import datetime
from app.models.models import RoleEnum, PriorityEnum, TaskStatusEnum

# User Schemas
class UserBase(BaseModel):
    name: str
    email: EmailStr
    role: RoleEnum = RoleEnum.FACULTY
    department_id: Optional[str] = None
    designation: Optional[str] = "Assistant Professor"
    area_of_interest: Optional[str] = None
    joining_date: Optional[str] = "Not Available"
    association: Optional[str] = "Regular"
    avatar_url: Optional[str] = None

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: str
    status: str
    
    class Config:
        from_attributes = True

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class EmployeeResponse(UserBase):
    id: str
    status: str = "ACTIVE"
    
    class Config:
        from_attributes = True

class EmployeeCreate(UserBase):
    password: Optional[str] = "Sbjit@123"

class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    designation: Optional[str] = None
    area_of_interest: Optional[str] = None
    joining_date: Optional[str] = None
    association: Optional[str] = None
    role: Optional[RoleEnum] = None
    avatar_url: Optional[str] = None

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

# Token Schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

# Dashboard & Report Schemas
class DashboardStatsResponse(BaseModel):
    employees_count: int
    pending_tasks_count: int
    high_priority_tasks: int
    approvals_count: int
    waiting_approvals: int
    ai_productivity: str = "92%"
    workflow_progress: float = 75.0

class ActivityLogResponse(BaseModel):
    id: str
    message: str
    category: Optional[str] = "task"
    icon: Optional[str] = "✅"
    timestamp: Optional[str] = None

class DepartmentReportSummary(BaseModel):
    total_tasks: int
    completed_tasks: int
    active_faculty: int
    ai_efficiency: str = "92%"
    completion_rate: str = "66%"

# Event Schemas
ACTIVITY_TYPES = {
    "Academic", "Meeting", "Workshop", "Department Activity", "Research"
}
ACTIVITY_STATUSES = {"Planned", "Assigned", "Review", "Completed"}
ACTIVITY_PRIORITIES = {"Low", "Medium", "High"}


class EventCreate(BaseModel):
    title: str
    date: str
    type: str = "Academic"
    person: str
    description: Optional[str] = None
    location: Optional[str] = None
    status: str = "Planned"
    priority: str = "Medium"
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    all_day: bool = True
    notify_assignee: bool = False

    @field_validator("date")
    @classmethod
    def _normalise_date(cls, value: str) -> str:
        from app.utils.dates import to_iso_date

        return to_iso_date(value)

    @field_validator("type")
    @classmethod
    def _valid_type(cls, value: str) -> str:
        return value if value in ACTIVITY_TYPES else "Academic"

    @field_validator("status")
    @classmethod
    def _valid_status(cls, value: str) -> str:
        return value if value in ACTIVITY_STATUSES else "Planned"

    @field_validator("priority")
    @classmethod
    def _valid_priority(cls, value: str) -> str:
        return value if value in ACTIVITY_PRIORITIES else "Medium"

    @field_validator("start_time", "end_time")
    @classmethod
    def _valid_time(cls, value: Optional[str]) -> Optional[str]:
        from app.utils.dates import clean_time

        return clean_time(value)


class EventUpdate(BaseModel):
    title: Optional[str] = None
    date: Optional[str] = None
    type: Optional[str] = None
    person: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    all_day: Optional[bool] = None

    @field_validator("date")
    @classmethod
    def _normalise_date(cls, value: Optional[str]) -> Optional[str]:
        from app.utils.dates import to_iso_date

        return to_iso_date(value) if value else None

    @field_validator("start_time", "end_time")
    @classmethod
    def _valid_time(cls, value: Optional[str]) -> Optional[str]:
        from app.utils.dates import clean_time

        return clean_time(value)


class EventResponse(EventCreate):
    # Legacy activity documents may predate some of these fields; defaults keep
    # the collection readable instead of failing the response model.
    id: str
    title: str = "Untitled activity"
    date: str = ""
    person: str = ""
    creator_id: Optional[str] = "admin"
    created_at: Optional[str] = None

    class Config:
        from_attributes = True

# Task Schemas
class TaskRequestBase(BaseModel):
    title: str
    description: str
    category: str = "General"
    priority: str = "Medium"
    suggested_deadline: str
    estimated_effort: Optional[str] = None
    additional_notes: Optional[str] = None

class TaskRequestCreate(TaskRequestBase):
    pass

class TaskRequestUpdate(BaseModel):
    status: Optional[str] = None # PENDING, APPROVED, REJECTED
    rejection_reason: Optional[str] = None
    created_task_id: Optional[str] = None

class TaskRequestResponse(TaskRequestBase):
    id: str
    requester_id: str
    requester_name: str
    status: str
    created_at: str
    reviewed_at: Optional[str] = None
    reviewed_by: Optional[str] = None
    rejection_reason: Optional[str] = None
    created_task_id: Optional[str] = None

class TaskCommentCreate(BaseModel):
    content: str
    mentions: List[str] = Field(default_factory=list)

class TaskCommentResponse(TaskCommentCreate):
    id: str
    task_id: str
    author_id: str
    author_name: str
    created_at: str
    updated_at: str

class TaskAttachmentBase(BaseModel):
    file_name: str
    file_type: str
    file_size: int

class TaskAttachmentCreate(TaskAttachmentBase):
    storage_path: str

class TaskAttachmentResponse(TaskAttachmentCreate):
    id: str
    task_id: str
    uploaded_by: str
    created_at: str

class GoalMilestoneBase(BaseModel):
    title: str
    description: str
    due_date: str
    order: int
    status: str = "PENDING"

class GoalMilestoneCreate(GoalMilestoneBase):
    pass

class GoalMilestoneUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[str] = None
    order: Optional[int] = None
    status: Optional[str] = None
    completed_at: Optional[str] = None

class GoalMilestoneResponse(GoalMilestoneBase):
    id: str
    goal_id: str
    completed_at: Optional[str] = None
    created_at: str
    updated_at: str

class DepartmentGoalBase(BaseModel):
    title: str
    description: str
    category: str = "General"
    start_date: str
    target_date: str
    status: str = "NOT_STARTED"

class DepartmentGoalCreate(DepartmentGoalBase):
    pass

class DepartmentGoalUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    start_date: Optional[str] = None
    target_date: Optional[str] = None
    status: Optional[str] = None

class DepartmentGoalResponse(DepartmentGoalBase):
    id: str
    owner_id: str
    created_at: str
    updated_at: str
    milestones: List[GoalMilestoneResponse] = Field(default_factory=list)

class Subtask(BaseModel):
    id: str
    title: str
    completed: bool = False

class TaskCreate(BaseModel):
    title: str
    assigned: str
    deadline: str
    priority: str = "High"
    status: Optional[str] = "Pending"
    progress: Optional[str] = "0%"
    description: Optional[str] = None
    category: Optional[str] = "General"
    start_date: Optional[str] = None
    deadline_time: Optional[str] = None
    estimated_effort: Optional[str] = None
    reminder: Optional[str] = None
    require_approval: Optional[bool] = False
    assigned_id: Optional[str] = None
    subtasks: List[Subtask] = Field(default_factory=list)
    goal_id: Optional[str] = None

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    assigned: Optional[str] = None
    deadline: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    progress: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    start_date: Optional[str] = None
    deadline_time: Optional[str] = None
    estimated_effort: Optional[str] = None
    reminder: Optional[str] = None
    require_approval: Optional[bool] = None
    assigned_id: Optional[str] = None
    subtasks: Optional[List[Subtask]] = None
    goal_id: Optional[str] = None

class TaskResponse(TaskCreate):
    id: str
    created_at: Optional[str] = None
    risk_score: Optional[int] = None
    risk_level: Optional[str] = None
    risk_factors: Optional[List[str]] = Field(default_factory=list)
    comments: Optional[List[TaskCommentResponse]] = Field(default_factory=list)
    attachments: Optional[List[TaskAttachmentResponse]] = Field(default_factory=list)

    class Config:
        from_attributes = True

# Approval Schemas
class ApprovalCreate(BaseModel):
    title: str
    requested: str
    assigned: str
    priority: str = "High"
    status: Optional[str] = "Pending"
    comments: Optional[str] = None

class ApprovalUpdate(BaseModel):
    status: Optional[str] = None
    comments: Optional[str] = None

class ApprovalResponse(ApprovalCreate):
    # Documents written before these fields existed must still serialise, so the
    # response model tolerates them instead of failing the whole list.
    id: str
    title: str = "Untitled request"
    requested: str = ""
    assigned: str = ""
    reviewed_at: Optional[str] = None
    created_at: Optional[str] = None

    class Config:
        from_attributes = True

# Notification Schemas
class NotificationCreate(BaseModel):
    user_id: Optional[str] = None
    title: str
    message: str
    type: str = "Task"
    priority: Optional[str] = "Medium"
    target_route: Optional[str] = None
    icon: Optional[str] = "📋"
    status: Optional[str] = "New"
    time: Optional[str] = "Just now"
    is_read: bool = False

class NotificationResponse(NotificationCreate):
    id: str
    created_at: Optional[str] = None

    class Config:
        from_attributes = True

class UnreadCountResponse(BaseModel):
    unread_count: int

# AI Schemas
class AINotificationSummaryResponse(BaseModel):
    summary: str
    message: str = ""
    total: int = 0
    unread: int = 0
    by_type: Dict[str, int] = {}
    attention: List[str] = []


class AIApprovalSuggestionItem(BaseModel):
    id: str
    title: str
    score: int
    reason: str


class AIApprovalSuggestionsResponse(BaseModel):
    message: str
    suggestions: List[AIApprovalSuggestionItem] = []


class AICalendarInsightResponse(BaseModel):
    message: str
    highlights: List[str] = []
    source: str = "heuristic"


class AIChatRequest(BaseModel):
    message: str

class AIChatResponse(BaseModel):
    user: str
    ai: str

class AIPriorityItem(BaseModel):
    task_id: str
    title: str
    priority: str
    risk_score: int
    rank: int
    why: List[str]

class HODActionItem(BaseModel):
    type: str # CRITICAL, HIGH RISK, APPROVAL, WORKLOAD
    title: str
    description: str
    target_id: Optional[str] = None
    target_route: Optional[str] = None
    priority_level: int

class AIDashboardSummaryResponse(BaseModel):
    greeting: str
    teacher_priorities: Optional[List[AIPriorityItem]] = None
    hod_actions: Optional[List[HODActionItem]] = None
    productivity_score: Optional[str] = None

class AIReportResponse(BaseModel):
    title: str = "HieraSync AI Workflow Analysis Report"
    summary: str
    recommendations: List[str]
    generated_at: str

class FacultyPerformance(BaseModel):
    faculty_id: str
    faculty_name: str
    total_tasks: int
    completed: int
    on_time: int
    late: int
    pending: int
    overdue: int
    completion_rate: float
    on_time_rate: float
    average_completion_time: Optional[float] = None
    current_workload: int
    productivity_score: float
    productivity_explanation: str

# Settings Schemas
class UserSettingsResponse(BaseModel):
    user_id: str
    ai_recommendation: bool = True
    task_analysis: bool = True
    deadline_alert: bool = True
    email_notifications: bool = True

class UserSettingsUpdate(BaseModel):
    ai_recommendation: Optional[bool] = None
    task_analysis: Optional[bool] = None
    deadline_alert: Optional[bool] = None
    email_notifications: Optional[bool] = None

class DepartmentProfileResponse(BaseModel):
    department: str = "Artificial Intelligence & Machine Learning"
    institute: str = "SBJIT Nagpur"
    platform: str = "HieraSync AI"
    purpose: str = "Organizational Workflow Management"
    version: str = "1.0"
    status: str = "Active"

# Global Search Schemas
class SearchResultItem(BaseModel):
    id: str
    title: str
    type: str  # task | faculty | notification | event

class GlobalSearchResponse(BaseModel):
    query: str
    results: List[SearchResultItem]

# Department Schemas
class DepartmentCreate(BaseModel):
    name: str

class DepartmentResponse(BaseModel):
    id: str
    name: str
    code: str
    hod_id: str

# Join Request Schemas
class JoinRequestCreate(BaseModel):
    code: str

class JoinRequestResponse(BaseModel):
    id: str
    faculty_id: str
    faculty_name: str
    faculty_email: str
    department_id: str
    department_name: Optional[str] = None
    department_code: str
    status: str
    requested_at: str
