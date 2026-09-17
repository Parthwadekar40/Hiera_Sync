# HiéraSync AI — Academic Workflow Platform

A modern web-based platform for the CSE (Artificial Intelligence & Machine Learning) department of
Sinhgad Academy of Technology, Nagpur. It centralises department operations: research tracking,
task workflow, the faculty activity calendar, approvals, AI insights and progress analysis.

## Key Features

- **Activity Calendar** (`/calendar`) — FullCalendar month/week/day/list views with a live
  day-by-day agenda for the selected date, quick filters (type, priority, status, owner),
  keyword search, drag-and-drop rescheduling, click-and-drag time range selection, a compact
  heat view for spotting overloaded days, ICS/CSV export, and a side drawer for creating or
  editing activities with live validation (double-booking and past-date warnings).
- **Approvals desk** (`/approvals`) — decision queue with status tabs, search, per-request
  reviewer notes, new-request submission and requester notifications.
- **Research tracker** (`/employees`) — faculty profiles, area of interest, publication and
  project counts.
- **Tasks, Goals, Reports, Notifications and an AI assistant** for the day-to-day HOD/faculty loop.
- **Offline-safe UI** — when the API is unreachable, the calendar and approvals desk fall back to
  a local preview dataset (marked in the banner) so the pages can still be reviewed.
- **Demo mode** — if `firebase-credentials.json` is missing or unreachable, the API boots on a
  process-local in-memory database (sample activities and approvals are seeded on first read, and
  newly registered accounts are activated straight away instead of waiting on a join-request
  approval — with real Firebase credentials the normal PENDING → HOD approval flow applies).
  `GET /health` reports which mode is live.

```bash
cd backend && python scripts/seed_demo.py --password Hiera@2026   # faculty + a month of activities
```

## Quick Start (no Firebase needed)

Prerequisites: **Node.js 20.19+ or 22 LTS** (`node -v`) and **Python 3.10–3.12** (`python --version`).
Vite 8 refuses older Node versions, so upgrade before you start.

**Windows PowerShell**

A Windows venv stores its scripts in `.venv\Scripts\`, not `.venv\bin\` — so the usual
`source .venv/bin/activate` fails with *"No such file or directory"* in Git Bash. Activate with
`.venv\Scripts\Activate.ps1` (PowerShell) or `source .venv/Scripts/activate` (Git Bash), or skip
activation altogether and call the venv interpreter directly.

```powershell
git clone https://github.com/Parthwadekar40/Hiera_Sync.git
cd Hiera_Sync\backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000      # terminal 1
```

```powershell
cd ..\frontend
npm install
npm run dev                                               # terminal 2
```

Same commands from **Git Bash**, where activation is optional:

```bash
python -m venv .venv
source .venv/Scripts/activate                        # or skip it entirely:
./.venv/Scripts/python.exe -m pip install -r requirements.txt
./.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000
```

**macOS / Linux**

```bash
git clone https://github.com/Parthwadekar40/Hiera_Sync.git
cd Hiera_Sync/backend
python3 -m venv .venv && source .venv/bin/activate
# If venv creation fails on Debian/Ubuntu ("ensurepip is not available"):
#   sudo apt install python3-venv   # then re-run the line above
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000       # terminal 1
```

```bash
cd ../frontend
npm install
npm run dev                                               # terminal 2
```

Then seed some data (third terminal, from `backend/`, keep the API running):

```bash
python scripts/seed_demo.py --password Hiera@2026
```

Open **http://localhost:5173** and sign in with `hod@sbjit.edu.in` / `Hiera@2026`
(faculty accounts use the same password: `neha@`, `sweta@`, `preeti@`, `bhushan@sbjit.edu.in`).

What to look at:

| Page | What should happen |
| --- | --- |
| `/calendar` | Month grid with activities, today highlighted, day agenda on the right, filters + ICS/CSV export, drag an activity to another day (it persists), **Manage → Heat view**, and the create/edit drawer warns about double bookings. |
| `/approvals` | Decision queue with tabs, the "Suggested order" strip, Approve / Send-back with a note, New Request modal. Sign in as a faculty account to see the read-only variant. |
| `/notifications` | The reminders the API queued for the assignee, plus the AI digest button. |
| `/reports` | Charts, CSV export of the current filters. |
| `/` (landing) | The new type pairing — Roboto Slab display over Manrope body. |

No `firebase-credentials.json`? The API boots in **demo mode**: an in-memory database, sample
activities seeded on first read, accounts activated immediately. Check `http://127.0.0.1:8000/health`
— it answers `{"database": "memory (volatile demo data)"}`. Data resets when the API restarts
(`--reload` restarts on every backend file change, so re-run the seed script after editing the backend).

To use real Firestore instead, follow **Setup Instructions → Firebase Setup** below; the app switches
over as soon as `backend/firebase-credentials.json` exists and `FIREBASE_PROJECT_ID` matches.

### Starting a fresh Firestore project (first login)

