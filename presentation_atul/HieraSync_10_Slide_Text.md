# HieraSync AI — 10-Slide Presentation (Full Text)

**Project repository:** https://github.com/Atulgupta07/Hiera_Sync
**Deck file:** `HieraSync_AI_10_Slides.pptx` (10 slides, 16:9, speaker notes on every slide)

**Verified facts pulled from the actual repository:**

| Item | Value (counted from code) |
|---|---|
| Backend routers (modules) | 20 |
| REST API endpoints | 95 |
| Backend Python code | ~7,212 lines |
| Frontend TypeScript/TSX code | ~11,444 lines |
| Total code | ~18,650 lines |
| Frontend screens/pages | 17 |
| Pydantic data models | 9 (User, Department, Task, Event, Approval, Notification, Document, TaskRequest, DepartmentGoal) |
| User roles | 10 |
| Backend service name (in code) | `CampusPulse API` |

---

## SLIDE 1 — TITLE

**HieraSync AI**
Smart College Workflow, Task & Event Management System

One platform to assign work, approve requests, track progress and auto-generate reports — with an AI assistant built in.

- Repository: github.com/Atulgupta07/Hiera_Sync
- **20** API Modules · **95** REST Endpoints · **~18,650** Lines of Code · **10** User Roles · **17** App Screens · **9** Data Models
- Presented by: Atul Gupta & Team
- Guide: Prof. ______________
- Department: Computer Science & Engineering (AI & ML)
- Stack: React 19 · FastAPI · Firebase · Google Gemini

**🎤 Say this:** "Good morning. Our project is HieraSync AI — a smart college workflow, task and event management system. In one line: it replaces notices, registers, Excel sheets and WhatsApp chasing with a single role-based web platform that also has an AI assistant. It is a full working system — 20 backend modules, 95 REST endpoints, about 18,650 lines of code, 17 screens and 10 user roles."

---

## SLIDE 2 — INTRODUCTION

> HieraSync AI (backend service name: **CampusPulse API**) is a web-based platform that brings every department activity — tasks, approvals, events, goals, files and reports — into **one secure, role-based system**, with an AI assistant that answers questions from live data.

**What the system actually does**
- **Single login for the full hierarchy —** Principal → HOD → Faculty → Staff / Students (10 roles)
- **Work is assigned as tasks —** with deadline, priority, progress %, comments & attachments
- **Requests & approvals move in a chain —** HOD stage, then Principal stage, fully logged
- **AI assistant (Google Gemini) —** answers using your real tasks, approvals and events
- **Automatic reminders —** in-app + WhatsApp, checked by a background job every 5 minutes
- **Academic calendar PDFs —** uploaded once, parsed by AI into categorised events

**Key numbers:** 95 REST Endpoints · 20 Backend Modules · 17 Frontend Screens · 9 Firestore Data Models

**Diagram — From manual work → to one automated system**

| | Step 1 | Step 2 | Step 3 | Step 4 | Step 5 |
|---|---|---|---|---|---|
| **BEFORE** | Notice on board | WhatsApp group | Register / Excel | Phone follow-up | Report typed by hand |
| **WITH HIERASYNC** | Login (role-based) | Assign task | Auto notify + remind | Track progress live | One-click report |

**🎤 Say this:** "Everything a department does happens inside one role-based system. The bottom strip shows the core idea: today the flow is notice → WhatsApp → register → phone follow-up → hand-typed report. With HieraSync it becomes login → assign → auto-notify → track → one-click report. Same work, but recorded, automatic and measurable."

---

## SLIDE 3 — PROBLEM STATEMENT & OBJECTIVES

**Problem Statement:** College departments still run on notices, WhatsApp groups, registers and Excel sheets — so work is invisible, approvals are slow, deadlines are missed and every report has to be rebuilt by hand.

**Problems identified**
1. No single place to see who is doing what, and by when
2. Approvals travel on paper or WhatsApp — no status, no trail
3. Deadlines are missed because every reminder is manual
4. The academic calendar is a PDF that nobody re-reads
5. NAAC / NBA reports are re-created by hand every time
6. Faculty workload is invisible, so work is unevenly divided
7. Files, proofs and discussions are scattered across chats
8. New faculty have no record of past activities

