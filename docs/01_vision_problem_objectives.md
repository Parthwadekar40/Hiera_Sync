# HieraSync AI — Vision, Problem, Objectives & Scope

*Aligned to `HieraSync_AI_30_Slide_Master_Presentation_v2.pdf` (Slides 1–6). Group 11 — Dept. of Computer Science & Engineering (AI & ML), S. B. Jain Institute of Technology, Management & Research, Nagpur — AY 2026‑27. Guided by Mrs. Neha Gurnani.*

---

## 1. Abstract

HieraSync AI is a **role-aware academic workflow and event management platform**. It gives a department one system of record for tasks, events, approvals, documents, goals and analytics, and it governs that record with the institution's own hierarchy — Principal → HOD → Faculty → Staff/Students — instead of a generic corporate flat model.

Its differentiating capability is a **zero-cost, explainable heuristic AI risk engine** that scores every open obligation (0–100, LOW/MEDIUM/HIGH) for the probability of missing its deadline, and an **automation layer** that converts that score into timely action: in-app alerts, e-mail, SMS and WhatsApp, escalating from assignee to HOD to Principal when follow-ups are ignored.

## 2. Core platform vision (Slide 3)

| Vision pillar | What it means in this build | Where it lives |
|---|---|---|
| **Unified full-stack portal** | Tasks, events, approvals, notifications, goals and analytics in one SPA + one REST API | `frontend/src`, `backend/app/api/v1` (22 routers) |
| **Role-aware governance** | Every endpoint resolves a capability against the hierarchy, not a hand-written role list | `backend/app/auth/rbac.py` (Slide 13 matrix as data) |
| **10 distinct roles** | ADMIN, PRINCIPAL, HOD, TEACHER, FACULTY, TA, STUDENT, STUDENT_REP, LAB_ASSISTANT, STAFF | `app/models/models.py::RoleEnum` |
| **Single source of truth** | Replaces paper registers, WhatsApp threads and disconnected Excel sheets | document store: `users, departments, tasks, approvals, events, notifications, goals, …` |

## 3. Technical & operational scope (Slide 3)

* **Domain** — Academic workflow automation + applied AI: heuristic risk scoring, deterministic summarisation, report generation, notification routing.
* **Target environment** — CSE (AI & ML) at SBJIT Nagpur; extensible to any college department (department-scoped queries, per-department risk-weight profiles).
* **Engineering depth** — 21 FastAPI routers under `/api/v1`, 13+ React pages, JWT + role middleware on every route, cron automation with 10 scheduled jobs.
* **Cloud-ready architecture** — React SPA + FastAPI + Firebase Firestore/Auth/Storage, with an **embedded Firestore-compatible document store** so the platform also runs offline, in CI, and on a demo laptop with no GCP project (see `docs/05`).

**Out of scope (deliberate):** fees, admissions, attendance and timetable master data (ERP territory — Slide 7 says ERPs own those); mobile-native apps (PWA is roadmap); GPU/LLM inference (Slide 9 requires *zero* per-seat AI cost).

## 4. Background & operational motivation (Slide 4)

The four friction points the deck identifies, and the mechanism in this build that closes each:

| Observed failure | Root cause | HieraSync mechanism |
|---|---|---|
| **Lost approvals** — paper forms and chat messages leave no audit trail; requests stall for days | No state machine, no owner, no clock | Staged workflow with SLA timers, delegation, and a **hash-chained audit trail** (`app/engine/approvals.py`) |
| **Workload opacity** — HOD cannot see per-faculty load; distribution is guesswork | No aggregation of assignments | Weighted load vs. role-aware capacity, utilisation table and balance index in `/metrics/scorecard` |
| **Manual reporting** — NAAC/NBA packs assembled from Excel | No export path from live data | `/metrics/export` (CSV/JSON for tasks, faculty, approvals, audit, departments) + weekly auto-report job |
| **Missed deadlines** — no follow-ups or risk signals | Alerts only exist in someone's memory | Risk sweep + T‑3/T‑1/day-of reminders + overdue escalation ladder, delivered on 4 channels |

> **Motivation (deck, verbatim):** *digitize the hierarchy itself — every request flows through the correct authority with timestamps, comments and status.*
> **Opportunity:** *cloud + AI can automate prioritization, reminders and delay-risk alerts at near-zero operational cost.*
> **Outcome:** *faster decisions, fair workload distribution and accreditation-ready digital records.*

## 5. Problem statement (Slide 5, verbatim)

> "Academic departments lack a unified, role-aware digital system to assign, track, approve, and analyse teaching and administrative work — causing delays, operational opacity, and severe workload imbalance."

**Industry context.** The same defect appears outside academia: work is *assigned* but not *monitored*, so detection happens after the slip. The deck's 2025–26 evidence — a UNSW academic pilot cutting administrative workload ~60% with AI agents, and commercial suites (Asana/Monday) leading risk detection but **paywalling AI at $7–20/user/month** — frames the economic gap: the capability exists, the licensing does not fit a department budget.

**Target solution.** (1) **Zero-cost architecture** — heuristic AI, no per-seat licence, no GPU, no LLM token bill. (2) **Academic hierarchy first** — exact institutional role inheritance (Principal → HOD → Faculty → Staff), not a generic flat project board.

## 6. Project objectives (Slide 6) and how each is met

| # | Objective (deck) | Implementation | Proof |
|---|---|---|---|
| O1 | **Centralized workspace** — tasks, events, approvals, documents, goals, notifications in one secure portal | 22 routers, one document store, JWT-protected SPA | `tests/test_platform.py::TestApi::test_legacy_v1_pages_still_render` |
| O2 | **Two-stage digital approvals** — HOD → Principal with comments, decision logs, status | `app/engine/approvals.py` state machine + SLA + delegation + audit chain | `TestApprovals` (8 tests) + `POST /api/v1/workflow/{id}/audit` |
| O3 | **Follow-up automation** — in-app notification centre, scheduled daily 8 AM reminders, deadline alerts | 10 cron/interval jobs + durable outbox + 4 channels | `TestNotifyEngine`, `POST /api/v1/channels/jobs/{id}/run` |
| O4 | **AI assistance & risk engine** — deadline-risk prediction, priority scoring, conversational assistant, report generator | 8-factor explainable engine + weight calibration + Gemini-or-simulated chat + auto report generator | `TestRiskEngine`, `GET /api/v1/risk/*`, `docs/02` benchmark |
| O5 | **Analytics & one-click reports** — dashboards, faculty performance views, exportable department summaries | `/api/v1/metrics/*` with formula disclosure + CSV/JSON exports | `TestApi::test_scorecard_and_export` |

**Success criterion (deck, verbatim):** *"login as each role → assign → approve → notify → analyse."* This is executable, not aspirational:

```bash
cd backend && python scripts/e2e_demo.py       # prints a 12-stage transcript
```

## 7. Scope boundaries

* Department-level web deployment for CSE (AI & ML); web-first responsive UI.
* Firebase (or embedded store) as the cloud backend — no on-premise server to install.
* Heuristic AI with **no GPU servers** and no paid inference.
* Human-in-the-loop: the system *signals* and *routes*; an approver always decides (Slide 8 gap → "full automation risks overload").
* Multi-department/multi-tenant SaaS and PWA push are roadmap items, not delivered claims (`docs/07`).
