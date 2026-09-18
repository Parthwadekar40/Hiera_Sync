/**
 * Platform API — v2 capability modules (risk, approval workflow, metrics, notification channels).
 * Mirrors backend/app/api/v1/{risk,workflow,metrics,channels}.py.
 */
import { client } from './client';

/** Absolute base for <a href> / EventSource links (client.ts prepends it for fetch calls). */
export const API_ROOT = (import.meta.env.VITE_API_URL as string) || 'http://127.0.0.1:8000/api/v1';

/* ------------------------------------------------------------------ risk */

export interface RiskFactor {
  key: string;
  label?: string;
  sub_score: number;
  weight: number;
  contribution: number;
  share_of_risk?: number;
  evidence: string;
}

export interface RiskAssessment {
  task_id?: string;
  risk_score: number;
  linear_score?: number;
  evidence_logit?: number;
  eta_days?: number;
  overdue_by_days?: number;
  weights_used?: Record<string, number>;
  top_drivers?: RiskFactor[];
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH';
  at_risk?: boolean;
  escalation_severity?: string;
  delay_probability: number;
  confidence: number;
  factors: RiskFactor[];
  drivers?: string[];
  explanation?: string;
  recommendations?: string[];
  projected_completion?: string;
  days_left?: number | null;
}

export interface RiskBoardTask {
  id: string;
  title: string;
  status: string;
  priority: string;
  progress: string | number;
  deadline: string | null;
  assigned: string | null;
  assigned_id: string | null;
  assessment: RiskAssessment;
}

/** GET /risk/board - rows carry the full assessment so the UI never re-requests. */
export interface RiskBoard {
  count: number;
  bands: { LOW: number; MEDIUM: number; HIGH: number };
  weights: Record<string, number>;
  context: { mean_reliability: number; median_approval_hours: number; department_overdue_share: number };
  tasks: RiskBoardTask[];
}

export const riskApi = {
  board: () => client<RiskBoard>('/risk/board'),
  score: (taskId: string) => client<RiskAssessment>(`/risk/score/${taskId}`),
  whatIfNote: 'scores a copy - nothing is persisted',
  whatIf: (body: { task_id?: string; overrides: Record<string, unknown>; task?: Record<string, unknown> }) =>
    client<{
      task_id: string;
      before: { risk_score: number; risk_level: string; delay_probability: number };
      after: { risk_score: number; risk_level: string; delay_probability: number; recommendations?: string[]; top_drivers?: string[] };
      delta: number;
      verdict: 'improves' | 'worsens' | 'neutral';
    }>('/risk/what-if', { method: 'POST', data: body }),
  weights: () =>
    client<{
      effective_weights: Record<string, number>;
      default_weights: Record<string, number>;
      calibration: Record<string, unknown>;
      bands: Array<{ min: number; label: string }>;
      factor_labels: Record<string, string>;
    }>('/risk/weights'),
  setWeights: (weights: Record<string, number>, persist = true) =>
    client<{ ok: boolean; weights: Record<string, number> }>('/risk/weights', { method: 'PUT', data: { weights, persist } }),
  calibrate: () =>
    client<{ ok: boolean; samples?: number; auc_before?: number; auc_after?: number; gain?: number; weights?: Record<string, number> }>(
      '/risk/calibrate',
      { method: 'POST', data: {} },
    ),
  benchmark: (tasks = 240) =>
    client<{
      experiment: { samples: number; train: number; test: number; positive_rate: number; seed: number; features: string[] };
      results: Record<string, { roc_auc: number; pr_auc: number; precision_at_alert_budget: number; f1_at_alert_budget: number; flag_rate: number; top_20pct_precision: number; precision: number; recall: number; ece: number }>;
      ranking: Array<{ model: string; roc_auc: number }>;
      best: string;
      our_rank: number;
      delta_vs_best_ml?: number;
      calibration?: { auc_before: number; auc_after: number; gain: number; samples: number };
      sample_efficiency_sweep?: Record<string, Record<string, number>>;
      live_profile?: Record<string, unknown>;
    }>(`/risk/benchmark?tasks=${tasks}`),
};

/* -------------------------------------------------------------- workflow */

export interface ApprovalDoc {
  id: string;
  title: string;
  kind: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'CANCELLED';
  stage: string;
  stages: string[];
  stage_index: number;
  sla_hours?: number;
  sla_elapsed_hours?: number;
  sla_state?: 'on_track' | 'due_soon' | 'breached' | 'escalated';
  requester_name?: string;
  requester_id?: string;
  department_id?: string;
  amount?: number;
  description?: string;
  evidence?: Record<string, unknown>;
  hod_comment?: string;
  principal_comment?: string;
  audit?: Array<{ at: string; actor_role: string; action: string; note?: string; hash?: string }>;
  can_act?: boolean;
  action_hint?: string;
  audit_integrity?: { valid: boolean; problems: string[] };
  created_task_id?: string;
}

