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
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Interactive API docs: <http://127.0.0.1:8000/docs>. Without credentials the service still boots
and serves the API from in-memory sample data (`FIREBASE_AVAILABLE=false`).

### Frontend Setup

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173
npm run build    # type-check + production bundle
```

## API Surface (department modules)

| Method | Path | Notes |
| --- | --- | --- |
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

## Repository Layout

```
backend/
  app/api/v1/       route handlers (auth, users, events, tasks, approvals, ai, …)
  app/schemas/      Pydantic models, including the activity/approval contracts
  app/scheduler/    background reminder jobs
  app/utils/        shared helpers (dates, logging)
frontend/
  src/api/          typed fetch client, one module per resource
  src/components/   shared widgets (FullCalendarEventModal, tasks/, …)
  src/layouts/      MainLayout, Navbar, Sidebar
  src/pages/        routes; CalendarPage + calendarData + Approvals own the workflow UI
  src/utils/        calendar formatting, ICS/CSV export
  src/index.css     design tokens, component primitives, FullCalendar overrides
```

## Deployment

- **Backend**: Cloud Run, Render or any `uvicorn` host; mount the service account JSON via a secret
  and set `FIREBASE_PRIVATE_KEY_PATH` to its path.
- **Frontend**: Firebase Hosting, Vercel or Netlify — build with `VITE_API_URL` pointing at the API.

## Licence

Private academic project.
