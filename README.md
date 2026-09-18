# HieraSync AI

**Smart Academic Workflow & Event Management System** — a role-aware full-stack platform for assigning, tracking,
approving and analysing academic work, with a **zero-cost explainable AI risk engine** and **automated notifications
on in-app, e-mail, SMS and WhatsApp**.

> Department of Computer Science & Engineering (AI & ML), S. B. Jain Institute of Technology, Management & Research,
> Nagpur — AY 2026‑27 · Group 11: Atul Gupta (CM23019), Tanvi Beer (CM23020), Tanish Kesharwani (CM23020),
> Parth Wadekar (CM23040) · Guide: **Mrs. Neha Gurnani**
> Specification source: [`HieraSync_AI_30_Slide_Master_Presentation_v2.pdf`](HieraSync_AI_30_Slide_Master_Presentation_v2.pdf)
> · documentation set: [`docs/`](docs/README.md)

---

## Run it (no cloud account, no credentials)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate      # a ready .venv is already committed in this sandbox
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

* API + interactive docs → `http://localhost:8000/docs` · health → `/health` · pointer → `/`
* First boot seeds a deterministic demo corpus (2 departments (join codes `AIML`, `IT`), 18 users covering **all 10 roles**, 28 tasks spanning
  every risk band, 8 approvals at different stages, events, goals, channel preferences) and auto-calibrates risk weights.
* Sign in as `principal@demo.hierasync.in` / `hod.aiml@hierasync.demo` / `hod.it@hierasync.demo` / `neha.gurnani@hierasync.demo` / `teacher@hierasync.demo` — password `HierSync@123`.
* Departments in the demo data: code **`AIML`** (Computer Science & Engineering, AI & ML) and **`IT`** (Information Technology) — either works on the Join Department screen.

```bash
cd frontend && npm install && npm run dev              # http://localhost:5173  (/api proxied to :8000)
cd backend && python scripts/e2e_demo.py               # the deck's success criterion, as a 13-check test
cd backend && python -m pytest -q                      # 48 tests
docker compose up --build                              # backend + SPA + browsable notification outbox
```

## What it does

| | |
|---|---|
| **One workspace** | Tasks (Kanban + subtasks + progress), events (FullCalendar), goals with milestones, documents/attachments, comments, department roster |
| **Governance** | 2-stage **HOD → Principal** approvals with per-kind policies, mandatory rejection notes, SLA timers, delegation, resubmission, **hash-chained audit trail**, and automatic task creation on approval |
| **AI (explainable, free)** | 8-factor deadline-risk engine scoring every open task 0–100 (LOW/MEDIUM/HIGH) with per-factor evidence, ETA forecast, what-if simulator, per-institution weight calibration, and a reproducible benchmark against deadline-only / progress-gap / logistic-regression / random-forest baselines |
| **Automation** | 10 cron & interval jobs: risk sweep, T‑3/T‑1/day-of reminders, overdue escalation ladder (assignee → HOD → Principal), approval SLA nudges, daily digest, weekly report, event reminders, goal check-in, outbox flush, retention purge |
| **Delivery** | in-app centre with unread badge + **live SSE feed**, SMTP e-mail, Twilio SMS, Meta WhatsApp Cloud API — with consent, per-severity routing, quiet hours, digest batching, dedupe, retry/backoff, dead-letter paging, a delivery ledger, and a **dev outbox that writes real HTML/text previews when no credentials exist** |
| **Analytics** | scorecard with published formulas, faculty performance & workload balance, department rollup, on-time rate, forecast, CSV/JSON one-click exports |
| **Security** | JWT + bcrypt, 10 roles × 16 capabilities enforced per endpoint (`docs/05_RBAC_MATRIX.md`), row-level analytics scoping |

## Architecture at a glance

