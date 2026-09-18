/**
 * Platform API — v2 capability modules (risk, approval workflow, metrics, notification channels).
 * Mirrors backend/app/api/v1/{risk,workflow,metrics,channels}.py.
 */
import { client } from './client';

/** Absolute base for <a href> / EventSource links (client.ts prepends it for fetch calls). */
export const API_ROOT = (import.meta.env.VITE_API_URL as string) || 'http://127.0.0.1:8000/api/v1';

/* ------------------------------------------------------------------ risk */

export interface RiskFactor {
  factor: string;
  label?: string;
  sub_score: number;
  weight: number;
  contribution: number;
  share_of_risk?: number;
  evidence: string;
}

export interface RiskAssessment {
  task_id?: string;
  title?: string;
  risk_score: number;
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

export interface RiskBoard {
  generated_at: string;
  scope: string;
  summary: { open: number; LOW: number; MEDIUM: number; HIGH: number; mean_risk: number; expected_misses?: number };
  items: Array<RiskAssessment & { task_id: string; title: string; assignee?: string; deadline?: string | null; status?: string; priority?: string }>;
}

export const riskApi = {
  board: () => client<RiskBoard>('/risk/board'),
  score: (taskId: string) => client<RiskAssessment>(`/risk/score/${taskId}`),
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
      corpus: Record<string, unknown>;
      metrics: Array<{ model: string; auc: number; pr_auc: number; precision_at_alert_budget: number; f1: number; flag_rate: number; top_decile_precision: number }>;
      leaderboard: { best_auc: string; best_precision_at_budget: string; note: string };
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

export const workflowApi = {
  queue: () =>
    client<{ generated_at: string; buckets: Record<string, number>; items: ApprovalDoc[]; stats?: Record<string, number> }>('/workflow/queue'),
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
  policies: () => client<Record<string, { stages: string[]; sla_hours: number; note_required_on_reject?: boolean; principal_above?: number }>>('/workflow/policies'),
  rbac: () => client<{ roles: string[]; capabilities: string[]; matrix: Record<string, string[]>; analytics_scope: Record<string, string> }>('/workflow/rbac'),
  funnel: () => client<Record<string, number | string>>('/workflow/stats/funnel'),
};

/* --------------------------------------------------------------- metrics */

export interface Scorecard {
  window_days: number;
  scope: string;
  tasks: { total: number; open: number; completed: number; overdue: number; on_time_rate: number; mean_progress: number; median_cycle_days?: number };
  risk: { scored: number; HIGH: number; MEDIUM: number; LOW: number; mean_score: number; expected_misses: number };
  approvals: { pending: number; approved: number; rejected: number; median_hours?: number | null; breaches: number; approval_rate?: number };
  workload: { tracked_users: number; balance_index: number; fairness_gap?: number; overloaded?: Array<{ name: string; load: number }> };
  automation: { delivered: number; simulated?: number; failed?: number; delivered_channels?: Record<string, number> };
  formulas: Record<string, string>;
  insights?: Array<{ severity: string; text: string; action?: string }>;
}

export const metricsApi = {
  scorecard: (days = 30) => client<Scorecard>(`/metrics/scorecard?days=${days}`),
  faculty: () =>
    client<Array<{ user_id: string; name: string; role: string; designation?: string; open: number; completed: number; overdue: number; on_time_rate: number; performance_index: number; workload: number }>>(
      '/metrics/faculty',
    ),
  departments: () => client<Array<Record<string, unknown>>>('/metrics/departments'),
  forecast: (weeks = 4) => client<{ horizon_weeks: number; points: Array<{ week: number; expected_completions: number; expected_slips: number; open_at_risk: number }> }>(`/metrics/forecast?weeks=${weeks}`),
  riskTrend: (days = 30) => client<{ points: Array<{ taken_at: string; HIGH: number; MEDIUM: number; LOW: number; mean_risk: number }> }>(`/metrics/risk-trend?days=${days}`),
  exportUrl: (dataset: string, format: 'csv' | 'json' = 'csv') =>
    `${API_ROOT}/metrics/export?dataset=${dataset}&format=${format}`,
  snapshot: () => client<Record<string, unknown>>('/metrics/snapshot', { method: 'POST', data: {} }),
};

/* -------------------------------------------------------- notification ops */

export interface ChannelRow {
  id: string;
  user_id: string;
  channel: 'inapp' | 'email' | 'sms' | 'whatsapp';
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

export const channelsApi = {
  status: () =>
    client<{
      dev_mode: boolean;
      outbox_dir?: string;
      scheduler_enabled: boolean;
      timezone: string;
      channels: Record<string, { enabled: boolean; provider: string; label: string; detail?: string; reason?: string; live?: boolean }>;
      policy: Record<string, string[]>;
      queue: { pending: number; scheduled: number; retry: number; dead: number };
    }>('/channels/status'),
  preferences: () =>
    client<{
      preferences: Record<string, unknown>;
      defaults: Record<string, unknown>;
      policy_channels: Record<string, string[]>;
      muted_kinds_options: string[];
    }>('/channels/preferences'),
  setPreferences: (patch: Record<string, unknown>) => client<Record<string, unknown>>('/channels/preferences', { method: 'PUT', data: patch }),
  outbox: (limit = 25) => client<{ rows: ChannelRow[]; total?: number }>(`/channels/outbox?limit=${limit}`),
  deliveries: (limit = 25) => client<{ rows: Array<Record<string, unknown>> }>(`/channels/deliveries?limit=${limit}`),
  flush: () => client<{ scanned: number; sent: number; failed?: number; dead?: number }>('/channels/flush', { method: 'POST', data: {} }),
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
