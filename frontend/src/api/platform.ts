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
  related_task_id?: string | null;
  resubmissions?: number;
  delegated_to?: string | null;
  delegated_from?: string | null;
  escalation_count?: number;
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

/** POST /workflow/ - step 1 of the deck's workflow (Slide 15). */
export interface NewRequestPayload {
  title: string;
  kind?: 'leave' | 'no_objection' | 'event' | 'purchase' | 'budget' | 'outcome_approval' | 'deadline_change' | 'joining' | 'generic';
  description?: string;
  amount?: number | null;
  priority?: 'Low' | 'Medium' | 'High' | 'Critical';
  evidence?: Record<string, unknown>;
  attachment_ids?: string[];
  department_id?: string | null;
  expected_completion?: string | null;
  goal_id?: string | null;
}

export type DecisionResult = {
  id: string;
  status: ApprovalDoc['status'];
  stage: string;
  stages: string[];
  next_actor?: string | null;
  created_task?: { id: string; title: string; deadline?: string } | false;
  related_task_id?: string | null;
  audit?: NonNullable<ApprovalDoc['audit']>;
};



export const workflowApi = {
  raise: (body: NewRequestPayload) => client<ApprovalDoc & { id: string }>('/workflow/', { method: 'POST', data: body }),
  queue: () => client<{ role: string; counts: { total: number; breached: number; due_soon: number }; items: QueueItem[] }>('/workflow/queue'),
  list: (scope: 'incoming' | 'mine' | 'all' = 'incoming') => client<ApprovalDoc[]>(`/workflow/?scope=${scope}`),
  get: (id: string) => client<ApprovalDoc>(`/workflow/${id}`),
  decide: (id: string, decision: 'APPROVE' | 'REJECT', note = '') =>
    client<DecisionResult>(`/workflow/${id}/decide`, { method: 'POST', data: { decision, note } }),
  resubmit: (id: string, note: string, evidence?: Record<string, unknown>) =>
    client<ApprovalDoc>(`/workflow/${id}/resubmit`, { method: 'POST', data: { note, evidence } }),
  cancel: (id: string, note = '') => client<ApprovalDoc>(`/workflow/${id}/cancel`, { method: 'POST', data: { note } }),
  delegate: (id: string, to: string, note = '') =>
    client<ApprovalDoc>(`/workflow/${id}/delegate`, { method: 'POST', data: { to, note } }),
  audit: (id: string) => client<{ approval_id: string; entries: ApprovalDoc['audit']; valid: boolean }>(`/workflow/${id}/audit`),
  verify: () => client<{ ok: boolean; checked?: number; problems?: string[] }>('/workflow/verify', { method: 'POST', data: {} }),
  policies: () =>
    client<{
      stages: string[];
      policies: Array<{ kind: string; stages: string[]; sla_hours: number; requires_note_on_reject?: boolean; required_evidence?: string[]; principal_above?: number }>;
    }>('/workflow/policies'),
  rbac: () => client<{ roles: string[]; capabilities: string[]; matrix: Record<string, string[]>; analytics_scope: Record<string, string> }>('/workflow/rbac'),
  funnel: () =>
    client<{
      buckets: Record<string, number>;
      pending_breaching_sla: number;
      escalation_events: number;
      median_hours_to_decision: number | null;
      median_hours_to_first_response: number | null;
      by_kind: Record<string, number>;
      baseline_note?: string;
    }>('/workflow/stats/funnel'),
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
  faculty: (days = 90) =>
    client<{
      count: number;
      weights: Record<string, number>;
      note: string;
      items: Array<{ user_id: string; name: string; role: string; designation?: string; active: number; completed: number; overdue: number; on_time_rate: number; avg_progress: number; performance_index: number; workload: number; responsiveness?: number }>;
    }>(`/metrics/faculty?days=${days}`),
  departments: (days = 90) =>
    client<{
      items: Array<{
        department_id: string;
        department: string;
        code?: string;
        active_tasks: number;
        completion_rate: number;
        on_time_rate: number;
        overdue_rate: number;
        high_risk_tasks: number;
        projected_misses: number;
        approvals_pending: number;
        approvals_breached: number;
        workload_balance_index: number;
        health_index: number;
      }>;
    }>(`/metrics/departments?days=${days}`),
  forecast: (weeks = 4) => client<{ points: Array<{ week: string; count: number }> }>(`/metrics/forecast?weeks=${weeks}`),
  riskTrend: (days = 30) =>
    client<{ count: number; items: Array<{ taken_at: string; bands?: Record<string, number>; LOW?: number; MEDIUM?: number; HIGH?: number; mean_risk?: number; open_tasks?: number }> }>(
      `/metrics/risk-trend?days=${days}`,
    ),
  snapshot: () => client<Record<string, unknown>>('/metrics/snapshot', { method: 'POST', data: {} }),
  /** GET /api/v1/metrics/export - kind is one of the six accreditation datasets. */
  exportUrl: (kind: string, format: 'csv' | 'json' = 'csv', days = 90) =>
    `${API_ROOT}/metrics/export?kind=${kind}&format=${format}&days=${days}`,
  datasets: ['scorecard', 'faculty', 'tasks', 'approvals', 'departments', 'audit'] as const,
  /** The export needs the Authorization header, so stream it and hand the browser a blob. */
  download: async (kind: string, format: 'csv' | 'json' = 'csv', days = 90) => {
    const token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token') || '';
    const res = await fetch(metricsApi.exportUrl(kind, format, days), { headers: { Authorization: `Bearer ${token}` } });
    if (!res.ok) throw new Error(`Export failed (${res.status})`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `hierasync-${kind}-${new Date().toISOString().slice(0, 10)}.${format}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    return a.download;
  },
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
