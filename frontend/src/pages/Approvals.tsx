import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { aiApi, approvalsApi } from "../api";
import { useAuth } from "../contexts/AuthContext";
import type { ApprovalCreate, ApprovalResponse } from "../types";
import { formatDate, toISODate } from "../utils/calendar";
import "./Approvals.css";

type Decision = "Pending" | "Approved" | "Rejected";

interface Toast {
  id: number;
  tone: "success" | "error" | "info";
  text: string;
}

const STATUS_TONE: Record<Decision, string> = {
  Pending: "is-pending",
  Approved: "is-approved",
  Rejected: "is-rejected",
};

const PRIORITY_TONE: Record<string, string> = {
  High: "prio-high",
  Medium: "prio-medium",
  Low: "prio-low",
};

const SEED: ApprovalResponse[] = [
  {
    id: "app_1",
    title: "Final Year Project Review Panel",
    requested: "AIML Final Year Students",
    assigned: "Dr. Animesh Tayal",
    priority: "High",
    status: "Pending",
    comments: "External reviewer confirmed for the panel.",
    created_at: new Date().toISOString(),
  },
  {
    id: "app_2",
    title: "AI Lab Equipment Request",
    requested: "AI Lab Coordinator",
    assigned: "Mrs. Neha Gurnani",
    priority: "Medium",
    status: "Pending",
    comments: "Six workstation GPUs for the fine-tuning lab.",
    created_at: new Date().toISOString(),
  },
  {
    id: "app_3",
    title: "Machine Learning Workshop Budget",
    requested: "AIML Student Club",
    assigned: "Ms. Sweta Arun Bokade",
    priority: "Low",
    status: "Approved",
    reviewed_at: new Date().toISOString(),
    created_at: new Date().toISOString(),
  },
  {
    id: "app_4",
    title: "Research Paper Submission — IEEE Conference",
    requested: "Student Research Team",
    assigned: "Dr. Bhushan Mahendra Manjre",
    priority: "High",
    status: "Pending",
    comments: "Camera-ready deadline in 9 days.",
    created_at: new Date().toISOString(),
  },
  {
    id: "app_5",
    title: "Industry Visit — Nagpur AI Park",
    requested: "TYAIML Class Representative",
    assigned: "Mrs. Neha Gurnani",
    priority: "Medium",
    status: "Rejected",
    comments: "Same week as mid-semester assessments.",
    reviewed_at: new Date().toISOString(),
    created_at: new Date().toISOString(),
  },
];

const asDecision = (value?: string): Decision =>
  value === "Approved" || value === "Rejected" ? value : "Pending";

type AdviceSuggestion = { id: string; title: string; reason: string };
type Advice = { message: string; suggestions: AdviceSuggestion[] };