```
React 19 + TS + Vite + Tailwind v4 + Framer Motion + Recharts/FullCalendar/dnd-kit
        │ HTTPS + Bearer JWT
FastAPI (Python) · Pydantic v2 · 22 routers under /api/v1 · engines: risk · approvals · analytics
        │                                           └ APScheduler (10 jobs) → notify engine → providers
Firestore (cloud)  or  embedded Firestore-compatible document store (SQLite + JSON)   SMTP · Twilio · Meta Graph
```

`DATABASE_BACKEND=auto` uses Firestore when credentials are present and otherwise falls back to the embedded store —
same query surface, so the platform runs in CI, on a demo laptop, or on a college server without a GCP project.

## Repository layout

```
backend/
  app/
    api/v1/            21 FastAPI routers (tasks, events, approvals, auth, ai, reports, risk, workflow, metrics, channels, …)
    auth/              JWT issue/verify + rbac.py (capability matrix = docs/05_RBAC_MATRIX.md)
    db/                store.py (Firestore-compatible engine), compat.py (field normalizers), seed.py (demo corpus)
    engine/            risk.py · approvals.py · analytics.py · calibrate.py · benchmarks.py
    notify/            base · providers (smtp/twilio/whatsapp/outbox) · templates · routing · queue (outbox) · engine
    scheduler/         jobs.py — 10 idempotent cron/interval jobs with claim slots
    models/ schemas/   Pydantic v2 contracts
    config/ settings.py  60+ env-driven settings
  scripts/             e2e_demo.py (acceptance), check_store_parity.py, export_sqlite_to_firestore.py
  tests/               test_platform.py — 48 tests
  Dockerfile · requirements.txt · .env.example
frontend/              src/{api,pages,components,hooks,context} · 13+ role-aware pages · Dockerfile · nginx.conf
docs/                  01–07 report sections + 05_RBAC_MATRIX.md + benchmark_results.json + README.md (index)
docker-compose.yml     backend + SPA + outbox preview (:8080); dev profile runs Vite with HMR
```

## Documentation

Start with [`docs/README.md`](docs/README.md) — it maps every deck slide to a document, an endpoint and a test
([`docs/07 §5`](docs/07_advantages_roi_traceability.md#5-traceability-matrix--deck-slide--artifact)).

1. [Vision, problem, objectives, scope](docs/01_vision_problem_objectives.md)
2. [Literature survey, comparative & benchmark analysis](docs/02_literature_and_comparative_analysis.md)
3. [Architecture, DFDs, use case, workflow, modules](docs/03_architecture_and_design.md)
4. [Database design](docs/04_database_design.md)
5. [Engineering justifications, risk math, delivery policy, limitations](docs/05_engineering_justifications.md) · [RBAC matrix](docs/05_RBAC_MATRIX.md)
6. [Run, test, deploy, notification setup](docs/06_run_test_deploy.md)
7. [Advantages, ROI, applications, roadmap, traceability](docs/07_advantages_roi_traceability.md)

## Headline result (measured, reproducible)

```bash
cd backend && python -m app.engine.benchmarks --tasks 500
```

At an **equal alert budget**, HieraSync's engine is the most accurate triage tool in the comparison —
**precision 0.700 vs 0.550–0.644** for deadline-only, MS-Project-style progress gap, manual triage and both trained
models — while flagging **~3× fewer tasks** (20 % vs 43–61 %), needing **no labelled history** to start, and
shipping per-factor explanations. ROC-AUC is within 0.03 of the best baseline (0.594 vs 0.622), and weight calibration
lifts it from 0.625 → 0.655 on 300 rows. Full table, sample-efficiency sweep and the limits of the claim:
[`docs/02 §4`](docs/02_literature_and_comparative_analysis.md#4-results-n--500-seed-7-test-split-200-rows-base-slip-rate-0495).

## Notes

* E-mail/SMS/WhatsApp activate automatically once credentials exist; without them every message is still written to
  `backend/var/outbox/` as a viewable preview (the compose stack serves it on `:8080`).
* Python is the implementation language for the API, engines, scheduler, benchmark and tests; TypeScript only in the SPA.
* Frontend scaffolding retains the Vite React-TS template docs in `frontend/README.md`.