Login checks the bcrypt hash on the `users/{uid}` document in Firestore — it does **not** ask Firebase
Authentication. So an account created in the Firebase console cannot sign in, and an empty database has
no account to sign in with. Addresses are compared case-insensitively: registering as `Hod@SBJIT.edu.in`
and typing `hod@sbjit.edu.in` later is the same account, including for profiles written before that.

**Empty database — bootstrap it through the UI:**

1. Open `http://localhost:5173/register` and create your own account (this writes both the Auth user
   and the Firestore profile). New accounts come back `PENDING`.
2. You are redirected to **/join-department**, which now offers *"No department yet? → create the
   department"*. Open it and create the department — with an empty database that single action
   activates your account, makes you its **HOD**, and shows the invitation code.
3. Give that code to your faculty. They register, enter the code on /join-department, and you approve
   them on the same screen.

`python scripts/seed_demo.py --only-admin --password '...'` does steps 1–2 for you, prints the code, and
writes nothing else — no demo activities or requests land in a live database.

**Already have data, or the first login still fails** — settle it from the terminal instead. `--list` is
read-only; the write path does exactly what the API would have done:

```bash
cd backend
python scripts/grant_access.py --list
python scripts/grant_access.py --email hod@sbjit.edu.in --password 'Hiera@2026' --create-department
```

It creates the profile when it is missing and repairs it otherwise — password set, `status: ACTIVE`,
`role: HOD`, linked to a department (by id, invite code or a fragment of its name), and it claims an
unclaimed department's HOD seat. Re-running it changes nothing, so it is safe to try.

## Design System

All shared visual decisions live in `frontend/src/index.css`; page stylesheets consume the tokens
instead of re-declaring them.

| Token group | Values | Notes |
| --- | --- | --- |
| `--font-sans` | Manrope, Google Sans Flex, Saira, Roboto Slab | body copy |
| `--font-display` | Roboto Slab, Manrope | page titles, headings, hero numbers |
| `--font-label` | Saira, Manrope | kickers, labels, buttons, table heads |
| `--font-data` | Roboto Slab, Manrope | dates, counters, times (tabular numerals) |
| `--radius-xs … --radius-xl` | 4 / 6 / 8 / 10 / 12 px | controls |
| `--radius-card` / `--radius-hero` | 12 / 14 px | bento boxes and large panels — crisp corners, not squircles |
| `--hs-content-max` / `--hs-gutter` | 1440 px / `clamp(16px, 2.4vw, 34px)` | shared page shell |

Fonts are loaded once from Google Fonts in `frontend/index.html`
(`Google Sans Flex`, `Manrope`, `Roboto Slab`, `Saira`) and no stylesheet imports its own family.

**Page alignment:** every workflow route renders inside `.hs-page`, which applies the same gutter
and the same centred 1440px measure, so pages no longer sit a few pixels left or right of each
other; the auth screens and the department wizard use their own full-bleed shell but reuse the
`--hs-gutter` token, and `MainLayout` adds no horizontal padding of its own.
`html { scrollbar-gutter: stable }` keeps the measure stable when a page grows a scrollbar, and the
shell scrolls back to the top on navigation so rows never appear clipped.

## Tech Stack

- Frontend: React 19 (Vite 8, TypeScript), Tailwind CSS v4, FullCalendar, Recharts
- Backend: FastAPI (Python)
- Database: Firebase Firestore
- Authentication: Firebase Authentication (JWT in `localStorage` for the SPA)
- Scheduler: APScheduler

## Setup Instructions

### Firebase Setup

