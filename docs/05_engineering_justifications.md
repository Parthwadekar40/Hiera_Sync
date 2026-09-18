# HieraSync AI — Engineering Justifications, Risk-Engine Math & Delivery Policy

*Covers Slide 16 (stack + justifications), the Slide 18 risk engine internals, the Slide 19 notification design, security, reliability and honest limitations.*

---

## 1. Technology stack & justification (Slide 16, extended)

| Layer | Selected technology | Engineering justification (deck) | What it buys in this build |
|---|---|---|---|
| Frontend SPA | React 19 + TypeScript + Vite | Actions/Suspense, strict static typing, instant HMR | `tsc -b` gate keeps 13+ pages type-safe |
| Styling & UI | Tailwind CSS v4 + Framer Motion | Utility-first responsive system, fluid animation | role-aware dashboards without a theme fork |
| Interactive UI | FullCalendar, Recharts, dnd-kit | Production calendar, charts, drag-and-drop Kanban | Kanban columns *are* the workflow states; board drag = status change |
| Backend REST | FastAPI (Python) + Pydantic v2 | Async performance, strict validation, auto OpenAPI | 22 routers, `/docs` as a live contract for the report appendix |
| Security / Auth | Firebase Auth + JWT (`python-jose`) | Stateless tokens, per-request role enforcement | + capability matrix (`rbac.py`) so intent is declared, not implied |
| Cloud data / cron | Cloud Firestore + APScheduler | Serverless NoSQL, 8 AM reminder cron | + embedded store driver so the platform runs with zero cloud setup |
| **Notification gateways** | SMTP (email), Twilio REST (SMS), Meta WhatsApp Cloud API | *future scope in the deck; delivered here* | stdlib `smtplib`/`urllib` — **no extra SDKs**, no cost until you add credentials |
| **Risk model** | Deterministic Python (no sklearn/GPU) | Zero-cost heuristic AI | single dependency-free module → runs in CI, on a college laptop, on a free tier |

**Why Python as the main language:** one language across API, engines, cron, benchmark harness and test-suite; scientific-style code without a JVM/Node runtime; FastAPI's type-driven validation removes an entire bug class (v1's `progress="75%"` strings vs floats is exactly why `compat.normalize_task` exists).

## 2. The heuristic AI risk engine — specification

### 2.1 Factors (all sub-scores normalised to 0–100)

| Factor | Default weight | Signal | Evidence produced |
|---|---|---|---|
| `schedule_pressure` | 0.24 | expected progress (elapsed ÷ total span) − actual progress | "Behind plan by 35 points (40 % done vs 75 % expected by now)" |
| `time_urgency` | 0.20 | days left ÷ remaining-work-in-days (4 focused days per full task) | "1.3 day(s) left for ~3.2 day(s) of remaining work (ratio 0.50)" |
| `stagnation` | 0.14 | idle days vs. allowed cadence (scales with slack left) | "No progress update for 4.0 day(s) (expected every 1.8)" |
| `capacity` | 0.14 | priority-weighted active load vs role-aware capacity | "Assignee overload: 4.6 weighted vs capacity 4.1 (112 %)" |
| `reliability` | 0.10 | assignee on-time history, shrunk to the department prior (Beta-style, n+4) | "68 % of this assignee's last 9 task(s) finished on time" |
| `dependency` | 0.08 | `blocked_by` / open subtasks near the deadline | "Waiting on 2 unfinished prerequisite(s): …" |
| `complexity` | 0.05 | subtask count, missing effort estimate, thin description, recurrence, urgency | "Complexity drivers: effort not estimated, thin description" |
| `approval_latency` | 0.05 | time queued ÷ department median approval hours | "Queue time 2.4× the norm (58 h vs 24 h)" |

### 2.2 Fusion & bands

```
z      = BASE_PRIOR + Σ_i  w_i · gain · logit( 0.03 + 0.94 · s_i/100 )      # BASE_PRIOR=-0.55, gain=1.35
p      = σ(z)                                                               # delay probability
score  = clip(100·p, 1, 99)   ∈ [0,100]
band   = HIGH if score ≥ 55 · MEDIUM if ≥ 30 · else LOW
at_risk= score ≥ 75           # drives CRITICAL escalation channel policy
confidence = f(feature completeness, factor agreement) ∈ [0.35, 0.97]
ETA    = (100 − progress) / observed velocity, else remaining_work·4·max(1, load/capacity)
```

Two deliberate properties: **(a) the score *is* the probability** (a 62 means ~62 % modelled slip chance — no "what does this number mean?" in a viva), and **(b) logit fusion instead of a linear sum**, so one confident signal moves the number while marginal ones don't (measured: better top-decile precision than the linear version; `docs/02 §4`).

**Worked example** (seeded corpus task, deadline +1.3 d, 20 % progress, assignee at 112 % capacity):

```
schedule_pressure 72.4 ×0.24 → logit +1.24      time_urgency 92.0 ×0.20 → +1.66
stagnation 30.0  ×0.14 → +0.16                  capacity 48.7  ×0.14 → +0.36
reliability 32   ×0.10 → +0.13                  dependency 66.7×0.08 → +0.45
complexity 60    ×0.05 → +0.24                  approval 0     ×0.05 → −0.07
                                    z = −0.55 + 4.17· …  → p ≈ 0.29 → score 29.1 (LOW, at_risk ✗)
drivers: Deadline proximity, Assignee workload, Blockers & dependencies
recommendation: "Projected finish in ~3.2 day(s) vs 1.3 day(s) of slack: re-scope or raise a deadline-change approval."
```