**Objectives of the project**
1. Build one secure, role-based platform for the whole hierarchy
2. Digitise task assignment with deadline, priority, progress & proof
3. Automate a two-stage approval workflow (HOD → Principal)
4. Send reminders automatically — in-app and on WhatsApp
5. Convert uploaded academic-calendar files into events using AI
6. Provide an AI assistant that answers from live department data
7. Warn about risky deadlines before they are actually missed
8. Generate dashboards, analytics and exportable reports in one click

**🎤 Say this:** "On the left are the eight problems we found. On the right are our eight objectives, and each objective directly answers a problem. Every one of these eight objectives is implemented in the code."

---

## SLIDE 4 — LITERATURE SURVEY

We studied the systems a college department already uses. Each one solves a part of the problem — none covers a department end-to-end.

| Existing approach | What it does well | Limitation for a department | HieraSync AI answer |
|---|---|---|---|
| Registers, notices & WhatsApp groups | Zero cost, everyone already knows how to use it | No tracking, no history, no reports; information is lost in chat | Same simplicity, but every action is recorded, searchable and reportable |
| College ERP / MIS software | Strong for admission, fees, attendance and exam records | Stores records only — no day-to-day task assignment or approval flow | Adds the missing workflow, approval and progress-tracking layer |
| Corporate PM tools (Trello, Asana, Jira) | Excellent task boards and progress views | Paid per user; no HOD→Principal hierarchy, no academic calendar | Free stack, hierarchy-aware roles and academic-specific modules |
| Google Classroom / Workspace | Good for teaching material and file sharing | Built for teacher↔student, not for staff duties, approvals or events | Covers the staff-side operations that Classroom does not touch |
| Generic AI chatbots (ChatGPT etc.) | Very good natural-language answers | Knows nothing about your tasks, deadlines or pending approvals | Gemini + live Firestore context, so it answers about YOUR actual work |

**Research gap:** no single free system combines hierarchy-based task workflow + two-stage approvals + academic calendar intelligence + an AI assistant that reads live institutional data.

**🎤 Say this:** "Manual registers are free but leave no record. ERPs handle fees and exams but not daily work. Trello and Asana charge per user and have no HOD-to-Principal hierarchy. Classroom is teacher-student only. Generic chatbots know nothing about our actual tasks. The gap at the bottom is exactly what our project fills."

---

## SLIDE 5 — SYSTEM DESIGN (Three-Tier Architecture)

**TIER 1 — PRESENTATION · Client / Browser**
- React 19 Single Page App
- 17 screens · Redux Toolkit store
- ProtectedRoute + AuthContext
- FullCalendar · Recharts · dnd-kit
- Tailwind CSS 4 responsive UI

↕ *HTTPS — REST / JSON*

**TIER 2 — APPLICATION · FastAPI Server**
- 20 routers → 95 REST endpoints
- JWT verify + `check_role()` guard
- APScheduler background jobs
- Document parser (PDF/DOCX/XLSX)
- Risk engine + AI service layer

↕ *Admin SDK / HTTPS*

**TIER 3 — DATA & SERVICES · Firebase + External APIs**
- Firestore NoSQL collections
- Firebase Auth · Firebase Storage
- Google Gemini 1.5 Flash API
- WhatsApp Cloud API v22.0
- SMTP e-mail notifications

**Request flow:** 1 User clicks in React screen → 2 `fetch()` with Bearer JWT → 3 FastAPI checks token + role → 4 Firestore read/write → 5 Notify · WhatsApp · Gemini → 6 JSON back → UI updates

**Cross-cutting:** JWT HS256 · 30 min | `check_role()` RBAC | CORS middleware | APScheduler · every 5 min | Central logging | 503 handlers for API errors

**🎤 Say this:** "Tier 1 is the browser — React 19, 17 screens. Tier 2 is FastAPI — 20 routers, 95 endpoints, plus JWT check, role guard, scheduler, document parser and AI service. Tier 3 is Firebase plus the external Gemini and WhatsApp APIs. Follow the flow: user clicks, browser sends fetch with a Bearer JWT, FastAPI validates token and role, reads or writes Firestore, triggers notifications or AI, returns JSON."

