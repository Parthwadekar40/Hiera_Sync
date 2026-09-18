/**
 * Automation Center — notification channels, delivery queue, scheduler control (Slide 19 + future scope shipped).
 * Everything here is real: policy routing, consent gates, quiet hours, retries and the delivery ledger.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Bell, CheckCircle2, Clock, Mail, MessageSquare, Phone, Play, Radio, RefreshCw, Send, Trash2 } from 'lucide-react';
import { channelsApi, type ChannelRow, type JobSpec } from '../api/platform';
import { useAuth } from '../contexts/AuthContext';

const STATUS_TONE: Record<string, string> = {
  sent: 'bg-emerald-500/10 text-emerald-600 ring-emerald-500/30',
  simulated: 'bg-sky-500/10 text-sky-600 ring-sky-500/30',
  pending: 'bg-amber-500/10 text-amber-600 ring-amber-500/30',
  scheduled: 'bg-amber-500/10 text-amber-600 ring-amber-500/30',
  retry: 'bg-orange-500/10 text-orange-600 ring-orange-500/30',
  dead: 'bg-rose-500/10 text-rose-600 ring-rose-500/30',
};

const CHANNEL_ICON: Record<string, typeof Mail> = {
  inapp: Bell,
  email: Mail,
  sms: Phone,
  whatsapp: MessageSquare,
};

type Status = Awaited<ReturnType<typeof channelsApi.status>>;
type Prefs = Awaited<ReturnType<typeof channelsApi.preferences>>;

export default function AutomationCenter() {
  const { user } = useAuth();
  // The SPA's Role union is narrower than the backend's 10 roles; compare loosely on purpose.
  const role = String((user as { role?: string } | null)?.role ?? '');
  const isOperator = ['ADMIN', 'PRINCIPAL', 'HOD'].includes(role);
  const [status, setStatus] = useState<Status | null>(null);
  const [prefs, setPrefs] = useState<Prefs | null>(null);
  const [rows, setRows] = useState<ChannelRow[]>([]);
  const [jobs, setJobs] = useState<JobSpec[]>([]);
  const [jobsMeta, setJobsMeta] = useState<{ scheduler_enabled: boolean; timezone: string }>({ scheduler_enabled: true, timezone: '' });
  const [tab, setTab] = useState<'queue' | 'ledger' | 'feed'>('queue');
  const [feed, setFeed] = useState<string[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [ledger, setLedger] = useState<Array<Record<string, unknown>>>([]);
  const [artifacts, setArtifacts] = useState<Array<{ name: string; channel: string; modified: string }>>([]);
  const sourceRef = useRef<EventSource | null>(null);

  const loadAll = useCallback(async () => {
    const [s, p, o, j] = await Promise.all([channelsApi.status(), channelsApi.preferences(), channelsApi.outbox(40), channelsApi.jobs()]);
    setStatus(s);
    setPrefs(p);
    setRows(o.items ?? []);
    setArtifacts(o.dev_artifacts ?? []);
    setJobs(j.jobs ?? []);
    setJobsMeta({ scheduler_enabled: j.scheduler_enabled, timezone: j.timezone });
  }, []);

  useEffect(() => {
    void loadAll().catch((e: unknown) => setNote(e instanceof Error ? e.message : 'Load failed'));
    return () => sourceRef.current?.close();
  }, [loadAll]);

  useEffect(() => {
    if (tab !== 'feed') return;
    const es = new EventSource(channelsApi.streamUrl());
    sourceRef.current = es;
    es.addEventListener('alert', (ev) => {
      try {
        const data = JSON.parse((ev as MessageEvent).data) as Record<string, unknown>;
        setFeed((f) => [`${new Date().toLocaleTimeString()} · ${data.channel ?? 'inapp'} · ${String(data.title ?? 'notification')}`, ...f].slice(0, 30));
      } catch {
        /* ignore malformed frames */
      }
    });
    es.onerror = () => es.close();
    return () => es.close();
  }, [tab]);

  const act = async (key: string, fn: () => Promise<unknown>, done: string) => {
    setBusy(key);
    setNote(null);
    try {
      await fn();
      setNote(done);
      await loadAll();
    } catch (e) {
      setNote(e instanceof Error ? e.message : 'Action failed');
    } finally {
      setBusy(null);
    }
  };

  const patch = async (key: string, value: unknown) => {
    try {
      await channelsApi.setPreferences({ [key]: value });
      setPrefs(await channelsApi.preferences());
    } catch (e) {
      setNote(e instanceof Error ? e.message : 'Preference update failed');
    }
  };

  const toggle = (key: string, current: unknown, label: string) => (
    <label className="flex items-center justify-between gap-3 py-2 text-sm text-slate-600 dark:text-slate-300">
      <span>{label}</span>
      <input type="checkbox" checked={Boolean(current)} onChange={(e) => void patch(key, e.target.checked)} className="h-4 w-4 accent-indigo-600" />
    </label>
  );

  const q = status?.outbox?.by_status;
  const sev = (['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'] as const).map((s) => ({ s, chans: status?.policy?.[s] ?? [] }));

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-white">Notification Automation</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            In-app · e-mail · SMS · WhatsApp, driven by the scheduler and the risk engine. Timezone {status?.timezone ?? '—'}
            {jobsMeta && !jobsMeta.scheduler_enabled ? ' · scheduler OFF (jobs run on demand only)' : ''}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button onClick={() => void act('flush', channelsApi.flush, 'Delivery worker drained the queue.')} disabled={busy === 'flush'} className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50">
            <Send className="h-4 w-4" /> {busy === 'flush' ? 'Sending…' : 'Flush queue now'}
          </button>
          <button onClick={() => void act('test', () => channelsApi.test(), 'Test messages dispatched to your active channels.')} disabled={busy === 'test'} className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 dark:border-slate-700 dark:text-slate-200">
            <RefreshCw className={`h-4 w-4 ${busy === 'test' ? 'animate-spin' : ''}`} /> Send test
          </button>
          {isOperator && (
            <button onClick={() => void act('purge', channelsApi.purge, 'Retention purge complete.')} disabled={busy === 'purge'} className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-500 hover:text-rose-600 dark:border-slate-700">
              <Trash2 className="h-4 w-4" /> Purge old
            </button>
          )}
        </div>
      </header>

      {note && <div className="rounded-lg bg-slate-100 px-4 py-2 text-sm text-slate-700 dark:bg-slate-800 dark:text-slate-200">{note}</div>}

      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {(['inapp', 'email', 'sms', 'whatsapp'] as const).map((c) => {
          const info = status?.channels?.[c];
          const configured = (info?.chain ?? []).filter((h) => h.configured).map((h) => h.provider);
          const Icon = CHANNEL_ICON[c];
          return (
            <div key={c} className="rounded-xl border border-slate-200 p-4 dark:border-slate-800">
              <div className="flex items-center justify-between">
                <span className="inline-flex items-center gap-2 text-sm font-semibold uppercase text-slate-800 dark:text-slate-100">
                  <Icon className="h-4 w-4" /> {c}
                </span>
                <span
                  className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase ring-1 ${
                    info?.live ? 'bg-emerald-500/10 text-emerald-600 ring-emerald-500/30' : 'bg-slate-500/10 text-slate-500 ring-slate-500/30'
                  }`}
                >
                  {info?.live ? 'live' : 'dev outbox'}
                </span>
              </div>
              <p className="mt-2 text-xs text-slate-500">{info?.will_use ?? 'not configured'}</p>
              <p className="mt-1 text-[11px] uppercase tracking-wide text-slate-400">
                {info?.simulated_only ? 'previews only - add credentials to go live' : configured.length ? `configured: ${configured.join(', ')}` : 'in-app document store'}
              </p>
            </div>
          );
        })}
      </section>

      <section className="grid gap-4 lg:grid-cols-3">
        <div className="rounded-xl border border-slate-200 p-5 dark:border-slate-800">
          <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100">Delivery queue</h2>
          <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
            {[
              { k: 'total', v: status?.outbox?.total },
              ...Object.entries(q ?? {}).slice(0, 3).map(([k, v]) => ({ k, v })),
            ].map((x) => (
              <div key={x.k} className="rounded-lg bg-slate-50 px-3 py-2 dark:bg-slate-800/60">
                <div className="text-[11px] uppercase tracking-wide text-slate-400">{x.k}</div>
                <div className="text-lg font-semibold tabular-nums text-slate-800 dark:text-slate-100">{x.v ?? 0}</div>
              </div>
            ))}
          </div>
          <h3 className="mt-5 text-xs font-semibold uppercase tracking-wide text-slate-400">Channel policy</h3>
          <ul className="mt-2 space-y-1 text-xs text-slate-600 dark:text-slate-300">
            {sev.map((x) => (
              <li key={x.s} className="flex justify-between">
                <span className="font-medium">{x.s}</span>
                <span>{x.chans.join(' · ') || 'in-app only'}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded-xl border border-slate-200 p-5 dark:border-slate-800">
          <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100">My channels & consent</h2>
          {!prefs ? (
            <p className="mt-2 text-sm text-slate-500">Loading…</p>
          ) : (
            <div className="mt-2">
              {toggle('email_enabled', prefs.preferences.email_enabled, 'E-mail enabled')}
              {toggle('sms_enabled', prefs.preferences.sms_enabled, 'SMS enabled')}
              {toggle('whatsapp_enabled', prefs.preferences.whatsapp_enabled, 'WhatsApp enabled')}
              {toggle('whatsapp_opt_in', prefs.preferences.whatsapp_opt_in, 'WhatsApp opt-in (required by Meta)')}
              {toggle('quiet_hours_enabled', prefs.preferences.quiet_hours_enabled, `Quiet hours (${String(prefs.preferences.quiet_hours ?? '22:30-07:00')})`)}
              <label className="mt-2 block text-xs font-medium text-slate-600 dark:text-slate-300">
                Phone (E.164)
                <input
                  defaultValue={String(prefs.preferences.phone ?? '')}
                  onBlur={(e) => e.target.value && void patch('phone', e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
                  placeholder="+919876543210"
                />
              </label>
              <label className="mt-3 block text-xs font-medium text-slate-600 dark:text-slate-300">
                Digest mode
                <select
                  value={String(prefs.preferences.digest_mode ?? 'none')}
                  onChange={(e) => void patch('digest_mode', e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
                >
                  {['none', 'daily', 'weekly'].map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
              </label>
              <div className="mt-3 grid grid-cols-3 gap-2">
                {(['email', 'sms', 'whatsapp'] as const).map((c) => (
                  <label key={c} className="text-[11px] font-medium text-slate-500">
                    min {c}
                    <select
                      value={String(prefs.preferences[`min_severity_${c}` as keyof typeof prefs.preferences] ?? 'MEDIUM')}
                      onChange={(e) => void patch(`min_severity_${c}`, e.target.value)}
                      className="mt-1 w-full rounded-md border border-slate-200 px-2 py-1 text-xs dark:border-slate-700 dark:bg-slate-900"
                    >
                      {['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].map((s) => (
                        <option key={s}>{s}</option>
                      ))}
                    </select>
                  </label>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="rounded-xl border border-slate-200 p-5 dark:border-slate-800">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-800 dark:text-slate-100">
            <Clock className="h-4 w-4" /> Scheduled jobs
          </h2>
          <ul className="mt-3 max-h-80 space-y-2 overflow-y-auto pr-1">
            {jobs.map((j) => (
              <li key={j.id} className="flex items-start justify-between gap-2 rounded-lg bg-slate-50 px-3 py-2 dark:bg-slate-800/60">
                <div>
                  <div className="text-xs font-semibold text-slate-700 dark:text-slate-200">{j.title}</div>
                  <div className="text-[11px] text-slate-500">
                    {j.schedule} · {j.purpose}
                  </div>
                </div>
                {isOperator && (
                  <button
                    title="Run now"
                    onClick={() => void act(`job:${j.id}`, () => channelsApi.runJob(j.id), `${j.title} finished.`)}
                    disabled={busy === `job:${j.id}`}
                    className="rounded-md border border-slate-200 p-1.5 text-slate-500 hover:text-indigo-600 disabled:opacity-40 dark:border-slate-700"
                  >
                    <Play className="h-3.5 w-3.5" />
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 dark:border-slate-800">
        <div className="flex gap-1 border-b border-slate-200 px-3 py-2 dark:border-slate-800">
          {[
            { id: 'queue', label: 'Outbox', icon: Send },
            { id: 'ledger', label: 'Delivery ledger', icon: CheckCircle2 },
            { id: 'feed', label: 'Live feed', icon: Radio },
          ].map((t) => (
            <button
              key={t.id}
              onClick={() => {
                setTab(t.id as typeof tab);
                if (t.id === 'ledger' && ledger.length === 0) void channelsApi.deliveries(50).then((r) => setLedger(r.items ?? []));
              }}
              className={`inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium ${
                tab === t.id ? 'bg-indigo-50 text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-300' : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              <t.icon className="h-3.5 w-3.5" /> {t.label}
            </button>
          ))}
        </div>
        <div className="overflow-x-auto p-3">
          {tab === 'queue' && (
            <table className="min-w-full text-xs">
              <thead className="text-left uppercase tracking-wide text-slate-400">
                <tr>
                  <th className="px-2 py-1">When</th>
                  <th className="px-2 py-1">Channel</th>
                  <th className="px-2 py-1">Kind</th>
                  <th className="px-2 py-1">Subject</th>
                  <th className="px-2 py-1">Status</th>
                  <th className="px-2 py-1">Notes</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {rows.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-2 py-8 text-center text-slate-500">
                      Queue empty — every message has been delivered.
                    </td>
                  </tr>
                )}
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td className="whitespace-nowrap px-2 py-1 text-slate-500">{String(r.created_at ?? '').replace('T', ' ').slice(0, 16)}</td>
                    <td className="px-2 py-1 font-medium text-slate-700 dark:text-slate-200">{r.channel}</td>
                    <td className="px-2 py-1 text-slate-500">{r.kind}</td>
                    <td className="max-w-[24rem] truncate px-2 py-1 text-slate-600 dark:text-slate-300">{r.subject ?? r.text}</td>
                    <td className="px-2 py-1">
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1 ${STATUS_TONE[r.status] ?? 'bg-slate-500/10 text-slate-500 ring-slate-500/30'}`}>
                        {r.status} · {r.attempts}
                      </span>
                    </td>
                    <td className="px-2 py-1 text-slate-400">{r.defer_reason || r.last_error || ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {tab === 'ledger' && (
            <table className="min-w-full text-xs">
              <thead className="text-left uppercase tracking-wide text-slate-400">
                <tr>
                  <th className="px-2 py-1">When</th>
                  <th className="px-2 py-1">Channel</th>
                  <th className="px-2 py-1">Provider</th>
                  <th className="px-2 py-1">To</th>
                  <th className="px-2 py-1">Status</th>
                  <th className="px-2 py-1">ms</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {ledger.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-2 py-8 text-center text-slate-500">
                      No attempts recorded yet.
                    </td>
                  </tr>
                )}
                {ledger.map((r, i) => (
                  <tr key={String(r.id ?? i)}>
                    <td className="whitespace-nowrap px-2 py-1 text-slate-500">{String(r.created_at ?? '').replace('T', ' ').slice(0, 16)}</td>
                    <td className="px-2 py-1 text-slate-700 dark:text-slate-200">{String(r.channel ?? '')}</td>
                    <td className="px-2 py-1 text-slate-500">{String(r.provider ?? '')}</td>
                    <td className="px-2 py-1 text-slate-500">{String(r.address ?? '')}</td>
                    <td className="px-2 py-1">
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1 ${STATUS_TONE[String(r.status)] ?? 'bg-slate-500/10 text-slate-500 ring-slate-500/30'}`}>
                        {String(r.status)}
                      </span>
                    </td>
                    <td className="px-2 py-1 tabular-nums text-slate-400">{String(r.latency_ms ?? '')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {tab === 'queue' && artifacts.length > 0 && (
            <p className="mt-2 px-2 text-[11px] text-slate-400">
              Simulated deliveries are written as real files for demos ({artifacts.length} artifact(s), newest:{' '}
              {artifacts
                .slice(0, 3)
                .map((a) => a.name)
                .join(', ')}
              ).
            </p>
          )}
          {tab === 'feed' && (
            <div className="px-2 py-3">
              <p className="mb-2 text-xs text-slate-500">
                Subscribed to <code>/channels/stream</code> (SSE). New in-app alerts for your account appear here without a refresh.
              </p>
              <ul className="space-y-1 text-xs text-slate-600 dark:text-slate-300">
                {feed.length === 0 ? <li className="text-slate-400">Waiting for events…</li> : feed.map((f) => <li key={f}>{f}</li>)}
              </ul>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