### 2.3 Governance & learning

* Weights are **overridable per institution** (`PUT /api/v1/risk/weights`) and persisted to `risk_weights/global`.
* **Calibration**: `POST /api/v1/risk/calibrate` runs coordinate descent on ROC-AUC over closed tasks (late completion = positive label), needs ≥12 labelled rows, and returns `auc_before/auc_after/gain/weights/history`. Run once a term. Auto-invoked at boot on an empty store.
* **Comparability**: `GET /api/v1/risk/benchmark` re-runs the harness; `docs/benchmark_results.json` is its committed output, so the report and the code cannot disagree.
* **What-if simulator**: `POST /api/v1/risk/what-if {task_id, overrides}` re-scores with a moved deadline, a reassignment or added subtasks — the HOD's "what happens if…" tool.

## 3. Notification & automation policy

```
event → severity(kind|override) → recipients → per-recipient preferences
      → channel plan (policy ∧ consent ∧ reachability) → quiet hours / digest deferral
      → outbox row (per-channel dedupe key) → provider (live or dev-outbox)
      → delivery ledger  →  retry w/ exponential backoff+jitter  →  dead-letter + operator alert
```

| Severity | Channels (default policy) | Rationale |
|---|---|---|
| CRITICAL | in-app, e-mail, SMS, WhatsApp | escalation, SLA breach, at-risk (score ≥ 75) overdue — must interrupt |
| HIGH | in-app, e-mail, SMS, WhatsApp | overdue, approval request, newly HIGH risk |
| MEDIUM | in-app, e-mail | assignment, reminders, event notices |
| LOW | in-app only | completions, insights — batched into a digest if the user opted in |

Per-user gates that the policy respects: `email_enabled`, `sms_enabled`, `whatsapp_enabled`, **`whatsapp_opt_in`** (Meta requires explicit per-number opt-in for business-initiated templates; unsent reasons are recorded as `whatsapp:opt_in_required`, never silently dropped), `min_severity_{email,sms,whatsapp}`, `muted_kinds`, `quiet_hours` (default 22:30–07:00 `Asia/Kolkata`; CRITICAL breaks through), `digest_mode: none|daily|weekly`.

Reliability properties: idempotent **dedupe** (`sha256(user|kind|title|body|channel)` inside a 360-min window), **max 4 attempts** with `60 s · 2^n` + jitter capped at 1 h, per-provider **rate limit** (40/min to protect free tiers), **dead-letter** writes an operator alert into `notifications`, and delivery failures **never** fail the business request (`NOTIFY_FAIL_SOFT`). `NOTIFY_TIMEZONE` drives both cron wall-clock and quiet hours so "8 AM" means 8 AM in Nagpur, not UTC.

## 4. Security

* JWT (HS256) with `sub=email`, expiry from config; bcrypt password hashing (cost 12); no password ever serialised (`hashed_password` stripped in responses).
* Capability-based authorisation on new routes; row-level scoping for analytics (`full_institute/department/self/none`).
* PII minimisation: phone numbers are used only for the channel a user opted into; the delivery ledger stores the address, not message content for SMS/WhatsApp.
* Secrets only via `.env` (git-ignored); service-account JSON ignored by `.gitignore`; CORS list from config; no credentials in the frontend.
* Approval decisions are tamper-evident (SHA-256 chain); `POST /api/v1/workflow/verify` is the check.
* Known v1 debt kept visible: Firestore security rules are the client-side guard when the SPA talks to Firestore directly — server routes remain the authority.

## 5. Reliability, performance, observability

* `/health` (liveness, backend, scheduler) and `/health/deep` (datastore probe, outbox stats, per-channel provider selection, RBAC count, route count).
* Every request carries `X-Request-Id` + `X-Elapsed-Ms`; scheduler writes claim + result rows so a missed run is diagnosable, not invisible.
* `risk_snapshots` gives a trend line (bands, mean risk, expected misses) without any BI stack.
* Single-process assumptions documented: the rate-limiter window and provider cache are in-memory (fine for one worker; multi-worker needs Redis — roadmap). SQLite mode is single-writer; Firestore mode is the multi-instance path.

## 6. Limitations (stated, not hidden)

1. The engine is **calibrated heuristics, not a learned function**; on large clean histories a supervised model ranks slightly better (`docs/02 §4` sweep). We ship the history and the swap point.
2. **`deadline_only` edges our AUC by 0.028** on the synthetic corpus while flagging 2.5× more tasks; we optimise precision-at-budget and alert volume, which is the operationally relevant trade.
3. WhatsApp business-initiated delivery needs an **approved template per message kind** and a verified Meta number; without it the engine falls back to e-mail/SMS and records the reason.
4. The embedded store is for dev/CI/demos (sequential scans, single writer); production uses Firestore.
5. E-mail/SMS/WhatsApp are best-effort channels: a campus firewall or a dead SMTP password degrades them to the dev outbox, and the platform keeps working.