---

## SLIDE 6 — TECHNOLOGY USED

| Layer | Technologies used in the project | Why it was chosen |
|---|---|---|
| **Frontend** | React 19.2, TypeScript 6, Vite 8, Tailwind CSS 4, Redux Toolkit, React Router 7, FullCalendar 6, Recharts 3, dnd-kit, Framer Motion, Lucide icons | Fast dev server, type safety, ready-made calendar & charts |
| **Backend** | Python + FastAPI, Uvicorn ASGI server, Pydantic v2 schemas, pydantic-settings, modular router architecture (20 routers) | Async, very fast, free Swagger API docs at `/docs` |
| **Database** | Firebase Firestore (NoSQL) — collections for users, tasks, events, approvals, requests, goals, notifications, join_requests | Real-time, schema-flexible, no server to maintain, free tier |
| **Security** | Firebase Authentication, JWT (python-jose, HS256, 30-min expiry), passlib + bcrypt hashing, `check_role()` RBAC dependency | Industry-standard auth; one guard protects every endpoint |
| **AI & Integrations** | Google Gemini 1.5 Flash REST API with local fallback engine, WhatsApp Cloud API v22.0, SMTP e-mail, APScheduler | Real AI answers; system still works even if the AI key is missing |
| **Files & Reports** | pypdf, python-docx, openpyxl for PDF/Word/Excel parsing; Firebase Storage; CSV & report export endpoints | Accepts whatever format the office already has |
| **Tools & Deployment** | Git & GitHub, VS Code, Oxlint, Swagger UI; backend → Cloud Run / Render, frontend → Vercel / Firebase Hosting | Free hosting tiers suitable for a college deployment |

**🎤 Say this:** "FastAPI was chosen because it is async, fast, and auto-generates Swagger docs at slash-docs which we use for testing. Firestore means no SQL server to maintain. And importantly — we wrote a local fallback engine, so if the Gemini key is missing the assistant still answers from Firestore data."

---

## SLIDE 7 — DEVELOPED MODULES (20 Modules, 95 Endpoints)

| Module | API | What it does in the system |
|---|---|---|
| Authentication & Employees | 8 | Register, login (JWT), `/me` profile, forgot-password, employee list & CRUD by role |
| Departments & Join Requests | 10 | Create department, unique join code, faculty join request → HOD approve / reject |
| Tasks & Reviews | 6 | Create, update, delete, assign & co-assign tasks; submit for review; AI risk score |
| Comments & Attachments | 7 | Threaded comments on a task; upload, list, download and delete proof files |
| Task Requests | 4 | 8 request types (leave, resource, deadline extension…); approval auto-creates a task |
| Two-Stage Approvals | 5 | Raise request → HOD stage → Principal stage; approve / reject with comments & trail |
| Events & Smart Calendar | 6 | Event CRUD, participants, meeting link, conflict checking, recurring events |
| Institutional Calendar (AI) | 8 | Upload PDF/DOCX/XLSX → AI extracts & categorises → draft → publish → history |
| Department Goals | 8 | Long-term goals with category, target date, status and milestone tracking |
| AI Assistant | 4 | Dashboard summary, Gemini chat on live data, AI report generation, checklist suggestions |
| Notifications & WhatsApp | 13 | 8 notification types, unread count, mark-read; WhatsApp send, opt-in, webhook, dedup |
| Reports & Analytics | 8 | Dashboard stats, recent activity, summaries, per-task reports, export, faculty performance |
| Files, Search, Settings | 8 | Firebase Storage upload/download, global search, profile & department settings, health check |

**Enumerations defined in the models:**
- **Roles (10):** Admin · Principal · HOD · Teacher · Faculty · TA · Student · Student-Rep · Lab Assistant · Staff
- **Task status (5):** TODO → IN_PROGRESS → IN_REVIEW → COMPLETED / OVERDUE
- **Priority (4):** Low · Medium · High · Urgent
- **Request types (8):** Task, Deadline Extension, Leave, Event, Document, Resource, Collaboration, General
- **Notification types (8):** Task Assigned, Event Invite, Approval Request, System Alert, Request Submitted / Approved / Rejected / Comment