/** Queue rows are lean: SLA state is nested and the action hint is `action_reason`. */
export interface QueueItem {
  id: string;
  title: string;
  kind: string;
  requester_name?: string;
  priority?: string;
  stage: string;
  created_at?: string;
  action_reason?: string;
  sla?: { state: 'on_track' | 'due_soon' | 'breached' | 'escalated'; hours_waiting: number; sla_hours: number; hours_remaining: number; percent_consumed: number; breached: boolean };
}

export const workflowApi = {
  queue: () => client<{ role: string; counts: { total: number; breached: number; due_soon: number }; items: QueueItem[] }>('/workflow/queue'),
  list: (scope: 'incoming' | 'mine' | 'all' = 'incoming') => client<ApprovalDoc[]>(`/workflow/?scope=${scope}`),
  get: (id: string) => client<ApprovalDoc>(`/workflow/${id}`),
  raise: (body: Record<string, unknown>) => client<ApprovalDoc>('/workflow/', { method: 'POST', data: body }),
  decide: (id: string, decision: 'APPROVE' | 'REJECT', note = '') =>
    client<{ ok: boolean; status: string; stage: string; next_actor?: string; created_task: boolean; created_task_id?: string; doc: ApprovalDoc }>(
      `/workflow/${id}/decide`,
      { method: 'POST', data: { decision, note } },
    ),
  resubmit: (id: string, note: string, evidence?: Record<string, unknown>) =>
    client<ApprovalDoc>(`/workflow/${id}/resubmit`, { method: 'POST', data: { note, evidence } }),
  cancel: (id: string, note = '') => client<{ ok: boolean }>(`/workflow/${id}/cancel`, { method: 'POST', data: { note } }),
  delegate: (id: string, toUserId: string, note = '') =>
    client<ApprovalDoc>(`/workflow/${id}/delegate`, { method: 'POST', data: { to_user_id: toUserId, note } }),
  audit: (id: string) => client<{ approval_id: string; entries: ApprovalDoc['audit']; valid: boolean }>(`/workflow/${id}/audit`),
  verify: () => client<{ ok: boolean; checked?: number; problems?: string[] }>('/workflow/verify', { method: 'POST', data: {} }),
  policies: () =>
    client<{
      stages: string[];
      policies: Array<{ kind: string; stages: string[]; sla_hours: number; requires_note_on_reject?: boolean; required_evidence?: string[]; principal_above?: number }>;
    }>('/workflow/policies'),
  rbac: () => client<{ roles: string[]; capabilities: string[]; matrix: Record<string, string[]>; analytics_scope: Record<string, string> }>('/workflow/rbac'),
  funnel: () => client<Record<string, number | string>>('/workflow/stats/funnel'),
};

/* --------------------------------------------------------------- metrics */

export interface Scorecard {
  generated_at: string;
  window_days: number;
  scope: { department_id: string | null; assignee_id: string | null };
  analytics_scope: string;
  tasks: { total: number; active: number; completed: number; overdue: number; overdue_rate: number; completion_rate: number; on_time_rate: number; avg_days_late: number; avg_progress: number };
  risk: { bands: Record<string, number>; mean_score: number; high_risk_count: number; at_risk_count: number; projected_misses: number; mean_confidence: number };
  approvals: { pending: number; breached_sla: number; sla_compliance: number; median_hours_to_decision: number | null; decided: number; rejection_rate: number };
  workload: { per_assignee: Array<Record<string, number | string>>; mean_load: number; spread: number; balance_index: number };
  automation: { deliveries_total: number; delivered: number; failed_or_retrying: number; delivery_success_rate: number; mean_latency_ms: number; simulated_only: number };
  top_risks: Array<Record<string, unknown>>;
  insights: Array<{ severity: string; text: string; action?: string }>;
  formulas: Record<string, string>;
}

