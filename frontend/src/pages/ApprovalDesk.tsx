/**
 * Approval Desk — the deck's core workflow as a working surface (Slide 15 + Slide 19).
 * Staged routing (HOD → Principal), per-kind SLA clock, mandatory rejection notes, delegation,
 * resubmission, and the hash-chained decision log with an integrity check.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import {
  BadgeCheck,
  CalendarClock,
  Check,
  FilePlus2,
  Link2,
  RefreshCw,
  RotateCcw,
  Send,
  ShieldAlert,
  ArrowRightLeft,
  X,
} from 'lucide-react';
import { workflowApi, type ApprovalDoc, type NewRequestPayload, type QueueItem } from '../api/platform';
import { useAuth } from '../contexts/AuthContext';

const SLA_TONE: Record<string, string> = {
  on_track: 'bg-emerald-500/10 text-emerald-600 ring-emerald-500/30',
  due_soon: 'bg-amber-500/10 text-amber-600 ring-amber-500/30',
  breached: 'bg-rose-500/10 text-rose-600 ring-rose-500/30',
  escalated: 'bg-fuchsia-500/10 text-fuchsia-600 ring-fuchsia-500/30',
};

const KINDS: Array<NewRequestPayload['kind']> = [
  'leave',
  'no_objection',
  'event',
  'purchase',
  'budget',
  'outcome_approval',
  'deadline_change',
  'joining',
  'generic',
];

const emptyForm: NewRequestPayload = { title: '', kind: 'leave', description: '', priority: 'Medium', amount: null, evidence: {} };

export default function ApprovalDesk() {
  const { user } = useAuth();
  const uid = (user as { id?: string } | null)?.id ?? '';

  const [queue, setQueue] = useState<{ role: string; counts: { total: number; breached: number; due_soon: number }; items: QueueItem[] } | null>(null);
  const [policies, setPolicies] = useState<Awaited<ReturnType<typeof workflowApi.policies>> | null>(null);
  const [funnel, setFunnel] = useState<Awaited<ReturnType<typeof workflowApi.funnel>> | null>(null);
  const [filter, setFilter] = useState<'all' | 'due_soon' | 'breached' | 'mine'>('all');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [doc, setDoc] = useState<ApprovalDoc | null>(null);
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ tone: 'ok' | 'err'; text: string } | null>(null);
  const [composing, setComposing] = useState(false);
  const [form, setForm] = useState<NewRequestPayload>(emptyForm);
  const [evidenceKey, setEvidenceKey] = useState('reason');
  const [evidenceVal, setEvidenceVal] = useState('');

  const refresh = useCallback(async () => {
    const [q, pol, fun] = await Promise.all([workflowApi.queue(), workflowApi.policies(), workflowApi.funnel()]);
    setQueue(q);
    setPolicies(pol);
    setFunnel(fun);
  }, []);

  useEffect(() => {
    void refresh().catch((e: unknown) => setMsg({ tone: 'err', text: e instanceof Error ? e.message : 'Failed to load the queue' }));
  }, [refresh]);

  useEffect(() => {
    if (!selectedId) return;
    void workflowApi.get(selectedId).then(setDoc).catch(() => setDoc(null));
  }, [selectedId]);

  const rows = useMemo(() => {
    const items = queue?.items ?? [];
    if (filter === 'all') return items;
    if (filter === 'mine') return items.filter((i) => i.requester_name === (user?.name ?? ''));
    return items.filter((i) => i.sla?.state === filter);
  }, [queue, filter, user?.name]);

  const run = async (key: string, fn: () => Promise<unknown>, done: string) => {
    setBusy(key);
    setMsg(null);
    try {
      const r = (await fn()) as { created_task?: { id: string; title: string } | false; next_actor?: string | null };
      const extra =
        r && typeof r === 'object' && r.created_task
          ? ` Task auto-created: ${r.created_task.id} — "${r.created_task.title}".`
          : r && typeof r === 'object' && r.next_actor
            ? ` Next: ${r.next_actor}.`
            : '';
      setMsg({ tone: 'ok', text: done + extra });
      if (selectedId) setDoc(await workflowApi.get(selectedId));
      await refresh();
      setNote('');
    } catch (e) {
      const err = e as { message?: string; data?: { detail?: { code?: string; message?: string } | string } };
      const detail = err.data?.detail;
      const code = typeof detail === 'object' && detail ? detail.code : undefined;
      setMsg({ tone: 'err', text: `${code ? code + ' — ' : ''}${(typeof detail === 'object' && detail?.message) || err.message || 'Rejected by the server'}` });
    } finally {
      setBusy(null);
    }
  };

  const submitNew = async () => {
    if (!form.title.trim()) {
      setMsg({ tone: 'err', text: 'A title is required.' });
      return;
    }
    await run('raise', async () => {
      const res = await workflowApi.raise({ ...form, evidence: evidenceVal ? { [evidenceKey]: evidenceVal, ...form.evidence } : form.evidence });
      setComposing(false);
      setForm(emptyForm);
      setEvidenceVal('');
      setSelectedId(res.id);
      return { created_task: false as const };
    }, `Request filed and routed to ${(policies?.policies.find((p) => p.kind === form.kind)?.stages[0] ?? 'HOD')}.`);
  };

  const policy = policies?.policies.find((p) => p.kind === (doc?.kind ?? ''));
  const stages = doc?.stages ?? policy?.stages ?? ['HOD'];

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-white">Approval Desk</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Acting as <span className="font-medium">{queue?.role ?? '—'}</span> · two-stage HOD → Principal routing with SLA timers and a
            tamper-evident decision log.
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setComposing((v) => !v)} className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-500">
            <FilePlus2 className="h-4 w-4" /> New request
          </button>
          <button onClick={() => void refresh()} className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 dark:border-slate-700 dark:text-slate-200">
            <RefreshCw className="h-4 w-4" /> Reload
          </button>
          <button
            onClick={() => void run('verify', workflowApi.verify, 'Audit chains verified for every request.')}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 dark:border-slate-700 dark:text-slate-200"
          >
            <ShieldAlert className="h-4 w-4" /> Verify audit chain
          </button>
        </div>
      </header>

      {funnel && (
        <section className="space-y-3">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
            {[
              { k: 'pending', v: funnel.buckets.PENDING ?? 0 },
              { k: 'approved', v: funnel.buckets.APPROVED ?? 0 },
              { k: 'rejected', v: funnel.buckets.REJECTED ?? 0 },
              { k: 'breaching SLA', v: funnel.pending_breaching_sla },
              { k: 'median decision', v: funnel.median_hours_to_decision === null ? '—' : `${funnel.median_hours_to_decision}h` },
              { k: 'escalations', v: funnel.escalation_events },
            ].map((c) => (
              <div key={c.k} className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
                <div className="text-xs uppercase tracking-wide text-slate-400">{c.k}</div>
                <div className="mt-1 text-2xl font-semibold tabular-nums text-slate-900 dark:text-white">
                  {typeof c.v === 'number' ? String(c.v) : String(c.v ?? '—')}
                </div>
              </div>
            ))}
          </div>
          <p className="text-[11px] text-slate-400">
            by kind: {Object.entries(funnel.by_kind).map(([k, v]) => `${k} ${v}`).join(' · ')}
            {funnel.baseline_note ? ` — ${funnel.baseline_note}` : ''}
          </p>
        </section>
      )}

      {composing && (
        <motion.section initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} className="rounded-xl border border-indigo-200 bg-indigo-50/40 p-5 dark:border-indigo-500/30 dark:bg-indigo-500/5">
          <div className="grid gap-3 md:grid-cols-4">
            <label className="md:col-span-2 block text-xs font-medium text-slate-600 dark:text-slate-300">
              Title
              <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900" placeholder="e.g. Two days leave for National Conference" />
            </label>
            <label className="block text-xs font-medium text-slate-600 dark:text-slate-300">
              Kind
              <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value as NewRequestPayload['kind'] })} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900">
                {KINDS.map((k) => (
                  <option key={String(k)} value={k}>
                    {k}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-xs font-medium text-slate-600 dark:text-slate-300">
              Priority
              <select value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value as NewRequestPayload['priority'] })} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900">
                {['Low', 'Medium', 'High', 'Critical'].map((p) => (
                  <option key={p}>{p}</option>
                ))}
              </select>
            </label>
            <label className="md:col-span-2 block text-xs font-medium text-slate-600 dark:text-slate-300">
              Description
              <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={2} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900" />
            </label>
            <label className="block text-xs font-medium text-slate-600 dark:text-slate-300">
              Amount (₹, purchases)
              <input type="number" value={form.amount ?? ''} onChange={(e) => setForm({ ...form, amount: e.target.value ? Number(e.target.value) : null })} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900" />
            </label>
            <div className="grid grid-cols-2 gap-2">
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-300">
                Evidence field
                <input value={evidenceKey} onChange={(e) => setEvidenceKey(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 px-2 py-2 text-xs dark:border-slate-700 dark:bg-slate-900" />
              </label>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-300">
                Value
                <input value={evidenceVal} onChange={(e) => setEvidenceVal(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 px-2 py-2 text-xs dark:border-slate-700 dark:bg-slate-900" placeholder="Hall booked via dept quota" />
              </label>
            </div>
          </div>
          <p className="mt-3 text-[11px] text-slate-500">
            Policy for <code>{form.kind}</code>:{' '}
            {policies?.policies.find((p) => p.kind === form.kind)
              ? `${policies.policies.find((p) => p.kind === form.kind)!.stages.join(' → ')} · SLA ${policies.policies.find((p) => p.kind === form.kind)!.sla_hours}h · evidence: ${
                  (policies.policies.find((p) => p.kind === form.kind)!.required_evidence ?? []).join(', ') || 'none'
                }`
              : 'loading…'}
          </p>
          <div className="mt-3 flex gap-2">
            <button onClick={() => void submitNew()} disabled={busy === 'raise'} className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-50">
              <Send className="h-4 w-4" /> {busy === 'raise' ? 'Filing…' : 'File & route to HOD'}
            </button>
            <button onClick={() => setComposing(false)} className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-600 dark:border-slate-700 dark:text-slate-300">
              Cancel
            </button>
          </div>
        </motion.section>
      )}

      {msg && (
        <div className={`rounded-lg px-4 py-2 text-sm ring-1 ${msg.tone === 'ok' ? 'bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:ring-emerald-500/30' : 'bg-rose-50 text-rose-700 ring-rose-200 dark:bg-rose-500/10 dark:text-rose-300 dark:ring-rose-500/30'}`}>
          {msg.text}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]">
        <section className="rounded-xl border border-slate-200 dark:border-slate-800">
          <div className="flex items-center justify-between border-b border-slate-200 px-3 py-2 dark:border-slate-800">
            <div className="flex gap-1">
              {(['all', 'due_soon', 'breached', 'mine'] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={`rounded-md px-2 py-1 text-xs font-medium ${filter === f ? 'bg-indigo-50 text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-300' : 'text-slate-500 hover:text-slate-800'}`}
                >
                  {f === 'mine' ? 'raised by me' : f.replace('_', ' ')}
                </button>
              ))}
            </div>
            <span className="text-[11px] text-slate-400">
              {rows.length} shown · {queue?.counts.breached ?? 0} breached
            </span>
          </div>
          <ul className="max-h-[30rem] divide-y divide-slate-100 overflow-y-auto dark:divide-slate-800">
            {rows.length === 0 && <li className="px-4 py-10 text-center text-sm text-slate-500">Nothing waiting at your stage.</li>}
            {rows.map((it) => (
              <li key={it.id}>
                <button onClick={() => setSelectedId(it.id)} className={`w-full px-4 py-3 text-left hover:bg-slate-50 dark:hover:bg-slate-800/60 ${selectedId === it.id ? 'bg-slate-50 dark:bg-slate-800/80' : ''}`}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-slate-800 dark:text-slate-100">{it.title}</p>
                      <p className="mt-0.5 text-xs text-slate-500">
                        {it.kind} · {it.requester_name ?? '—'} · stage <span className="font-medium">{it.stage}</span>
                      </p>
                    </div>
                    <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase ring-1 ${SLA_TONE[it.sla?.state ?? 'on_track']}`}>{it.sla?.state ?? 'on_track'}</span>
                  </div>
                  {it.sla && (
                    <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
                      <div className={`h-full rounded-full ${it.sla.percent_consumed > 100 ? 'bg-rose-500' : it.sla.percent_consumed > 75 ? 'bg-amber-500' : 'bg-emerald-500'}`} style={{ width: `${Math.min(100, it.sla.percent_consumed)}%` }} />
                    </div>
                  )}
                  {it.action_reason && <p className="mt-1.5 text-[11px] text-slate-400">{it.action_reason}</p>}
                </button>
              </li>
            ))}
          </ul>
        </section>

        <section className="rounded-xl border border-slate-200 p-5 dark:border-slate-800">
          {!doc ? (
            <div className="flex h-full min-h-[16rem] flex-col items-center justify-center gap-2 text-center text-sm text-slate-500">
              <CalendarClock className="h-6 w-6 text-slate-300" />
              Select a request to read its evidence, act on it, and inspect the audit chain.
            </div>
          ) : (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-base font-semibold text-slate-900 dark:text-white">{doc.title}</h2>
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">{doc.kind}</span>
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">{doc.status}</span>
                {doc.audit_integrity?.valid ? (
                  <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[11px] font-medium text-emerald-600">
                    <BadgeCheck className="h-3 w-3" /> chain intact
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 rounded-full bg-rose-500/10 px-2 py-0.5 text-[11px] font-medium text-rose-600">
                    <ShieldAlert className="h-3 w-3" /> chain problem
                  </span>
                )}
              </div>
              {doc.description && <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">{doc.description}</p>}

              <ol className="mt-4 flex items-center gap-2 text-xs">
                {stages.map((st, i) => (
                  <li key={st} className="flex items-center gap-2">
                    <span
                      className={`inline-flex items-center gap-1 rounded-full px-2 py-1 ring-1 ${
                        i < (doc.stage_index ?? 0) || doc.status === 'APPROVED'
                          ? 'bg-emerald-500/10 text-emerald-600 ring-emerald-500/30'
                          : st === doc.stage && doc.status === 'PENDING'
                            ? 'bg-indigo-500/10 text-indigo-600 ring-indigo-500/30'
                            : 'bg-slate-100 text-slate-400 ring-slate-200 dark:bg-slate-800 dark:ring-slate-700'
                      }`}
                    >
                      {i < (doc.stage_index ?? 0) || doc.status === 'APPROVED' ? <Check className="h-3 w-3" /> : null}
                      {st}
                    </span>
                    {i < stages.length - 1 && <span className="text-slate-300">→</span>}
                  </li>
                ))}
                {doc.sla_hours ? (
                  <li className="ml-auto text-[11px] text-slate-400">
                    SLA {doc.sla_hours}h{doc.sla_elapsed_hours ? ` · ${doc.sla_elapsed_hours.toFixed(0)}h elapsed` : ''}
                  </li>
                ) : null}
              </ol>

              {doc.evidence && Object.keys(doc.evidence).length > 0 && (
                <dl className="mt-4 grid grid-cols-2 gap-2 text-xs">
                  {Object.entries(doc.evidence).map(([k, v]) => (
                    <div key={k} className="rounded-lg bg-slate-50 px-3 py-2 dark:bg-slate-800/60">
                      <dt className="uppercase tracking-wide text-slate-400">{k}</dt>
                      <dd className="mt-0.5 text-slate-700 dark:text-slate-200">{Array.isArray(v) ? v.join(', ') : String(v)}</dd>
                    </div>
                  ))}
                </dl>
              )}

              {doc.hod_comment && <p className="mt-3 rounded-lg bg-slate-50 p-3 text-xs text-slate-600 dark:bg-slate-800/60 dark:text-slate-300"><span className="font-semibold">HOD:</span> {doc.hod_comment}</p>}
              {doc.principal_comment && <p className="mt-2 rounded-lg bg-slate-50 p-3 text-xs text-slate-600 dark:bg-slate-800/60 dark:text-slate-300"><span className="font-semibold">Principal:</span> {doc.principal_comment}</p>}

              <div className="mt-4">
                <label className="block text-[11px] font-medium uppercase tracking-wide text-slate-400">Decision note (mandatory to reject)</label>
                <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} placeholder={doc.action_hint ?? 'Record the reason, the budget head, or the condition you are approving under.'} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900" />
              </div>

              <div className="mt-3 flex flex-wrap gap-2">
                <button onClick={() => void run('approve', () => workflowApi.decide(doc.id, 'APPROVE', note), 'Approved.')} disabled={!doc.can_act || busy === 'approve'} className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-40">
                  <Check className="h-4 w-4" /> Approve{stages[(doc.stage_index ?? 0) + 1] ? ` → ${stages[(doc.stage_index ?? 0) + 1]}` : ''}
                </button>
                <button onClick={() => void run('reject', () => workflowApi.decide(doc.id, 'REJECT', note), 'Rejected with your note.')} disabled={!doc.can_act || busy === 'reject'} className="inline-flex items-center gap-2 rounded-lg border border-rose-200 px-3 py-2 text-sm font-medium text-rose-600 disabled:opacity-40 dark:border-rose-500/30">
                  <X className="h-4 w-4" /> Reject
                </button>
                {doc.status === 'REJECTED' && (doc.requester_id === uid || !!doc.can_act) && (
                  <button onClick={() => void run('resubmit', () => workflowApi.resubmit(doc.id, note || 'Revised with the requested evidence.'), 'Resubmitted to the first stage.')} className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-600 dark:border-slate-700 dark:text-slate-300">
                    <RotateCcw className="h-4 w-4" /> Resubmit
                  </button>
                )}
                {doc.status === 'PENDING' && (
                  <button
                    onClick={() => {
                      const to = window.prompt('Delegate this stage to a user id or e-mail (they must hold the matching capability):');
                      if (to) void run('delegate', () => workflowApi.delegate(doc.id, to, note), `Delegated to ${to}.`);
                    }}
                    className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-600 dark:border-slate-700 dark:text-slate-300"
                  >
                    <ArrowRightLeft className="h-4 w-4" /> Delegate
                  </button>
                )}
                {doc.related_task_id && (
                  <a href={`#/tasks`} className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-2 text-xs text-slate-600 dark:border-slate-700 dark:text-slate-300">
                    <Link2 className="h-3.5 w-3.5" /> instantiated task {doc.related_task_id}
                  </a>
                )}
              </div>
              {doc.action_hint && doc.status === 'PENDING' && <p className="mt-2 text-[11px] text-slate-400">{doc.action_hint}</p>}

              <h3 className="mt-6 text-xs font-semibold uppercase tracking-wide text-slate-400">Audit trail ({(doc.audit ?? []).length} entries)</h3>
              <ul className="mt-2 space-y-2">
                {(doc.audit ?? []).map((a, i) => (
                  <li key={`${a.at}-${i}`} className="rounded-lg border border-slate-100 px-3 py-2 text-xs dark:border-slate-800">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-slate-700 dark:text-slate-200">
                        {a.action} · {a.actor_role}
                      </span>
                      <span className="text-slate-400">{String(a.at).replace('T', ' ').slice(0, 19)}</span>
                    </div>
                    {a.note && <p className="mt-1 text-slate-500">{a.note}</p>}
                    {a.hash && <p className="mt-1 font-mono text-[10px] text-slate-400">sha256 {String(a.hash).slice(0, 24)}…</p>}
                  </li>
                ))}
                {(doc.audit ?? []).length === 0 && <li className="text-xs text-slate-400">No decisions recorded yet.</li>}
              </ul>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