**🎤 Say this:** "Two modules are our highlights. The Institutional Calendar module lets the office upload the official academic calendar as a PDF, Word or Excel file; our parser extracts the activities and the AI categorises them into eleven types like Examination, Workshop or Holiday, we review it as a draft, then publish it to everyone's calendar. The AI Assistant sends the user's live tasks, approvals and events to Gemini as context, so its answers are about your real work, not generic advice."

---

## SLIDE 8 — ADVANTAGES & APPLICATIONS

**Advantages**
- One login replaces registers, Excel sheets and WhatsApp chasing
- Every task, approval and comment is time-stamped and searchable
- Reminders are automatic — nothing depends on someone remembering
- AI risk score warns before a deadline is actually missed
- Reports and analytics are produced in one click, not one week
- Role-based access: each person sees only what concerns them
- Works even without the AI key — local fallback engine answers
- Free & open stack — Firebase free tier, no per-user licence cost
- Browser-based: works on laptop and mobile, nothing to install

**Applications**
- Department task & duty allotment
- Seminar, workshop & event management
- Leave, resource & document approvals
- Academic calendar publishing
- NAAC / NBA / AICTE documentation
- Faculty workload & performance analytics
- Student-rep & lab staff coordination
- Any hierarchical office (school, admin block)

**Who benefits**
| Role | Gains |
|---|---|
| Principal | Full-institute visibility & approvals |
| HOD | Assign, monitor and control department work |
| Faculty | Clear list of duties, deadlines & reminders |
| Staff / Students | One channel to raise and track requests |

**🎤 Say this:** "Note the seventh advantage — even without a Gemini key the assistant still works, because we wrote a local fallback engine. And the same system fits any hierarchical office, not just a college department."

---

## SLIDE 9 — REFERENCES

1. **FastAPI Documentation** — fastapi.tiangolo.com — Backend framework, routers, dependency injection
2. **React Documentation** — react.dev — React 19 components, hooks and routing
3. **Firebase Firestore Docs** — firebase.google.com/docs/firestore — NoSQL collections, queries and security rules
4. **Firebase Authentication** — firebase.google.com/docs/auth — Identity, sign-in methods, Admin SDK
5. **Google Gemini API** — ai.google.dev/gemini-api/docs — Gemini 1.5 Flash generateContent REST API
6. **WhatsApp Cloud API** — developers.facebook.com/docs/whatsapp — Template messages, webhooks, v22.0
7. **APScheduler Documentation** — apscheduler.readthedocs.io — Background jobs for 5-minute reminders
8. **Pydantic v2 Documentation** — docs.pydantic.dev — Request/response schemas and validation
9. **Tailwind CSS & Vite** — tailwindcss.com · vite.dev — Utility-first styling and build tooling
10. **Project Repository** — github.com/Atulgupta07/Hiera_Sync — Complete source code of this project

---

## SLIDE 10 — CONCLUSION

> HieraSync AI converts scattered, manual department work into one recorded, automated and measurable workflow — and adds an AI layer that reads the institution's own live data.

| | |
|---|---|
| **BUILT** | 20 backend modules, 95 REST endpoints, 17 screens, ~18,650 lines of code |
| **WORKING** | End-to-end flow runs: register → join dept → assign task → approve → report |
| **INTELLIGENT** | Gemini assistant, deadline-risk engine and AI academic-calendar parsing |
| **PRACTICAL** | Free stack, browser-based, mobile friendly, role-based and deployment ready |

**Future Scope**
- Android / iOS mobile app with push notifications
- Direct export into NAAC & NBA report templates
- Timetable and attendance system integration
- Multi-department and multi-college rollout
- Formal unit testing, load testing and security audit
- Offline mode with automatic sync when back online

