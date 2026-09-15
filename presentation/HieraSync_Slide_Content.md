# HieraSync AI — Review Seminar-I Presentation Kit

**File:** `HieraSync_Review_Seminar_I.pptx` — 25 slides, 16:9, editable (PowerPoint / Google Slides / LibreOffice).
**Charts:** `charts/` — module_progress.png, efficiency.png, risk_donut.png (already embedded in the PPT).
**Regenerate anytime:** `python3 make_charts.py && python3 build_ppt.py`

---

## 1. Slide map (covers your required 10-point format)

| # | Slide | Maps to format point |
|---|-------|----------------------|
| 1 | Title — HieraSync AI, college, names | 1. Title |
| 2 | Presentation Roadmap | (flow) |
| 3–4 | Introduction + Background & Motivation | 2. Introduction |
| 5–6 | Problem Statement + Objectives & Scope | 3. Problem Statement & Objectives |
| 7–8 | Existing systems table + Papers & gaps | 4. Literature Survey |
| 9–15 | Approach, Architecture, DFD-0, DFD-1, Use Case, DB design, Approval flowchart | 5. System Design |
| 16 | Technology stack & justification | 6. Technology Used |
| 17–19 | Module status table + 2 deep-dives | 7. Developed Modules |
| 20–21 | Advantages (+chart) + Applications & Future Scope | 8. Advantages & Applications |
| 22 | Progress status & plan ahead | (Review-I requirement) |
| 23 | References (IEEE style, real links) | 9. References |
| 24 | Conclusion | 10. Conclusion |
| 25 | Thank You + demo invite | (closing) |

Every slide has **speaker notes** (View → Notes in PowerPoint) — a ready 30–60 sec script per slide.

---

## 2. ⚠️ Things YOU must do (I can't do these for you)

1. **Fill your details** (5 min): open the PPT, slides 1 & 25 — replace `[Your Name]`, `[Roll No]`, `[Guide Name]`, `[Designation]`. If it's a group project, add all names on slide 1.
2. **Verify % claims** (10 min): slides 17/19/22 say ~90% core done, AI 80%. If anything in the repo doesn't run, lower that module's number in `build_ppt.py` + `make_charts.py` and rebuild — reviewers WILL ask "show it working."
3. **Practice the demo path** (most important): login as HOD → create/assign task → login as faculty → update progress → raise approval → login as principal → approve → show AI risk + analytics + notification. Keep backend + frontend running before your slot; keep seed/demo data ready.
4. **Optional but impressive:** take 2–3 real screenshots (Dashboard, Kanban tasks, Approvals) and add one "Live Screens" slide after slide 19. (I didn't add screenshots because I can't run your Firebase backend here.)
5. **Carry:** PPT on pen drive + email it to yourself; print 1 copy of slides 5, 6, 10, 15, 17 (reviewers love pointing at the flowchart).
6. **Cite honestly:** the efficiency chart (slide 20) is labelled *estimated* — if asked, say "projected from manual workflow observation, to be validated in pilot testing." Never present estimates as measured data.

---

## 3. Full slide content (text backup)

### S1 Title
HieraSync AI — Smart Academic Workflow & Event Management System. Dept. of CSE (AI & ML), S. B. Jain Institute of Technology, Management & Research, Nagpur. AY 2026–27. At-a-glance: 17+ REST modules, 13+ pages, 10 roles, 2-stage approvals, AI engine.

### S2 Roadmap
01 Title · 02 Introduction · 03 Problem & Objectives · 04 Literature Survey · 05 System Design · 06 Technology Used · 07 Developed Modules · 08 Advantages & Uses · 09 References · 10 Conclusion.

### S3 Introduction
Full-stack role-aware platform centralizing tasks, events, approvals, notifications, goals, reports + AI. Principal→HOD→Faculty→Staff/Students. Built for CSE (AI & ML), SBJIT; generalizable. Replaces registers/WhatsApp/Excel.

### S4 Background & Motivation
Pains: lost approvals, no workload view, manual NAAC reporting, missed deadlines. Fix: digitize the hierarchy; cloud + AI automation at near-zero ops cost. Evidence strip: UNSW pilot 60% admin cut (2025); Asana AI paywall $10.99+/user (2026).

### S5 Problem Statement
"Academic departments lack a unified, role-aware digital system to assign, track, approve and analyse teaching and administrative work — causing delays, opacity and overload." 4 cards: fragmented communication, no audit trail, approval bottleneck, zero insight.

### S6 Objectives & Scope
O1 central workspace · O2 HOD→Principal approvals · O3 automated reminders · O4 AI risk/priority/chat/reports · O5 analytics & one-click reports. Scope: department-level web pilot; success = all 5 demoed live.