export default function Approvals() {
  const { user } = useAuth();
  const role = (user?.role ?? "").toUpperCase();
  const canReview = role.includes("ADMIN") || role.includes("HOD") || role.includes("HEAD");

  const [items, setItems] = useState<ApprovalResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [source, setSource] = useState<"live" | "preview">("live");
  const [error, setError] = useState("");

  const [tab, setTab] = useState<"All" | Decision>("Pending");
  const [query, setQuery] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [note, setNote] = useState("");

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<ApprovalCreate>({
    title: "",
    requested: user?.name ?? "",
    assigned: "",
    priority: "Medium",
    comments: "",
  });
  const [formError, setFormError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const [toasts, setToasts] = useState<Toast[]>([]);
  const [advice, setAdvice] = useState<Advice | null>(null);
  const toastSeq = useRef(0);

  const pushToast = useCallback((text: string, tone: Toast["tone"] = "info") => {
    const id = ++toastSeq.current;
    setToasts((current) => [...current, { id, tone, text }]);
    window.setTimeout(
      () => setToasts((current) => current.filter((toast) => toast.id !== id)),
      4200
    );
  }, []);

  const localAdvice = useCallback((list: ApprovalResponse[]): Advice => {
    const pending = list.filter((item) => asDecision(item.status) === "Pending");
    if (pending.length === 0) {
      return { message: "Nothing is waiting for a decision right now.", suggestions: [] };
    }
    const weight = (value?: string) => (value === "High" ? 0 : value === "Medium" ? 1 : 2);
    const ranked = [...pending]
      .sort((a, b) => weight(a.priority) - weight(b.priority))
      .slice(0, 3);
    return {
      message: `${pending.length} request(s) are waiting — start with “${ranked[0].title}” (${
        ranked[0].priority || "Medium"
      } priority).`,
      suggestions: ranked.map((item) => ({
        id: String(item.id),
        title: item.title,
        reason: `${item.priority || "Medium"} priority`,
      })),
    };
  }, []);

  const refreshAdvice = useCallback(
    async (list: ApprovalResponse[]) => {
      try {
        const res = await aiApi.getApprovalSuggestions();
        if (res?.message) {
          setAdvice({
            message: res.message,
            suggestions: (res.suggestions ?? []).map((item) => ({
              id: String(item.id ?? ""),
              title: item.title ?? "Request",
              reason: item.reason ?? "",
            })),
          });
          return;
        }
        throw new Error("empty response");
      } catch {
        setAdvice(localAdvice(list));
      }
    },
    [localAdvice]
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await approvalsApi.getAll();
      setItems(data ?? []);
      setSource("live");
      void refreshAdvice(data ?? []);
    } catch (err: any) {
      setItems(SEED);
      setSource("preview");
      setAdvice(localAdvice(SEED));
      setError(err?.message || "Approval service is unreachable.");
    } finally {
      setLoading(false);
    }
  }, [localAdvice, refreshAdvice]);

  useEffect(() => {
    load();
  }, [load]);

  const stats = useMemo(() => {
    const now = Date.now();
    const age = (item: ApprovalResponse) => {
      const created = item.created_at ? new Date(item.created_at).getTime() : now;
      return Math.max(0, Math.round((now - created) / 86_400_000));
    };
    return {
      pending: items.filter((item) => asDecision(item.status) === "Pending").length,
      approved: items.filter((item) => asDecision(item.status) === "Approved").length,
      rejected: items.filter((item) => asDecision(item.status) === "Rejected").length,
      highPriority: items.filter(
        (item) => asDecision(item.status) === "Pending" && item.priority === "High"
      ).length,
      stale: items.filter((item) => asDecision(item.status) === "Pending" && age(item) > 3).length,
    };
  }, [items]);

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return items
      .filter((item) => (tab === "All" ? true : asDecision(item.status) === tab))
      .filter((item) =>
        needle
          ? [item.title, item.requested, item.assigned, item.comments]
              .join(" ")
              .toLowerCase()
              .includes(needle)
          : true
      )
      .sort((a, b) => {
        const rank = (value?: string) =>
          value === "High" ? 0 : value === "Medium" ? 1 : 2;
        return rank(a.priority) - rank(b.priority);
      });
  }, [items, query, tab]);

  const decide = async (item: ApprovalResponse, decision: Exclude<Decision, "Pending">) => {
    if (!canReview) {
      pushToast("Only the HOD desk can take approval decisions.", "error");
      return;
    }

    setBusyId(String(item.id));
    try {
      if (source === "live") {
        const next =
          decision === "Approved"
            ? await approvalsApi.approve(String(item.id))
            : await approvalsApi.reject(String(item.id));

        if (note.trim()) {
          await approvalsApi
            .update(String(item.id), { comments: note.trim() })
            .catch(() => undefined);
          next.comments = note.trim();
        }

        setItems((previous) =>
          previous.map((entry) => (String(entry.id) === String(item.id) ? { ...entry, ...next } : entry))
        );
      } else {
        setItems((previous) =>
          previous.map((entry) =>
            String(entry.id) === String(item.id)
              ? {
                  ...entry,
                  status: decision,
                  comments: note.trim() || entry.comments,
                  reviewed_at: new Date().toISOString(),
                }
              : entry
          )
        );
      }

      pushToast(`“${item.title}” marked ${decision.toLowerCase()}.`, "success");
      setOpenId(null);
      setNote("");
    } catch (err: any) {
      pushToast(err?.message || `Could not ${decision.toLowerCase()} this request.`, "error");
    } finally {
      setBusyId(null);
    }
  };

  const withdraw = async (item: ApprovalResponse) => {
    setBusyId(String(item.id));
    try {
      if (source === "live") await approvalsApi.delete(String(item.id));
      setItems((previous) => previous.filter((entry) => String(entry.id) !== String(item.id)));
      pushToast("Request removed.", "success");
    } catch (err: any) {
      pushToast(err?.message || "The request could not be removed.", "error");
    } finally {
      setBusyId(null);
    }
  };

  const submitRequest = async () => {
    if (form.title.trim().length < 5) {
      setFormError("Describe the request in at least 5 characters.");
      return;
    }
    if (!form.assigned.trim()) {
      setFormError("Name the approver (HOD / faculty in charge).");
      return;
    }

    setFormError("");
    setSubmitting(true);
    try {
      if (source === "live") {
        const created = await approvalsApi.create({
          ...form,
          title: form.title.trim(),
          requested: form.requested.trim() || user?.name || "Faculty",
          assigned: form.assigned.trim(),
        });
        setItems((previous) => [...previous, created]);
      } else {
        setItems((previous) => [
          ...previous,
          {
            ...form,
            id: `preview_${Date.now()}`,
            status: "Pending",
            created_at: new Date().toISOString(),
          },
        ]);
      }
      pushToast("Request submitted to the HOD desk.", "success");
      setShowForm(false);
      setForm({
        title: "",
        requested: user?.name ?? "",
        assigned: "",
        priority: "Medium",
        comments: "",
      });
      setTab("Pending");
    } catch (err: any) {
      pushToast(err?.message || "The request could not be submitted.", "error");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="approvals-page hs-page">
      <header className="approvals-header">
        <div>
          <div className="hs-kicker">SBJIT Nagpur · CSE (AI &amp; ML) Department</div>
          <h1>Approvals Desk</h1>
          <p>
            Requests raised by faculty and students, waiting on a department decision. Approve or
            send back with a note — the requester sees it in their notifications.
          </p>
        </div>

        <div className="approvals-header-actions">
          <span className={`role-chip ${canReview ? "is-reviewer" : "is-requester"}`}>
            {canReview ? "Reviewer access" : "Requester access"}
          </span>
          <button type="button" className="hs-btn hs-btn--primary" onClick={() => setShowForm(true)}>
            ＋ New Request
          </button>
        </div>
      </header>

      {source === "preview" && (
        <div className="approvals-note" role="status">
          <div>
            <strong>Offline preview</strong>
            <span>
              {error} Decisions here are local to this browser until the approval service responds.
            </span>
          </div>
          <button type="button" onClick={load}>
            Retry
          </button>
        </div>
      )}

      <section className="approvals-stats" aria-label="Approval statistics">
        <article className="hs-card approvals-stat">
          <span className="hs-kicker">Awaiting decision</span>
          <strong className="hs-stat-value">{stats.pending}</strong>
          <small>{stats.stale} waiting more than 3 days</small>
        </article>

        <article className="hs-card approvals-stat">
          <span className="hs-kicker">High priority</span>
          <strong className="hs-stat-value">{stats.highPriority}</strong>
          <small>Flagged for the HOD desk</small>
        </article>

        <article className="hs-card approvals-stat is-approved">
          <span className="hs-kicker">Approved</span>
          <strong className="hs-stat-value">{stats.approved}</strong>
          <small>Cleared this cycle</small>
        </article>

        <article className="hs-card approvals-stat is-rejected">
          <span className="hs-kicker">Sent back</span>
          <strong className="hs-stat-value">{stats.rejected}</strong>
          <small>Need a revised request</small>
        </article>
      </section>

      <section className="approvals-toolbar" aria-label="Approval filters">
        <div className="approvals-tabs" role="tablist">
          {(["Pending", "Approved", "Rejected", "All"] as const).map((value) => (
            <button
              key={value}
              role="tab"
              type="button"
              aria-selected={tab === value}
              className={`approvals-tab ${tab === value ? "is-on" : ""}`}
              onClick={() => setTab(value)}
            >
              {value}
              <span className="hs-num">
                {value === "All"
                  ? items.length
                  : items.filter((item) => asDecision(item.status) === value).length}
              </span>
            </button>
          ))}
        </div>

        <div className="approvals-search">
          <span aria-hidden="true">🔍</span>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search requests, requesters, approvers…"
            aria-label="Search approval requests"
          />
        </div>
      </section>

      {advice && !loading && (
        <section className="approvals-ai" aria-label="Suggested review order">
          <span className="hs-kicker">Suggested order</span>
          <p>{advice.message}</p>
          {advice.suggestions.length > 0 && (
            <div className="approvals-ai-chips">
              {advice.suggestions.map((item, index) => (
                <button
                  key={item.id || item.title}
                  type="button"
                  className="approvals-ai-chip"
                  onClick={() => setQuery(item.title)}
                  title="Filter the queue to this request"
                >
                  <span className="hs-num">{index + 1}</span>
                  <span>{item.title}</span>
                  {item.reason && <em>{item.reason}</em>}
                </button>
              ))}
            </div>
          )}
        </section>
      )}

      {loading ? (
        <div className="approvals-loading">
          <span className="loading-spinner" />
          Loading approval queue…
        </div>
      ) : visible.length === 0 ? (
        <div className="hs-card approvals-empty">
          <span aria-hidden="true">✅</span>
          <h2>Nothing in this queue</h2>
          <p>
            {query
              ? "No request matches that search. Try another keyword."
              : `${tab === "All" ? "The desk" : `${tab} requests`} is clear right now.`}
          </p>
        </div>
      ) : (
        <ul className="approvals-list">
          {visible.map((item) => {
            const decision = asDecision(item.status);
            const open = openId === String(item.id);
            const ageDays = item.created_at
              ? Math.max(
                  0,
                  Math.round((Date.now() - new Date(item.created_at).getTime()) / 86_400_000)
                )
              : 0;

            return (
              <li key={item.id}>
                <article className={`hs-card approvals-card ${STATUS_TONE[decision]}`}>
                  <div className="approvals-card-top">
                    <div className="approvals-title-block">
                      <span className={`prio ${PRIORITY_TONE[item.priority ?? "Medium"]}`}>
                        {item.priority ?? "Medium"}
                      </span>
                      <span className="pill-status">{decision}</span>
                      <h2>{item.title}</h2>
                      <p className="approvals-meta">
                        Raised by <strong>{item.requested || "—"}</strong> · to{" "}
                        <strong>{item.assigned || "HOD Desk"}</strong>
                        {item.created_at ? ` · ${formatDate(toISODate(item.created_at))}` : ""}
                      </p>
                    </div>

                    <div className="approvals-age">
                      <span className="hs-num">{ageDays}</span>
                      <small>day{ageDays === 1 ? "" : "s"} waiting</small>
                    </div>
                  </div>

                  {item.comments && (
                    <p className="approvals-note-body">
                      <span className="hs-kicker">Note</span>
                      {item.comments}
                    </p>
                  )}

                  <div className="approvals-card-actions">
                    {canReview && decision === "Pending" ? (
                      <>
                        <button
                          type="button"
                          className="hs-btn hs-btn--primary"
                          disabled={busyId === String(item.id)}
                          onClick={() => decide(item, "Approved")}
                        >
                          ✓ Approve
                        </button>
                        <button
                          type="button"
                          className="hs-btn hs-btn--ghost"
                          disabled={busyId === String(item.id)}
                          onClick={() => decide(item, "Rejected")}
                        >
                          ↩ Send back
                        </button>
                        <button
                          type="button"
                          className="link-btn"
                          onClick={() => {
                            setOpenId(open ? null : String(item.id));
                            setNote(item.comments ?? "");
                          }}
                        >
                          {open ? "Hide note" : "Add reviewer note"}
                        </button>
                      </>
                    ) : (
                      <span className="approvals-decided">
                        {decision === "Pending"
                          ? "Waiting for the HOD desk"
                          : `Closed ${decision.toLowerCase()}${
                              item.reviewed_at ? ` on ${formatDate(toISODate(item.reviewed_at))}` : ""
                            }`}
                      </span>
                    )}

                    {decision === "Pending" && !canReview && (
                      <button
                        type="button"
                        className="link-btn"
                        disabled={busyId === String(item.id)}
                        onClick={() => withdraw(item)}
                      >
                        Withdraw request
                      </button>
                    )}
                  </div>

                  {open && (
                    <div className="approvals-note-form">
                      <textarea
                        className="hs-field"
                        rows={2}
                        value={note}
                        onChange={(event) => setNote(event.target.value)}
                        placeholder="Why is this being approved or sent back? The requester will see this."
                      />
                    </div>
                  )}
                </article>
              </li>
            );
          })}
        </ul>
      )}

      {showForm && (
        <div className="modal-overlay" onMouseDown={() => setShowForm(false)}>
          <div
            className="approvals-modal"
            role="dialog"
            aria-modal="true"
            aria-label="New approval request"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="approvals-modal-head">
              <div>
                <div className="hs-kicker">HOD desk</div>
                <h2>New Approval Request</h2>
              </div>
              <button
                type="button"
                className="icon-btn"
                onClick={() => setShowForm(false)}
                aria-label="Close"
              >
                ×
              </button>
            </div>

            <div className="approvals-modal-body">
              <label>
                What needs approval? *
                <input
                  className="hs-field"
                  value={form.title}
                  onChange={(event) => setForm({ ...form, title: event.target.value })}
                  placeholder="e.g. Lab equipment purchase for AI/ML wing"
                  autoFocus
                />
              </label>

              <div className="approvals-form-row">
                <label>
                  Requested by
                  <input
                    className="hs-field"
                    value={form.requested}
                    onChange={(event) => setForm({ ...form, requested: event.target.value })}
                  />
                </label>

                <label>
                  Approver *
                  <input
                    className="hs-field"
                    value={form.assigned}
                    onChange={(event) => setForm({ ...form, assigned: event.target.value })}
                    placeholder="HOD / faculty in charge"
                  />
                </label>
              </div>

              <label>
                Priority
                <select
                  className="hs-field"
                  value={form.priority}
                  onChange={(event) => setForm({ ...form, priority: event.target.value })}
                >
                  <option>High</option>
                  <option>Medium</option>
                  <option>Low</option>
                </select>
              </label>

              <label>
                Justification
                <textarea
                  className="hs-field"
                  rows={3}
                  value={form.comments}
                  onChange={(event) => setForm({ ...form, comments: event.target.value })}
                  placeholder="Budget, dates, who benefits…"
                />
              </label>

              {formError && <p className="form-error">{formError}</p>}
            </div>

            <div className="approvals-modal-foot">
              <button type="button" className="hs-btn hs-btn--ghost" onClick={() => setShowForm(false)}>
                Cancel
              </button>
              <button
                type="button"
                className="hs-btn hs-btn--primary"
                onClick={submitRequest}
                disabled={submitting}
              >
                {submitting ? "Submitting…" : "Submit request"}
              </button>
            </div>
          </div>
        </div>
      )}

      {toasts.length > 0 && (
        <div className="approvals-toasts" role="status" aria-live="polite">
          {toasts.map((toast) => (
            <div key={toast.id} className={`toast toast--${toast.tone}`}>
              <span aria-hidden="true">
                {toast.tone === "success" ? "✓" : toast.tone === "error" ? "!" : "i"}
              </span>
              {toast.text}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