**What we learned**
- Designing a real REST API with role-based security
- Working with a NoSQL database and cloud services
- Integrating a live LLM with safe fallback handling
- Building a responsive React + TypeScript front end
- Turning a real institutional problem into software

**Thank You — Questions are welcome.**

---

# 📌 EXTRA: Likely viva questions & answers

**Q: Why FastAPI and not Django/Flask?**
A: FastAPI is async and fast, uses Pydantic for automatic request validation, and auto-generates interactive Swagger documentation at `/docs` — which we used to test all 95 endpoints without writing a separate client.

**Q: Why Firestore and not MySQL?**
A: Our data is document-shaped (a task with nested comments, attachments, assignees) and changes shape as features grow. Firestore is schema-flexible, real-time, needs no server maintenance and has a free tier. For a college deployment with no dedicated DB admin, that matters.

**Q: How is security handled?**
A: Three layers. (1) Firebase Authentication for identity. (2) Our own JWT signed with HS256, expiring in 30 minutes. (3) A `check_role()` FastAPI dependency that every protected endpoint declares — it loads the current user and rejects with HTTP 403 if their role is not in the allowed list. Passwords are hashed with bcrypt via passlib, never stored in plain text.

**Q: Is the AI real, or hard-coded?**
A: Real. We call Google Gemini 1.5 Flash over its REST API, and we inject live context — the user's current tasks, pending approvals and upcoming events pulled from Firestore — into the system prompt. If the API key is missing or the call fails, we fall back to a local keyword-matching engine over the same Firestore context, so the feature degrades gracefully instead of crashing.

**Q: How does the deadline-risk score work?**
A: It is a deterministic, explainable heuristic in `calculate_task_risk()`. Points are added for deadline pressure (overdue = +90, ≤2 days = +50, ≤5 days = +30), low progress near a deadline (+25), high priority (+15) and faculty overload of more than 3 active tasks (+20). The total is clamped to a 0–100 scale, then labelled HIGH above 70, MEDIUM above 40, otherwise LOW — and the system returns the list of reasons, so it is never a black box.

**Q: How does the academic calendar AI work?**
A: The office uploads the official calendar as PDF, DOCX or XLSX. `document_parser.py` extracts text and tables using pypdf, python-docx or openpyxl. Then `institutional_ai.py` matches the extracted activities against keyword sets and classifies each into one of 11 categories — Examination, Internal Assessment, Workshop, Seminar, Meeting, Holiday, Faculty Development, Student Activity, Academic Deadline, Teaching & Learning, or Events. The result is saved as a draft for human review, and only published to everyone's calendar after approval.

**Q: How do WhatsApp reminders avoid spamming?**
A: A background APScheduler job runs every 5 minutes, independent of any page refresh. For each event with reminders enabled it computes the trigger time (1 hour / 2 hours / 1 day before) and builds a deduplication key from event ID + participant ID + timing + date. If that key was already sent, it skips. So refreshing the page or restarting the server never re-sends a reminder.

**Q: What is the difference between an Approval and a Task Request?**
A: A Task Request is raised by a faculty member and reviewed by the HOD — approving it automatically creates a real task. An Approval is the formal two-stage institutional chain: it moves from HOD stage to Principal stage, and each stage stores its own comment, so there is a full audit trail.

**Q: What are the limitations?**
A: We are honest about three. (1) We have done manual functional testing through Swagger and role walkthroughs, but not yet a formal automated unit-test suite. (2) We have not run load testing, so we cannot quote concurrency figures yet. (3) CORS is currently open for development and must be restricted to the college domain before production deployment. All three are in our future scope.

---

# ⚠️ Before you present — 4 things to do

1. **Fill in slide 1** — replace "Atul Gupta & Team" with all team member names and roll numbers, and add your guide's name and your college name.
2. **Add 2–3 screenshots** of the running app (Dashboard, Tasks board, AI Assistant) — only you can take these, and they are the single most convincing addition.
3. **Save a PDF backup** (File → Save As → PDF) and carry it on a pen drive and your phone — seminar hall PCs often break fonts.
4. **Practice slides 5 and 7** — these are the two slides examiners ask about most. Know the request flow and be able to name any module's purpose.
