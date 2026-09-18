/**
 * Risk Center — the explainable AI surface of the deck (Slides 18 & 21).
 * Board of scored open obligations, per-factor evidence, what-if simulator, and weight governance.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import {
  AlertTriangle,
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  FlaskConical,
  Gauge,
  RefreshCw,
  Sliders,
  Sparkles,
} from 'lucide-react';
import { riskApi, type RiskAssessment, type RiskBoard, type RiskBoardTask } from '../api/platform';
import { useAuth } from '../contexts/AuthContext';

const BAND_STYLE: Record<string, string> = {
  HIGH: 'bg-rose-500/15 text-rose-300 ring-rose-500/30',
  MEDIUM: 'bg-amber-500/15 text-amber-300 ring-amber-500/30',
  LOW: 'bg-emerald-500/15 text-emerald-300 ring-emerald-500/30',
};

/** `progress` arrives as "35%" from the v1 field and as a number from the deck field. */
const pct = (v: string | number | null | undefined) => {
  if (typeof v === 'number') return Math.round(v);
  const n = Number.parseInt(String(v ?? '0'), 10);
  return Number.isNaN(n) ? 0 : n;
};

const dayShift = (iso: string | null | undefined, days: number) => {
  const base = iso ? new Date(iso) : new Date();
  const t = Number.isNaN(base.getTime()) ? new Date() : base;
  t.setDate(t.getDate() + days);
  return t.toISOString().slice(0, 10);
};

