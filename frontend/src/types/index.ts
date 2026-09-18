/** Backend `RoleEnum` — 10 institutional roles (Slide 13). Aliases are normalised server-side. */
export type RoleEnum =
  | 'ADMIN'
  | 'PRINCIPAL'
  | 'HOD'
  | 'FACULTY'
  | 'TEACHER'
  | 'TA'
  | 'LAB_ASSISTANT'
  | 'STAFF'
  | 'STUDENT'
  | 'STUDENT_REP';

export interface UserBase {
  name: string;
  email: string;
  role: RoleEnum;
  department_id?: string;
  designation?: string;
  area_of_interest?: string;
  joining_date?: string;
  association?: string;
  avatar_url?: string;
}

export interface UserResponse extends UserBase {
  id: string;
  status: string;
}

export interface LoginRequest {
  email: string;
  password?: string;
  rememberMe?: boolean;
}

export interface ForgotPasswordRequest {
  email: string;
}

export interface RegisterRequest {
  name: string;
  email: string;
  password?: string;
  role?: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: UserResponse;
}

export interface EmployeeResponse extends UserBase {
  id: string;
  status: string;
}

export interface EmployeeCreate extends UserBase {
  password?: string;
}

export interface EmployeeUpdate {
  name?: string;
  designation?: string;
  area_of_interest?: string;
  joining_date?: string;
  association?: string;
  role?: RoleEnum;
  avatar_url?: string;
}

export interface DashboardStatsResponse {
  employees_count: number;
  pending_tasks_count: number;
  high_priority_tasks: number;
  approvals_count: number;
  waiting_approvals: number;
  ai_productivity: string;
  workflow_progress: number;
}

export interface ActivityLogResponse {
  id: string;
  message: string;
  category?: string;
  icon?: string;
  timestamp?: string;
}

export interface DepartmentReportSummary {
  total_tasks: number;
  completed_tasks: number;
  active_faculty: number;
  ai_efficiency: string;
  completion_rate: string;
}

export interface EventCreate {
  title: string;
  date: string;
  type?: string;
  person: string;
  description?: string;
  location?: string;
}

export interface EventUpdate {
  title?: string;
  date?: string;
  type?: string;
  person?: string;
  description?: string;
  location?: string;
}

export interface EventResponse extends EventCreate {
  id: string;
  creator_id?: string;
  created_at?: string;
}

export interface Subtask {
  id: string;
  title: string;
  completed: boolean;
}

export interface TaskCreate {
  title: string;
  assigned: string;
  deadline: string;
  priority?: string;
  status?: string;
  progress?: string;
  description?: string;
  category?: string;
  start_date?: string;
  deadline_time?: string;
  estimated_effort?: string;
  reminder?: string;
  require_approval?: boolean;
  assigned_id?: string;
  subtasks?: Subtask[];
  goal_id?: string;
}

export interface TaskUpdate {
  title?: string;
  assigned?: string;
  deadline?: string;
  priority?: string;
  status?: string;
  progress?: string;
  description?: string;
  category?: string;
  start_date?: string;
  deadline_time?: string;
  estimated_effort?: string;
  reminder?: string;
  require_approval?: boolean;
  assigned_id?: string;
  subtasks?: Subtask[];
  goal_id?: string;
}

export interface TaskResponse extends TaskCreate {
  id: string;
  created_at?: string;
  risk_score?: number;
  risk_level?: "LOW" | "MEDIUM" | "HIGH";
  risk_factors?: string[];
  comments?: TaskCommentResponse[];
  attachments?: TaskAttachmentResponse[];
}

export interface ApprovalCreate {
  title: string;
  requested: string;
  assigned: string;
  priority?: string;
  status?: string;
  comments?: string;
}

export interface ApprovalUpdate {
  status?: string;
  comments?: string;
}

export interface ApprovalResponse extends ApprovalCreate {
  id: string;
  reviewed_at?: string;
  created_at?: string;
}

export interface NotificationCreate {
  title: string;
  message: string;
  type?: string;
  priority?: string;
  target_route?: string;
  icon?: string;
  status?: string;
  time?: string;
  is_read?: boolean;
}

