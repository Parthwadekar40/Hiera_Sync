/**
 * Analytics — department scorecard, faculty performance, forecast and one-click exports (Slide 19).
 * Every number on this page carries its formula: the API publishes them, we render them.
 */
import { useCallback, useEffect, useState } from 'react';
import { BarChart, Bar, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Camera, Download, Gauge, Info, Table2, TrendingUp, Users } from 'lucide-react';
import { channelsApi, metricsApi, type Scorecard } from '../api/platform';
import { useAuth } from '../contexts/AuthContext';

const WINDOW = [7, 30, 90] as const;

type Faculty = Awaited<ReturnType<typeof metricsApi.faculty>>;
type Depts = Awaited<ReturnType<typeof metricsApi.departments>>;
type Forecast = Awaited<ReturnType<typeof metricsApi.forecast>>;
type Trend = Awaited<ReturnType<typeof metricsApi.riskTrend>>;

const num = (v: unknown, suffix = '') => (typeof v === 'number' ? `${v.toFixed(v % 1 ? 1 : 0)}${suffix}` : v === null || v === undefined || v === '' ? '—' : `${String(v)}${suffix}`);

export default function Analytics() {
  const { user } = useAuth();
  const role = String((user as { role?: string } | null)?.role ?? '');
  const canExport = ['ADMIN', 'PRINCIPAL', 'HOD'].includes(role);

  const [days, setDays] = useState<number>(30);
  const [card, setCard] = useState<Scorecard | null>(null);
  const [fac, setFac] = useState<Faculty | null>(null);
  const [dept, setDept] = useState<Depts | null>(null);
  const [fc, setFc] = useState<Forecast | null>(null);
  const [trend, setTrend] = useState<Trend | null>(null);
  const [showFormulas, setShowFormulas] = useState(false);
  const [dataset, setDataset] = useState<string>('tasks');
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [c, f, d, p, t] = await Promise.all([
      metricsApi.scorecard(days),
      metricsApi.faculty(days),
      metricsApi.departments(days),
      metricsApi.forecast(Math.max(4, Math.round(days / 7))),
      metricsApi.riskTrend(Math.max(30, days)),
    ]);
    setCard(c);
    setFac(f);
    setDept(d);
    setFc(p);
    setTrend(t);
  }, [days]);

  useEffect(() => {
    void load().catch((e: unknown) => setNote(e instanceof Error ? e.message : 'Failed to load analytics'));
  }, [load]);

  const download = async (format: 'csv' | 'json') => {
    setBusy(`export:${format}`);
    try {
      const file = await metricsApi.download(dataset, format, Math.max(90, days));
      setNote(`Saved ${file}`);
    } catch (e) {
      setNote(e instanceof Error ? e.message : 'Export failed (your role may not hold export_reports)');
    } finally {
      setBusy(null);
    }
  };

  const trendData = (trend?.items ?? []).map((p) => ({
    day: String(p.taken_at).slice(5, 10),
    HIGH: p.bands?.HIGH ?? p.HIGH ?? 0,
    MEDIUM: p.bands?.MEDIUM ?? p.MEDIUM ?? 0,
    LOW: p.bands?.LOW ?? p.LOW ?? 0,
  }));

  const kpi = (label: string, value: string, hint?: string, tone = 'text-slate-900 dark:text-white') => (
    <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <div className="text-[11px] uppercase tracking-wide text-slate-400">{label}</div>
      <div className={`mt-1 text-2xl font-semibold tabular-nums ${tone}`}>{value}</div>
      {hint && <div className="mt-1 text-[11px] text-slate-400">{hint}</div>}
    </div>
  );

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-white">Department Analytics</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Scope: <span className="font-medium">{card?.analytics_scope ?? '—'}</span> · window{' '}
            {card ? `${card.window_days}d` : `${days}d`} · generated {card ? String(card.generated_at).replace('T', ' ').slice(0, 16) : '—'}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {WINDOW.map((w) => (
            <button
              key={w}
              onClick={() => setDays(w)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium ${days === w ? 'bg-indigo-600 text-white' : 'border border-slate-200 text-slate-600 dark:border-slate-700 dark:text-slate-300'}`}
            >
              {w}d
            </button>
          ))}
          <button onClick={() => setShowFormulas((v) => !v)} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 dark:border-slate-700 dark:text-slate-300">
            <Info className="h-3.5 w-3.5" /> formulas
          </button>
          <button
            onClick={() => {
              setBusy('snap');
              void metricsApi.snapshot().then(() => {
                setBusy(null);
                setNote('Risk snapshot recorded for the trend chart.');
                void load();
              });
            }}
            disabled={busy === 'snap' || !canExport}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 disabled:opacity-40 dark:border-slate-700 dark:text-slate-300"
          >
            <Camera className="h-3.5 w-3.5" /> record snapshot
          </button>
        </div>
      </header>

      {note && <div className="rounded-lg bg-slate-100 px-4 py-2 text-sm text-slate-700 dark:bg-slate-800 dark:text-slate-200">{note}</div>}

      {card && (
        <>
          <section className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
            {kpi('Open tasks', String(card.tasks.active), `${card.tasks.total} total in window`)}
            {kpi('On-time rate', num(card.tasks.on_time_rate, '%'), 'completed ≤ deadline', card.tasks.on_time_rate >= 80 ? 'text-emerald-600' : 'text-amber-600')}
            {kpi('Overdue', String(card.tasks.overdue), `avg ${num(card.tasks.avg_days_late, 'd late')}`, card.tasks.overdue > 0 ? 'text-rose-600' : 'text-emerald-600')}
            {kpi('HIGH risk', String(card.risk.high_risk_count), `${num(card.risk.mean_score)} mean score`, card.risk.high_risk_count > 0 ? 'text-rose-600' : 'text-emerald-600')}
            {kpi('Approval SLA', num(card.approvals.sla_compliance, '%'), `${card.approvals.pending} pending · ${card.approvals.breached_sla} breached`)}
            {kpi('Workload balance', num(card.workload.balance_index), `spread ${num(card.workload.spread)}`, card.workload.balance_index >= 70 ? 'text-emerald-600' : 'text-amber-600')}
          </section>

          {showFormulas && (
            <section className="rounded-xl border border-slate-200 p-4 dark:border-slate-800">
              <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-800 dark:text-slate-100">
                <Gauge className="h-4 w-4" /> How each figure is computed
              </h2>
              <dl className="mt-3 grid gap-2 text-xs md:grid-cols-2">
                {Object.entries(card.formulas ?? {}).map(([k, v]) => (
                  <div key={k} className="rounded-lg bg-slate-50 px-3 py-2 dark:bg-slate-800/60">
                    <dt className="font-mono text-[11px] text-indigo-600 dark:text-indigo-300">{k}</dt>
                    <dd className="mt-0.5 text-slate-600 dark:text-slate-300">{v}</dd>
                  </div>
                ))}
              </dl>
              {card.insights?.length > 0 && (
                <ul className="mt-3 space-y-1">
                  {card.insights.map((i) => (
                    <li key={i.text} className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600 dark:bg-slate-800/60 dark:text-slate-300">
                      <span className="mr-2 rounded bg-white px-1.5 py-0.5 text-[10px] font-semibold uppercase text-slate-500 ring-1 ring-slate-200">{i.severity}</span>
                      {i.text}
                      {i.action && <span className="ml-1 text-slate-400">→ {i.action}</span>}
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}

          <section className="grid gap-4 lg:grid-cols-2">
            <div className="rounded-xl border border-slate-200 p-4 dark:border-slate-800">
              <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-800 dark:text-slate-100">
                <TrendingUp className="h-4 w-4" /> Completions expected per week
              </h2>
              <div className="mt-3 h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={fc?.points ?? []}>
                    <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.2} />
                    <XAxis dataKey="week" tick={{ fontSize: 10 }} />
                    <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
                    <Tooltip contentStyle={{ fontSize: 12 }} />
                    <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <p className="mt-2 text-[11px] text-slate-400">
                Expected misses from the risk engine: {num(card.risk.projected_misses)} · mean confidence {num(Math.round(card.risk.mean_confidence * 100), '%')}
              </p>
            </div>

            <div className="rounded-xl border border-slate-200 p-4 dark:border-slate-800">
              <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-800 dark:text-slate-100">
                <Table2 className="h-4 w-4" /> Risk band trend
              </h2>
              {trendData.length < 2 ? (
                <p className="mt-6 text-sm text-slate-500">
                  Needs two or more snapshots. Press <span className="font-medium">record snapshot</span> (or wait for the 15-minute risk sweep) to start the series.
                </p>
              ) : (
                <div className="mt-3 h-56">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={trendData}>
                      <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.2} />
                      <XAxis dataKey="day" tick={{ fontSize: 10 }} />
                      <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
                      <Tooltip contentStyle={{ fontSize: 12 }} />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      <Line type="monotone" dataKey="HIGH" stroke="#f43f5e" strokeWidth={2} dot={false} />
                      <Line type="monotone" dataKey="MEDIUM" stroke="#f59e0b" strokeWidth={2} dot={false} />
                      <Line type="monotone" dataKey="LOW" stroke="#10b981" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}
              <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
                <select value={dataset} onChange={(e) => setDataset(e.target.value)} className="rounded-lg border border-slate-200 px-2 py-1.5 text-xs dark:border-slate-700 dark:bg-slate-900">
                  {metricsApi.datasets.map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))}
                </select>
                <button onClick={() => void download('csv')} disabled={!canExport || busy === 'export:csv'} className="inline-flex items-center gap-1.5 rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-40 dark:bg-white dark:text-slate-900">
                  <Download className="h-3.5 w-3.5" /> CSV
                </button>
                <button onClick={() => void download('json')} disabled={!canExport || busy === 'export:json'} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 disabled:opacity-40 dark:border-slate-700 dark:text-slate-300">
                  JSON
                </button>
                {!canExport && <span className="text-[11px] text-slate-400">export_reports is a HOD/Principal/Principal-of-institute capability</span>}
              </div>
            </div>
          </section>

          <section className="rounded-xl border border-slate-200 dark:border-slate-800">
            <h2 className="flex items-center gap-2 border-b border-slate-200 px-4 py-3 text-sm font-semibold text-slate-800 dark:border-slate-800 dark:text-slate-100">
              <Users className="h-4 w-4" /> Faculty performance & load
            </h2>
            <div className="overflow-x-auto">
              <table className="min-w-full text-xs">
                <thead className="bg-slate-50 text-left uppercase tracking-wide text-slate-400 dark:bg-slate-900/60">
                  <tr>
                    {['Name', 'Role', 'Open', 'Done', 'Late', 'On-time %', 'Index', 'Load'].map((h) => (
                      <th key={h} className="px-3 py-2">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {(fac?.items ?? []).map((f) => (
                    <tr key={f.user_id}>
                      <td className="px-3 py-2 font-medium text-slate-700 dark:text-slate-200">{f.name}</td>
                      <td className="px-3 py-2 text-slate-500">{f.role}</td>
                      <td className="px-3 py-2 tabular-nums text-slate-500">{f.active ?? 0}</td>
                      <td className="px-3 py-2 tabular-nums text-slate-500">{f.completed}</td>
                      <td className="px-3 py-2 tabular-nums text-slate-500">{f.overdue}</td>
                      <td className="px-3 py-2 tabular-nums text-slate-500">{num(f.on_time_rate, '%')}</td>
                      <td className="px-3 py-2">
                        <div className="flex items-center gap-2">
                          <div className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
                            <div className="h-full rounded-full bg-indigo-500" style={{ width: `${Math.max(2, Math.min(100, f.performance_index))}%` }} />
                          </div>
                          <span className="tabular-nums text-slate-600 dark:text-slate-300">{num(f.performance_index)}</span>
                        </div>
                      </td>
                      <td className="px-3 py-2 tabular-nums text-slate-500">{num(f.workload)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {fac?.note && <p className="border-t border-slate-200 px-4 py-2 text-[11px] text-slate-400 dark:border-slate-800">{fac.note}</p>}
          </section>

          <section className="rounded-xl border border-slate-200 dark:border-slate-800">
            <h2 className="border-b border-slate-200 px-4 py-3 text-sm font-semibold text-slate-800 dark:border-slate-800 dark:text-slate-100">Department rollup (accreditation view)</h2>
            <div className="overflow-x-auto">
              <table className="min-w-full text-xs">
                <thead className="bg-slate-50 text-left uppercase tracking-wide text-slate-400 dark:bg-slate-900/60">
                  <tr>
                    {['Department', 'Active', 'Completion %', 'On-time %', 'Overdue %', 'HIGH risk', 'Proj. misses', 'Approvals (pend/breach)', 'Balance', 'Health'].map((h) => (
                      <th key={h} className="px-3 py-2">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {(dept?.items ?? []).map((d) => (
                    <tr key={d.department_id}>
                      <td className="px-3 py-2 font-medium text-slate-700 dark:text-slate-200">{d.department}</td>
                      <td className="px-3 py-2 tabular-nums text-slate-500">{d.active_tasks}</td>
                      <td className="px-3 py-2 tabular-nums text-slate-500">{num(d.completion_rate, '%')}</td>
                      <td className="px-3 py-2 tabular-nums text-slate-500">{num(d.on_time_rate, '%')}</td>
                      <td className="px-3 py-2 tabular-nums text-slate-500">{num(d.overdue_rate, '%')}</td>
                      <td className="px-3 py-2 tabular-nums text-rose-600">{d.high_risk_tasks}</td>
                      <td className="px-3 py-2 tabular-nums text-slate-500">{num(d.projected_misses)}</td>
                      <td className="px-3 py-2 tabular-nums text-slate-500">
                        {d.approvals_pending} / <span className={d.approvals_breached ? 'text-rose-600' : ''}>{d.approvals_breached}</span>
                      </td>
                      <td className="px-3 py-2 tabular-nums text-slate-500">{num(d.workload_balance_index)}</td>
                      <td className="px-3 py-2 tabular-nums font-semibold text-slate-800 dark:text-slate-100">{num(d.health_index)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <p className="text-[11px] text-slate-400">
            Delivery health for the same window: {card.automation.delivered}/{card.automation.deliveries_total} delivered ({num(card.automation.delivery_success_rate, '%')}) ·{' '}
            {card.automation.simulated_only} simulated by the dev outbox · mean latency {num(Math.round(card.automation.mean_latency_ms), ' ms')} ·{' '}
            <button onClick={() => void channelsApi.flush().then((r) => setNote(`Flush: ${r.scanned} scanned, ${r.sent} sent.`))} className="underline hover:text-slate-600">
              flush queue now
            </button>
          </p>
        </>
      )}
    </div>
  );
}