export const metricsApi = {
  scorecard: (days = 30) => client<Scorecard>(`/metrics/scorecard?days=${days}`),
  faculty: () =>
    client<{
      count: number;
      weights: Record<string, number>;
      note: string;
      items: Array<{ user_id: string; name: string; role: string; open: number; completed: number; overdue: number; on_time_rate: number; performance_index: number; workload: number }>;
    }>('/metrics/faculty'),
  departments: () => client<Array<Record<string, unknown>>>('/metrics/departments'),
  forecast: (weeks = 4) => client<{ points: Array<{ week: string | number; count: number }> }>(`/metrics/forecast?weeks=${weeks}`),
  riskTrend: (days = 30) => client<{ points: Array<{ taken_at: string; HIGH: number; MEDIUM: number; LOW: number; mean_risk: number }> }>(`/metrics/risk-trend?days=${days}`),
  exportUrl: (dataset: string, format: 'csv' | 'json' = 'csv') =>
    `${API_ROOT}/metrics/export?dataset=${dataset}&format=${format}`,
  snapshot: () => client<Record<string, unknown>>('/metrics/snapshot', { method: 'POST', data: {} }),
  exportDatasets: ['tasks', 'faculty', 'approvals', 'audit', 'departments'] as const,
};

/* -------------------------------------------------------- notification ops */

export interface ChannelRow {
  id: string;
  user_id: string;
  channel: string;
  kind: string;
  severity: string;
  subject?: string;
  text?: string;
  status: 'pending' | 'scheduled' | 'retry' | 'sent' | 'dead';
  attempts: number;
  defer_reason?: string;
  provider?: string;
  last_error?: string;
  created_at?: string;
  sent_at?: string;
}

export interface JobSpec {
  id: string;
  title: string;
  schedule: string;
  purpose: string;
  idempotent: boolean;
}

export interface ChannelInfo {
  channel: string;
  will_use: string;
  live: boolean;
  simulated_only: boolean;
  chain: Array<{ channel: string; provider: string; configured: boolean; enabled: boolean }>;
}

export const channelsApi = {
  status: () =>
    client<{
      notifications_enabled: boolean;
      timezone: string;
      quiet_hours_default: string;
      policy: Record<string, string[]>;
      retry: { max_attempts: number; backoff_base_seconds: number; backoff_max_seconds: number; dedupe_window_minutes: number; rate_limit_per_minute: number };
      channels: Record<string, ChannelInfo>;
      your_reachability: { email?: string; phone?: string; whatsapp_opt_in?: boolean };
      outbox: { by_status: Record<string, number>; by_channel: Record<string, number>; total: number };
      persistence: { backend: string; path: string; collections: Record<string, number> };
    }>('/channels/status'),
  preferences: () =>
    client<{
      preferences: Record<string, unknown>;
      defaults: Record<string, unknown>;
      policy_channels: Record<string, string[]>;
      muted_kinds_options: string[];
    }>('/channels/preferences'),
  setPreferences: (patch: Record<string, unknown>) => client<Record<string, unknown>>('/channels/preferences', { method: 'PUT', data: patch }),
  outbox: (limit = 25) =>
    client<{ count: number; stats: { by_status: Record<string, number>; by_channel: Record<string, number>; total: number }; items: ChannelRow[]; dev_artifacts: Array<{ name: string; channel: string; modified: string }> }>(
      `/channels/outbox?limit=${limit}`,
    ),
  deliveries: (limit = 25) => client<{ count: number; summary: Record<string, number>; items: Array<Record<string, unknown>> }>(`/channels/deliveries?limit=${limit}`),
  flush: () => client<{ scanned: number; sent: number; failed?: number; dead?: number; skipped?: number }>('/channels/flush', { method: 'POST', data: {} }),
  test: (channels?: string[]) => client<Record<string, unknown>>('/channels/test', { method: 'POST', data: { channels } }),
  preview: (body: { kind: string; severity: string; title: string; message: string }) =>
    client<{ subject: string; text: string; html: string; sms_segments: number; html_length: number }>('/channels/preview', { method: 'POST', data: body }),
  kinds: () => client<{ kinds: Array<{ kind: string; label: string; default_severity: string; routes_to: string[] }> }>('/channels/kinds'),
  jobs: () => client<{ scheduler_enabled: boolean; timezone: string; jobs: JobSpec[] }>('/channels/jobs'),
  runJob: (id: string) => client<{ job: string; triggered_by: string; result: Record<string, unknown> }>(`/channels/jobs/${id}/run`, { method: 'POST', data: {} }),
  purge: () => client<{ removed: number; retention_days: number }>('/channels/purge', { method: 'POST', data: {} }),
  /** Server-sent events feed; the token is passed as a query param because EventSource cannot set headers. */
  streamUrl: () => `${API_ROOT}/channels/stream?token=${encodeURIComponent(localStorage.getItem('access_token') || sessionStorage.getItem('access_token') || '')}`,
};