export interface NotificationResponse extends NotificationCreate {
  id: string;
  created_at?: string;
}

export interface UnreadCountResponse {
  unread_count: number;
}

export interface AIChatRequest {
  message: string;
}

export interface AIChatResponse {
  user: string;
  ai: string;
}

export interface AIDashboardSummaryResponse {
  greeting?: string;
  insights: string[];
  productivity_score?: string;
}

export interface AIReportResponse {
  title?: string;
  summary: string;
  recommendations: string[];
  generated_at: string;
}

export interface UserSettingsResponse {
  user_id: string;
  ai_recommendation?: boolean;
  task_analysis?: boolean;
  deadline_alert?: boolean;
  email_notifications?: boolean;
}

export interface UserSettingsUpdate {
  ai_recommendation?: boolean;
  task_analysis?: boolean;
  deadline_alert?: boolean;
  email_notifications?: boolean;
}

export interface DepartmentProfileResponse {
  department?: string;
  institute?: string;
  platform?: string;
  purpose?: string;
  version?: string;
  status?: string;
}

export interface SearchResultItem {
  id: string;
  title: string;
  type: string;
}

export interface GlobalSearchResponse {
  query: string;
  results: SearchResultItem[];
}


export interface TaskRequestCreate {
  title: string;
  description: string;
  category?: string;
  priority?: string;
  suggested_deadline: string;
  estimated_effort?: string;
  additional_notes?: string;
}

export interface TaskRequestResponse extends TaskRequestCreate {
  id: string;
  requester_id: string;
  requester_name: string;
  status: string;
  created_at: string;
  reviewed_at?: string;
  reviewed_by?: string;
  rejection_reason?: string;
  created_task_id?: string;
}

export interface TaskCommentCreate {
  content: string;
  mentions: string[];
}

export interface TaskCommentResponse extends TaskCommentCreate {
  id: string;
  task_id: string;
  author_id: string;
  author_name: string;
  created_at: string;
  updated_at: string;
}

export interface TaskAttachmentResponse {
  id: string;
  task_id: string;
  file_name: string;
  file_type: string;
  file_size: number;
  storage_path: string;
  uploaded_by: string;
  created_at: string;
}

export interface GoalMilestoneCreate {
  title: string;
  description: string;
  due_date: string;
  order: number;
  status?: string;
}

export interface GoalMilestoneResponse extends GoalMilestoneCreate {
  id: string;
  goal_id: string;
  completed_at?: string;
  created_at: string;
  updated_at: string;
}

export interface DepartmentGoalCreate {
  title: string;
  description: string;
  category?: string;
  start_date: string;
  target_date: string;
  status?: string;
}

export interface DepartmentGoalResponse extends DepartmentGoalCreate {
  id: string;
  owner_id: string;
  created_at: string;
  updated_at: string;
  milestones: GoalMilestoneResponse[];
}

export interface AIPriorityItem {
  task_id: string;
  title: string;
  risk_level: 'HIGH' | 'MEDIUM' | 'LOW';
  priority_score: number;
  rank?: number;
  priority?: string;
  risk_score?: number;
  why?: string[];
  reason: string;
  suggested_action: string;
}

export interface HODActionItem {
  id: string;
  type: string;
  title: string;
  urgency: 'HIGH' | 'MEDIUM' | 'LOW';
  description: string;
  target_route: string | null;
  target_id?: string;
  priority_level: number;
}

export interface FacultyPerformance {
  faculty_id: string;
  faculty_name: string;
  total_tasks: number;
  completed: number;
  on_time: number;
  late: number;
  pending: number;
  overdue: number;
  completion_rate: number;
  on_time_rate: number;
  average_completion_time: number | null;
  current_workload: number;
  productivity_score: number;
  productivity_explanation: string;
}

export interface AIDashboardSummaryResponse {
  department_health_score: number;
  department_health_trend: string;
  risk_summary: string;
  ai_insights: string[];
  teacher_priorities?: AIPriorityItem[];
  hod_actions?: HODActionItem[];
}