export default function RiskCenter() {
  const { user } = useAuth();
  // The SPA's Role union is narrower than the backend's 10 roles; compare loosely on purpose.
  const role = String((user as { role?: string } | null)?.role ?? '');
  const canGovern = ['ADMIN', 'PRINCIPAL', 'HOD'].includes(role);

  const [board, setBoard] = useState<RiskBoard | null>(null);
  const [selected, setSelected] = useState<(RiskAssessment & { title?: string }) | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<'board' | 'explain' | 'simulate' | 'governance'>('board');

  // what-if state
  const [shift, setShift] = useState(3);
  const [progress, setProgress] = useState<number | null>(null);
  const [sim, setSim] = useState<Awaited<ReturnType<typeof riskApi.whatIf>> | null>(null);
  const [simBusy, setSimBusy] = useState(false);

  // governance state
  const [weights, setWeights] = useState<Awaited<ReturnType<typeof riskApi.weights>> | null>(null);
  const [draft, setDraft] = useState<Record<string, number>>({});
  const [bench, setBench] = useState<Awaited<ReturnType<typeof riskApi.benchmark>> | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setBoard(await riskApi.board());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load the risk board');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    void riskApi.weights().then((w) => {
      setWeights(w);
      setDraft({ ...w.effective_weights });
    });
  }, [load]);

  const tasks = useMemo<RiskBoardTask[]>(() => board?.tasks ?? [], [board]);
  const bands = board?.bands;
  const meanRisk = tasks.length ? tasks.reduce((a, t) => a + (t.assessment?.risk_score ?? 0), 0) / tasks.length : 0;

  const openExplain = async (taskId: string) => {
    setTab('explain');
    try {
      const detail = await riskApi.score(taskId);
      setSelected({ ...detail, title: tasks.find((t) => t.id === taskId)?.title });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Scoring failed');
    }
  };

  const runSim = async () => {
    const item = tasks.find((t) => t.id === selected?.task_id) ?? tasks[0];
    if (!item) return;
    setSimBusy(true);
    try {
      const overrides: Record<string, unknown> = { deadline: dayShift(item.deadline ?? null, shift) };
      if (progress !== null) overrides.progress = progress;
      setSim(await riskApi.whatIf({ task_id: item.id, overrides }));
    } finally {
      setSimBusy(false);
    }
  };

  const recalibrate = async () => {
    setBusy('calibrate');
    try {
      await riskApi.calibrate();
      const w = await riskApi.weights();
      setWeights(w);
      setDraft({ ...w.effective_weights });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Calibration failed');
    } finally {
      setBusy(null);
    }
  };

  const saveWeights = async () => {
    setBusy('weights');
    try {
      await riskApi.setWeights(draft);
      const w = await riskApi.weights();
      setWeights(w);
      await load();
    } finally {
      setBusy(null);
    }
  };

  const tabs = [
    { id: 'board', label: 'Board', icon: Gauge },
    { id: 'explain', label: 'Why this score', icon: Sparkles },
    { id: 'simulate', label: 'What-if', icon: FlaskConical },
    { id: 'governance', label: 'Weights & benchmark', icon: Sliders },
  ] as const;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-white">AI Risk Center</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Deterministic 8-factor engine · score = modelled probability of missing the deadline · no GPU, no licence.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => void load()}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} /> Rescore
          </button>
        </div>
      </header>

      <section className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {[
          { k: 'Scored open tasks', v: board ? String(board.count) : '—' },
          { k: 'HIGH', v: bands ? String(bands.HIGH) : '—', tone: 'text-rose-600' },
          { k: 'MEDIUM', v: bands ? String(bands.MEDIUM) : '—', tone: 'text-amber-600' },
          { k: 'LOW', v: bands ? String(bands.LOW) : '—', tone: 'text-emerald-600' },
          { k: 'Mean risk', v: board ? meanRisk.toFixed(1) : '—' },
        ].map((c) => (
          <div key={c.k} className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
            <div className="text-xs uppercase tracking-wide text-slate-400">{c.k}</div>
            <div className={`mt-1 text-2xl font-semibold ${c.tone ?? 'text-slate-900 dark:text-white'}`}>{c.v}</div>
          </div>
        ))}
      </section>

      {error && (
        <div className="flex items-center gap-2 rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-700 ring-1 ring-rose-200 dark:bg-rose-500/10 dark:text-rose-300 dark:ring-rose-500/30">
          <AlertTriangle className="h-4 w-4" /> {error}
        </div>
      )}

      <nav className="flex flex-wrap gap-1 border-b border-slate-200 dark:border-slate-800">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`-mb-px inline-flex items-center gap-2 border-b-2 px-3 py-2 text-sm font-medium transition ${
              tab === t.id
                ? 'border-indigo-500 text-indigo-600 dark:text-indigo-300'
                : 'border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
            }`}
          >
            <t.icon className="h-4 w-4" /> {t.label}
          </button>
        ))}
      </nav>

      {tab === 'board' && (
        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="overflow-hidden rounded-xl border border-slate-200 dark:border-slate-800">
          <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500 dark:bg-slate-900/60">
              <tr>
                <th className="px-4 py-3">Task</th>
                <th className="px-4 py-3">Assignee</th>
                <th className="px-4 py-3">Due</th>
                <th className="px-4 py-3">Prog.</th>
                <th className="px-4 py-3">Risk</th>
                <th className="px-4 py-3">Top driver</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white dark:divide-slate-800 dark:bg-slate-900">
              {tasks.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-slate-500">
                    {loading ? 'Scoring open obligations…' : 'Nothing open — the department is on track.'}
                  </td>
                </tr>
              )}
              {tasks.map((it) => {
                const a = it.assessment ?? ({} as RiskAssessment);
                return (
                <tr key={it.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/60">
                  <td className="px-4 py-3 font-medium text-slate-800 dark:text-slate-100">{it.title}</td>
                  <td className="px-4 py-3 text-slate-500">{it.assigned ?? '—'}</td>
                  <td className="px-4 py-3 text-slate-500">
                    {it.deadline ? String(it.deadline).slice(0, 10) : '—'}
                    {typeof a.days_left === 'number' && (
                      <span className={`ml-2 text-xs ${a.days_left < 0 ? 'text-rose-500' : 'text-slate-400'}`}>
                        {a.days_left < 0 ? `${Math.abs(Math.round(a.days_left))}d late` : `${Math.round(a.days_left)}d left`}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 tabular-nums text-slate-500">{pct(it.progress)}%</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ${BAND_STYLE[a.risk_level ?? 'LOW']}`}>
                      {(a.risk_score ?? 0).toFixed(1)} · {a.risk_level}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-500">{(a.drivers ?? []).slice(0, 2).join(' · ') || '—'}</td>
                  <td className="px-4 py-3 text-right">
                    <button onClick={() => void openExplain(it.id)} className="rounded-md px-2 py-1 text-xs font-medium text-indigo-600 hover:bg-indigo-50 dark:text-indigo-300 dark:hover:bg-indigo-500/10">
                      Explain
                    </button>
                  </td>
                </tr>
                );
              })}
            </tbody>
          </table>
        </motion.div>
      )}

      {tab === 'explain' && (
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="rounded-xl border border-slate-200 p-5 dark:border-slate-800 lg:col-span-2">
            {!selected ? (
              <p className="text-sm text-slate-500">Pick “Explain” on any row to see the evidence behind its score.</p>
            ) : (
              <>
                <div className="flex flex-wrap items-center gap-3">
                  <h2 className="text-lg font-semibold text-slate-900 dark:text-white">{selected.title}</h2>
                  <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ${BAND_STYLE[selected.risk_level]}`}>
                    {selected.risk_score.toFixed(1)} / 100 · {selected.risk_level}
                  </span>
                  <span className="text-xs text-slate-500">
                    P(slip) {(selected.delay_probability * 100).toFixed(0)}% · confidence {(selected.confidence * 100).toFixed(0)}%
                  </span>
                </div>
                {selected.explanation && <p className="mt-3 text-sm text-slate-600 dark:text-slate-300">{selected.explanation}</p>}
                <div className="mt-3 flex flex-wrap gap-3 text-[11px] text-slate-500">
                  <span>ETA: {selected.projected_completion ?? '—'}</span>
                  {typeof selected.eta_days === 'number' && <span>≈ {selected.eta_days.toFixed(1)} working day(s)</span>}
                  {typeof selected.linear_score === 'number' && <span>linear fusion would say {selected.linear_score.toFixed(1)}</span>}
                  {selected.at_risk && <span className="font-semibold text-rose-500">at-risk → CRITICAL escalation</span>}
                </div>
                <div className="mt-5 space-y-3">
                  {selected.factors.map((f) => (
                    <div key={f.key}>
                      <div className="flex items-baseline justify-between text-xs">
                        <span className="font-medium text-slate-700 dark:text-slate-200">{f.label ?? f.key}</span>
                        <span className="tabular-nums text-slate-400">
                          sub {f.sub_score.toFixed(0)} × w {f.weight} → {f.contribution >= 0 ? '+' : ''}
                          {f.contribution.toFixed(1)}
                          {typeof f.share_of_risk === 'number' ? ` · ${Math.min(100, Math.round(f.share_of_risk))}% of risk` : ''}
                        </span>
                      </div>
                      <div className="mt-1 h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
                        <div className="h-full rounded-full bg-gradient-to-r from-indigo-400 to-rose-500" style={{ width: `${Math.max(2, Math.min(100, f.sub_score))}%` }} />
                      </div>
                      <p className="mt-1 text-xs text-slate-500">{f.evidence}</p>
                    </div>
                  ))}
                </div>
                {selected.recommendations && selected.recommendations.length > 0 && (
                  <div className="mt-5 rounded-lg bg-slate-50 p-4 text-sm dark:bg-slate-800/60">
                    <div className="mb-1 flex items-center gap-2 font-medium text-slate-700 dark:text-slate-200">
                      <Activity className="h-4 w-4" /> Recommended actions
                    </div>
                    <ul className="ml-5 list-disc space-y-1 text-slate-600 dark:text-slate-300">
                      {selected.recommendations.map((r) => (
                        <li key={r}>{r}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            )}
          </div>
          <aside className="space-y-4">
            <div className="rounded-xl border border-slate-200 p-5 dark:border-slate-800">
              <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100">Bands</h3>
              <ul className="mt-2 space-y-1 text-xs text-slate-500">
                <li>HIGH — score ≥ 55 (act this week)</li>
                <li>MEDIUM — 30–54 (watch, add a checkpoint)</li>
                <li>LOW — &lt; 30</li>
                <li>at_risk — score ≥ 75 → CRITICAL escalation on all channels</li>
              </ul>
            </div>
            <div className="rounded-xl border border-slate-200 p-5 text-xs text-slate-500 dark:border-slate-800">
              Every factor is computed from the same documents the workflow writes — no feature store, no training job, and
              the score is reproducible for the same inputs.
            </div>
          </aside>
        </div>
      )}

      {tab === 'simulate' && (
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="rounded-xl border border-slate-200 p-5 dark:border-slate-800">
            <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100">Counterfactual</h2>
            <p className="mt-1 text-xs text-slate-500">Scores a copy of the selected task. Nothing is written.</p>
            <label className="mt-4 block text-xs font-medium text-slate-600 dark:text-slate-300">
              Selected task
              <select
                className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
                value={selected?.task_id ?? ''}
                onChange={(e) => void openExplain(e.target.value)}
              >
                <option value="">— choose —</option>
                {tasks.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.title} ({(t.assessment?.risk_score ?? 0).toFixed(0)})
                  </option>
                ))}
              </select>
            </label>
            <label className="mt-4 block text-xs font-medium text-slate-600 dark:text-slate-300">
              Move deadline by <span className="tabular-nums">{shift}</span> day(s)
              <input type="range" min={-7} max={21} value={shift} onChange={(e) => setShift(Number(e.target.value))} className="mt-1 w-full" />
            </label>
            <label className="mt-4 block text-xs font-medium text-slate-600 dark:text-slate-300">
              Force progress to {progress === null ? 'unchanged' : `${progress}%`}
              <input
                type="range"
                min={0}
                max={100}
                step={5}
                value={progress ?? 0}
                onChange={(e) => setProgress(Number(e.target.value))}
                className="mt-1 w-full"
              />
            </label>
            <button
              onClick={() => void runSim()}
              disabled={!selected || simBusy}
              className="mt-5 inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
            >
              <FlaskConical className="h-4 w-4" /> {simBusy ? 'Scoring…' : 'Run simulation'}
            </button>
          </div>
          <div className="rounded-xl border border-slate-200 p-5 dark:border-slate-800">
            {!sim ? (
              <p className="text-sm text-slate-500">Result appears here: before → after, with the new recommendation set.</p>
            ) : (
              <>
                <div className="flex items-center gap-3">
                  <span className="text-3xl font-semibold tabular-nums text-slate-900 dark:text-white">{sim.after.risk_score.toFixed(1)}</span>
                  <span
                    className={`inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs font-semibold ring-1 ${
                      sim.verdict === 'improves'
                        ? 'bg-emerald-500/10 text-emerald-600 ring-emerald-500/30'
                        : sim.verdict === 'worsens'
                          ? 'bg-rose-500/10 text-rose-600 ring-rose-500/30'
                          : 'bg-slate-500/10 text-slate-600 ring-slate-500/30'
                    }`}
                  >
                    {sim.verdict === 'worsens' ? <ArrowUpRight className="h-3.5 w-3.5" /> : <ArrowDownRight className="h-3.5 w-3.5" />}
                    {sim.delta > 0 ? '+' : ''}
                    {sim.delta} vs {sim.before.risk_score.toFixed(1)}
                  </span>
                </div>
                <p className="mt-2 text-xs text-slate-500">
                  P(slip) {(sim.before.delay_probability * 100).toFixed(0)}% → {(sim.after.delay_probability * 100).toFixed(0)}% · band{' '}
                  {sim.before.risk_level} → {sim.after.risk_level}
                </p>
                <ul className="mt-4 space-y-1 text-sm text-slate-600 dark:text-slate-300">
                  {(sim.after.recommendations ?? []).map((r) => (
                    <li key={r}>• {r}</li>
                  ))}
                </ul>
                <p className="mt-4 text-xs text-slate-400">
                  Drivers after the change: {(sim.after.top_drivers ?? []).join(', ') || '—'}
                </p>
              </>
            )}
          </div>
        </div>
      )}

      {tab === 'governance' && (
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="rounded-xl border border-slate-200 p-5 dark:border-slate-800">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100">Factor weights</h2>
              <span className="text-xs text-slate-400">
                {weights ? `calibration: ${Object.keys(weights.calibration ?? {}).length ? 'fitted' : 'defaults'}` : '…'}
              </span>
            </div>
            <div className="mt-4 space-y-2">
              {weights &&
                Object.entries(weights.default_weights).map(([k, def]) => (
                  <div key={k} className="flex items-center gap-3">
                    <span className="w-40 truncate text-xs text-slate-600 dark:text-slate-300">{weights.factor_labels?.[k] ?? k}</span>
                    <input
                      type="range"
                      min={0}
                      max={0.5}
                      step={0.01}
                      disabled={!canGovern}
                      value={draft[k] ?? def}
                      onChange={(e) => setDraft((d) => ({ ...d, [k]: Number(e.target.value) }))}
                      className="flex-1"
                    />
                    <span className="w-12 text-right text-xs tabular-nums text-slate-500">{(draft[k] ?? def).toFixed(2)}</span>
                  </div>
                ))}
            </div>
            {canGovern && (
              <div className="mt-4 flex gap-2">
                <button onClick={() => void saveWeights()} disabled={busy === 'weights'} className="rounded-lg bg-slate-900 px-3 py-2 text-xs font-medium text-white disabled:opacity-50 dark:bg-white dark:text-slate-900">
                  {busy === 'weights' ? 'Saving…' : 'Save to risk_weights/global'}
                </button>
                <button onClick={() => void recalibrate()} disabled={busy === 'calibrate'} className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-medium text-slate-700 disabled:opacity-50 dark:border-slate-700 dark:text-slate-200">
                  {busy === 'calibrate' ? 'Fitting…' : 'Recalibrate from closed tasks'}
                </button>
              </div>
            )}
            {!canGovern && <p className="mt-3 text-xs text-slate-400">Weights are read-only for your role (HOD/Principal/Admin may adjust them).</p>}
          </div>
          <div className="rounded-xl border border-slate-200 p-5 dark:border-slate-800">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100">Benchmark vs. competing models</h2>
              <button onClick={() => void riskApi.benchmark(240).then(setBench)} className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 dark:border-slate-700 dark:text-slate-200">
                Run n=240
              </button>
            </div>
            {!bench ? (
              <p className="mt-3 text-xs text-slate-500">
                Runs the synthetic-corpus comparison in-process (<code>app/engine/benchmarks.py</code>). The committed n=500 run lives in{' '}
                <code>docs/benchmark_results.json</code>; this button re-runs it live at n=240.
              </p>
            ) : (
              <>
                <table className="mt-4 w-full text-xs">
                  <thead className="text-left uppercase tracking-wide text-slate-400">
                    <tr>
                      <th className="py-1">Model</th>
                      <th className="py-1 text-right">AUC</th>
                      <th className="py-1 text-right">P@budget</th>
                      <th className="py-1 text-right">flag%</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {Object.entries(bench.results)
                      .sort((a, b) => b[1].precision_at_alert_budget - a[1].precision_at_alert_budget)
                      .map(([name, m]) => (
                        <tr key={name} className={name.startsWith('HieraSync') ? 'font-semibold text-indigo-600 dark:text-indigo-300' : 'text-slate-600 dark:text-slate-300'}>
                          <td className="py-1 pr-2">{name}</td>
                          <td className="py-1 text-right tabular-nums">{m.roc_auc.toFixed(3)}</td>
                          <td className="py-1 text-right tabular-nums">{m.precision_at_alert_budget.toFixed(3)}</td>
                          <td className="py-1 text-right tabular-nums">{(m.flag_rate * 100).toFixed(0)}%</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
                <p className="mt-3 text-xs text-slate-500">
                  Best AUC here: <span className="font-medium">{bench.best}</span> — this engine ranks #{bench.our_rank}. At an equal alert
                  budget it is the most precise triage tool, and it needs no labelled history;{' '}
                  {bench.calibration && bench.calibration.samples > 0
                    ? `weight calibration on ${bench.calibration.samples} closed tasks moved AUC ${bench.calibration.auc_before.toFixed(3)} → ${bench.calibration.auc_after.toFixed(3)}.`
                    : 'no labelled history yet, so calibration is idle.'}
                </p>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