### S7 Existing systems table
Manual/Excel/WhatsApp · Traditional ERPs · **AI PM suites 2026 (Asana, Monday, ClickUp, Notion AI — paywalled $7–20/user/mo, corporate-generic)** · Google Workspace · Moodle — strengths vs limitations; inference: none combine hierarchy + workflows + approvals + analytics + AI at low cost.

### S8 Papers & gaps
[1] IEEE Xplore 10743425 (ERP efficiency vs cost/complexity) · [2] IJERT 2026 modular web ERP (router-per-module) · [3] Frontiers 2025 Khairullah (AI in HEI admin — risk engine + analytics) · [4] Frontiers 2025 Buele (human-in-the-loop caution). Also reviewed: AI-agents study (60% cut), IJARSCT Django ERP, 2026 AI-PM app surveys. Gaps→answers: faculty workflows, zero-cost AI engine, human-in-loop approvals, serverless stack.

### S9 Design approach
Agile vertical slices; 3-tier SPA→REST→BaaS; JWT+RBAC per request; APScheduler cron; Firestore; router-per-module; heuristic AI.

### S10 Architecture
Tier 1 React 19+TS+Vite · Tier 2 FastAPI /api/v1 (17 routers, JWT/RBAC/CORS, scheduler) · Tier 3 Firebase (Firestore/Auth/Storage). Stateless REST, JWT header, /docs.

### S11 DFD Level 0
System (0) with Faculty, HOD, Principal/Admin, Cloud Services; flows: updates, tasks/approvals, decisions, persist/alerts.

### S12 DFD Level 1
P1 Users & Roles · P2 Tasks & Events · P3 Approvals · P4 Notify & Remind · P5 AI & Reports; D1 Users · D2 Tasks/Events · D3 Approvals · D4 Notify Log.

### S13 Use Case
Actors Admin/Principal/HOD/Faculty × 12 use cases (login, employees, tasks, progress, requests, 2 approvals, events, analytics, AI chat, alerts, goals).

### S14 DB design
users · departments · tasks · approvals · events · notifications · goals · comments/attachments subcollections + relationship line.

### S15 Approval flowchart
START → HOD review → diamond → forward to Principal → diamond → APPROVED ✓ (notify+log) / REJECTED ✕ + reason. Stages: PENDING → APPROVED_HOD → APPROVED_PRINCIPAL.

### S16 Technology
React 19+TS+Vite · Tailwind v4/Motion/lucide · FullCalendar/Recharts/dnd-kit · FastAPI+Pydantic · Firebase Auth+JWT · Firestore · Storage+APScheduler + why each.

### S17 Module status
M1 Auth 100% · M2 Employees 95% · M3 Tasks 95% · M4 Events 90% · M5 Approvals 90% · M6 Notifications 85% · M7 AI 80% · M8 Analytics 85% · M9 Goals/social 90%.

### S18 Deep-dive A
Tasks: Kanban dnd-kit, subtasks, goal links, mentions, attachments, role dashboards. AI: 0–100 risk score, LOW/MED/HIGH + factors, 3 endpoints, HOD action items, no GPU.

### S19 Deep-dive B
Approvals stages/history · Analytics stats/faculty performance/export · Notifications center/cron/email-hook + progress chart.

### S20 Advantages
Single source of truth · faster approvals · audit trail · proactive alerts · data-driven leadership · low cost + secure + efficiency chart (~80–90% est. saving).

### S21 Applications & future
Applications: dept governance, approvals, NAAC docs, appraisals, clubs/labs, multi-dept. Future: mobile/PWA, ML prediction, timetable/attendance, SMS gateway, multi-college SaaS.

### S22 Progress & plan
Done: scaffold, 17 routers, 13+ pages, approvals/scheduler/AI. In progress: chat polish, testing, deployment. Timeline: Review-I ~90% (Sep 26) → hardening (Oct) → Review-II (Nov) → final (Dec).

### S23 References (10 entries)
[1] IEEE Xplore 10743425 · [2] IJERT 2026 · [3] IJCRT1812344 · [4] IJARSCT Django ERP · [5] Frontiers 2025 Khairullah (AI in HEI admin) · [6] ResearchGate AI Agents in HE (60% cut) · [7] ResearchGate AI-Powered Workflows · [8] Frontiers 2025 Buele (faculty perceptions) · [9] Dupple 2026 AI-PM comparison · [10] Stack docs + repo.

### S24 Conclusion
Unified auditable platform; automated follow-ups; AI foresight; all 5 objectives live-demoable. "HieraSync turns departmental chaos into a calm, transparent workflow."