1. **Firebase Project Creation**: create a project in the [Firebase Console](https://console.firebase.google.com/).
2. **Firestore Setup**: Firestore Database → *Create database* (test mode while developing).
3. **Firebase Authentication**: Authentication → Sign-in method → enable *Email/Password*.
4. **Firebase Storage**: Storage → *Get started* with the default rules.
5. **Firebase Admin SDK**: Project settings → Service accounts → *Generate new private key*, and
   save the JSON as `backend/firebase-credentials.json` (never committed).

### Environment Variables

Backend — copy `backend/.env.example` to `backend/.env`:

```
FIREBASE_PROJECT_ID=your-firebase-project-id
FIREBASE_PRIVATE_KEY_PATH=firebase-credentials.json
SECRET_KEY=replace-with-a-long-random-string
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
GEMINI_API_KEY=
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

Frontend — optional, copy `frontend/.env.example` to `frontend/.env.local`. In development the Vite
server proxies `/api/v1` to `http://127.0.0.1:8000`, so nothing is required locally; set
`VITE_API_URL=https://your-api.example.com/api/v1` for production builds.

### Backend Setup

```bash
cd backend
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000   # demo mode works without credentials
python scripts/seed_demo.py --password Hiera@2026     # optional: a full department of data
```

The calendar page can also be driven end to end without a Firebase project: register a HOD account,
then create, drag, filter and export activities; the data simply does not survive a restart.

`FIREBASE_PRIVATE_KEY_PATH` may stay relative — it is resolved against the CWD first and then
against `backend/`, so a service-account file placed in `backend/` is found even if uvicorn is
started from the repository root (the module itself still has to be imported from `backend/`:
`python -m uvicorn app.main:app` from the root fails with *No module named 'app'*).

Interactive API docs: <http://127.0.0.1:8000/docs>. Without credentials the service still boots:
`app/database/memory.py` supplies a volatile Firestore double so registration, the calendar and the
approvals queue all work — check `GET /health`, which answers
`{"database": "memory (volatile demo data)"}` in that mode.

### Frontend Setup

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173
npm run build    # type-check + production bundle
npm run lint     # oxlint
npm run test:utils   # calendar date/ICS/CSV helpers (Node >= 22.18, no extra deps)
```

While the backend is not running, `/api/v1` requests fail and the pages switch to their bundled
preview data instead of showing an empty grid.

## API Surface (department modules)

| Method | Path | Notes |
| --- | --- | --- |
Collection endpoints answer on the bare path (`/api/v1/events`, not `/events/`), so a cross-origin
preflight is never bounced through a redirect.

| `GET` | `/api/v1/events` | supports `date_from`, `date_to`, `type`, `person` filters; seeds sample activities on an empty collection |
| `POST` | `/api/v1/events` | HOD/Admin only; dates normalised to `YYYY-MM-DD`, `notify_assignee` queues a reminder notification |
| `PUT` | `/api/v1/events/{id}` | HOD/Admin only; used by drag-and-drop rescheduling |
| `DELETE` | `/api/v1/events/{id}` | HOD/Admin only |
| `POST` | `/api/v1/events/{id}/remind` | re-send the reminder for one activity |
| `GET/POST` | `/api/v1/approvals` | queue listing + new request |
| `PUT` | `/api/v1/approvals/{id}` | edit note/status (only HOD/Admin may change the decision) |
| `PUT` | `/api/v1/approvals/{id}/approve` · `/reject` | HOD/Admin only, notifies the requester |
| `GET` | `/api/v1/ai/calendar-insights` | heuristic summary of the next 7 days; rewritten by Gemini when `GEMINI_API_KEY` is set |
| `GET` | `/api/v1/ai/approval-suggestions` | ranks the pending queue (priority + waiting time) and feeds the "Suggested order" strip |
| `POST` | `/api/v1/ai/notification-summary` | unread digest for the signed-in account |
| `POST` | `/api/v1/notifications` | accepts an optional `user_id` to target one account |

APScheduler runs a reminder sweep daily at 08:00 and every 6 hours: activities starting within two
days get a reminder for their owner, and activities whose date passed without completion are
escalated once. See `backend/app/scheduler/jobs.py`.

The whole surface is 18 route modules and 83 operations over 16 Firestore collections
(`GET /openapi.json` on a running instance is the authority).

## Verification

Two suites ship with the repository; neither needs a cloud project, an API key or a network.

```bash
cd backend && pip install -r requirements.txt && pip install pytest httpx
python -m pytest -q            # 82 cases over auth, RBAC, both approval queues, the risk
                               # model and the reminder jobs, on the in-memory double
cd ../frontend && npm install
npm run test:utils             # 9 cases over date parsing, overlap detection and ICS/CSV output
```

`backend/tests/` is written as characterisation tests: the expected values are read off `app/`, so a
change in behaviour fails with the name of the contract that moved. `docs/figures/` carries the paper's
figures (editable SVG + 300 dpi PNG) and `docs/tables/` its tables as CSV.

## Repository Layout

```
backend/
  app/api/v1/       18 route modules: auth (accounts + employees), events, tasks, approvals,
                    task-requests, comments, attachments, files, goals, notifications, ai,
                    analytics, reports, settings, search, departments, join, test
  app/auth/         bcrypt hashing, JWT issue/verify, case-insensitive email lookup, role gates
  app/scheduler/    APScheduler jobs (reminder window, idempotence markers)
  app/database/     Firestore bootstrap + the in-memory demo double
  app/schemas/      Pydantic models, including the activity/approval contracts
  app/utils/        shared helpers (dates, logging)
  tests/            pytest suite (82 cases) — runs on the in-memory double
frontend/
  src/api/          typed fetch client, one module per resource
  src/components/   Chatbot, FileUpload, NotificationCenter, ProtectedRoute, StatCard,
                    common/ (StatCard) and tasks/ (HOD + teacher dashboards, views,
                    comments, attachments, detail modal)
  src/layouts/      MainLayout, Navbar, Sidebar
  src/pages/        routes; CalendarPage + calendarData + Approvals own the workflow UI
  src/utils/        calendar formatting (date coercion, overlap), ICS/CSV export
tests/              node:test suite for the calendar utilities (npm run test:utils)
  src/index.css     design tokens, component primitives, FullCalendar overrides
```

## Deployment

- **Backend**: Cloud Run, Render or any `uvicorn` host; mount the service account JSON via a secret
  and set `FIREBASE_PRIVATE_KEY_PATH` to its path.
- **Frontend**: Firebase Hosting, Vercel or Netlify — build with `VITE_API_URL` pointing at the API.

## Licence

Private academic project.