### S25 Thank You
Demo + Q&A invite, repo link, names.

---

## 4. Likely viva questions + model answers

1. **What problem does your project solve, in one minute?** → Departments run on paper/WhatsApp/Excel: approvals stall, nobody sees workload, reports are manual. HieraSync is one role-aware web workspace for tasks, approvals, events, alerts, analytics + AI risk prediction.
2. **What is novel vs Trello/ERP?** → Academic hierarchy built-in (HOD→Principal stages), faculty-performance analytics, AI delay-risk scoring, all on a low-cost serverless stack — surveyed tools cover only parts.
3. **Explain your architecture.** → 3-tier: React SPA → FastAPI REST (17 routers, JWT+RBAC middleware) → Firebase (Firestore/Auth/Storage); APScheduler cron for reminders; stateless JSON APIs.
4. **Why Firestore, not MySQL/Postgres?** → Flexible workflow documents, serverless scaling, zero DB ops, generous free tier, realtime-ready; relations enforced at API layer with Pydantic.
5. **How does authentication/authorization work?** → Firebase Auth + JWT (python-jose); token in header; `get_current_user` + `check_role([...])` dependencies guard every endpoint; frontend ProtectedRoute + AuthContext.
6. **Explain the approval workflow.** → State machine PENDING → APPROVED_HOD → APPROVED_PRINCIPAL / REJECTED; comments + timestamps at each stage; notifications on transitions; task-requests auto-create tasks on approval.
7. **What does the "AI" actually do?** → Heuristic risk engine: deadline proximity + progress lag + assignee workload → 0–100 score, LOW/MED/HIGH + factors; dashboard summaries; chat endpoint; report generation. Deterministic, explainable, no GPU.
8. **How is risk_score calculated?** → `calculate_task_risk()` in tasks.py: completed→0; else weighted signals (days left vs progress %, overload count) produce score + factor strings shown as badges.
9. **DFD Level 0 vs Level 1?** → L0 = whole system as one bubble + external entities; L1 = internal processes P1–P5 + data stores D1–D4 and flows between them.
10. **How do notifications/reminders work?** → Notification collection + in-app center with unread counts; APScheduler cron daily 8 AM scans deadlines and creates alerts; email hook ready.
11. **Testing done?** → (Answer honestly) Manual API testing via OpenAPI /docs + UI walkthroughs per role; automated test suite + UAT planned in hardening phase (Oct).
12. **Deployment plan?** → Frontend on Vercel/Firebase Hosting; backend on Cloud Run; Firestore/Storage already cloud; env-based config; pilot in CSE (AI & ML).
13. **Limitations?** → Web-only (no native mobile yet); heuristic (not ML-learned) risk; email/SMS gateway not fully wired; single-department pilot scope.
14. **Individual contribution?** → Prepare 2–3 lines each: who built which routers/pages (e.g., auth+tasks, approvals+analytics, AI+notifications, UI shell).
15. **Why is % X and not 100?** → Point to slide 22: core done; remaining = polish, tests, deployment — scheduled before Review-II.
16. **Why not just use Asana/ClickUp/Notion?** → 2026 surveys: their AI is paywalled $7–20/user/month, they are corporate-generic with no HOD→Principal academic approval hierarchy, no faculty-performance analytics. HieraSync is free, academic-first, and purpose-built.
17. **What recent research supports AI in administration?** → Frontiers 2025 (Khairullah): AI scheduling/resource/decision support in HEIs incl. Univ. of Murcia case; 2025 AI-agents study: 60% admin workload cut in UNSW pilot; Buele 2025: keep humans in the loop — which is exactly our approval design.

---

## 5. Image prompts (optional extras — only if you want AI art)

I already generated all *required* diagrams/charts natively. Use these prompts only if you want decorative AI images (e.g., for the title background or poster):

1. **Title backdrop:** "Modern flat vector illustration, Indian engineering college campus building at dusk, subtle digital network overlay connecting faculty icons, deep navy blue and gold palette, clean, professional, wide 16:9, no text"
2. **Workflow concept:** "Minimal isometric illustration of a task approval pipeline: document icon moving through three checkpoints labeled only with abstract badges, indigo and cyan on light background, flat design, no text"
3. **AI analytics concept:** "Flat dashboard illustration with abstract charts, gauges and a graduation cap motif, navy/indigo/cyan palette, modern SaaS style, clean, no readable text"

> Tip: keep the title slide as-is (clean + formal scores better in reviews than busy AI art). If you add an image, put it only on slide 1's right card or slide 25's background at 15% transparency.
