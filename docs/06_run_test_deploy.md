# HieraSync AI — Run, Test, Deploy

Everything below is verified against this commit. `backend/.venv` already has the dependencies.

## 1. 60-second start (no cloud account needed)

```bash
cd backend
source .venv/bin/activate          # or: python -m venv .venv && pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# → http://localhost:8000/           JSON pointer to the API docs
# → http://localhost:8000/docs       OpenAPI (22 routers)
# → http://localhost:8000/health     backend: sqlite | firestore, scheduler: ok
```

`STATIC_DIR` is read relative to the process cwd, so always start uvicorn **from `backend/`** (`.env` is read from the cwd too). With `frontend/dist` present and `STATIC_DIR=../frontend/dist`, `http://localhost:8000/` serves the React app itself; otherwise the SPA runs on `:5173` via `npm run dev`.

First boot seeds a deterministic demo corpus (`SEED_DEMO_DATA=true`, 2 departments, 18 users covering **all 10 roles**, 28 tasks across every risk band, 8 approvals at different stages, events, goals, preferences) and auto-calibrates risk weights if none exist.

```bash
cd frontend && npm install && npm run dev     # http://localhost:5173 (proxies /api -> :8000)
```

Served by the same origin (the SPA is picked up from `STATIC_DIR`): `/dashboard`, `/tasks`, `/calendar`,
`/approvals`, **`/approvals/desk`** (staged workflow), **`/risk`** (risk engine), **`/analytics`** (scorecard + exports),
**`/automation`** (channels, jobs, outbox), `/ai`, `/goals`, `/notifications`, `/reports`, `/employees`, `/settings`.

## 2. Demo logins (password `HierSync@123`, override with `DEMO_PASSWORD`)

| Role | E-mail | Try this |
|---|---|---|
| Principal | `principal@demo.hierasync.in` | approve at stage 2, institute scorecard, calibrate weights |
| HOD | `hod.aiml@hierasync.demo` | assign a task, approve stage 1, department CSV export |
| Faculty | `neha.gurnani@hierasync.demo` | raise a leave request, update subtasks, check own risk (she sits in **dept_it**) |
| HOD (Information Technology) | `hod.it@hierasync.demo` | the second department: its own stage-1 queue (code **IT**) |
| Teacher | `teacher@hierasync.demo` | the 10th role — subtasks only, self-scope analytics |
| TA / Lab Asst / Staff / Student Rep / Student | `ta@…`, `lab.assistant@…`, `office.staff@…`, `student.rep@…`, `student@…` | self-task and event-only scopes |

## 3. Verification suite

```bash
cd backend
python scripts/e2e_demo.py                       # deck success criterion, 13 checks, exit code = result
python -m pytest -q                               # 48 unit/API tests
python -m app.engine.benchmarks --tasks 500       # model comparison (docs/02)
python scripts/check_store_parity.py              # embedded store vs Firestore query semantics
```

`TestUiSurfaces` covers exactly what the four v2 pages call — the approval queue/funnel/policies, delegation rights
transfer, the scorecard formulas, the forecast arithmetic (`likely_to_miss + within_horizon == open_tasks`), snapshot
capability gating, and the six export datasets including the 403 for a role without `export_reports`.

`e2e_demo.py` prints the whole loop and asserts it: RBAC 403 for a non-privileged export, `risk_score 23.6 LOW` on a fresh task, factors with evidence, what-if delta, HOD→Principal staged approval, auto-created task, notification fan-out (dev outbox: 7 e-mail / 6 SMS / 3 WhatsApp), queue flush, every cron job run on demand, audit-chain verification, analytics scorecard with published formulas, and a 23-row CSV export.

## 4. Configuration

Copy `backend/.env.example` → `backend/.env`. Frequently changed keys:

| Key | Default | Meaning |
|---|---|---|
| `DATABASE_BACKEND` | `auto` | `auto` → Firestore if credentials exist, else the embedded store; force `sqlite`/`firestore` |
| `FIRESTORE_CREDENTIALS_JSON` / `_PATH`, `FIRESTORE_PROJECT_ID` | – | Admin SDK credentials (path preferred over inline JSON) |
| `SECRET_KEY` | dev value | JWT signing key — **change in production** (legacy v1 name, still canonical) |
| `CORS_ORIGINS` | localhost:5173/3000/4173 | comma list |
| `SEED_DEMO_DATA` | `true` | demo corpus on an empty store |
| `STATIC_DIR` | `""` (off) | set `../frontend/dist` to serve the built SPA from FastAPI on one port; `.env.example` already ships that value |
| `SCHEDULER_ENABLED`, `NOTIFY_TIMEZONE` | true, Asia/Kolkata | automation master switch + the clock "8 AM" is measured against |
| `DEADLINE_REMINDER_TIMES` | `08:00` | the deck's **8 AM** reminder; accepts several times if they share a minute (`08:00,17:00`) |
| `WEEKLY_REPORT_TIME` | `Mon:07:00` | auto-generated report (day:time) |
| `OVERDUE_ESCALATION_TIME`, `RETENTION_PURGE_TIME` | `09:00`, `02:00` | escalation ladder, purge (both campus-local) |
| `NOTIFY_DEV_OUTBOX_DIR` | `var/outbox` | where simulated deliveries are written as dated files under `{email,sms,whatsapp}/`; there is **no enable flag** — a provider goes live the moment its credentials exist |
| `DEFAULT_QUIET_HOURS` | `22:30-07:00` | window in which non-critical e-mail/SMS/WhatsApp are deferred (per-user override in preferences) |
| `OUTBOX_POLL_SECONDS`, `OUTBOX_BATCH_SIZE` | 60, 50 | worker cadence and per-pass batch |
| `NOTIFY_MAX_ATTEMPTS`, `NOTIFY_RETRY_BASE_SECONDS` | 4, 60 | retry ladder `60s·2^n` + jitter, capped at 1 h |
| `NOTIFY_DEDUPE_MINUTES`, `NOTIFY_RATE_LIMIT_PER_MINUTE` | 360, 40 | repeat suppression and provider throttle |
| `SMTP_HOST/PORT/USERNAME/PASSWORD/FROM/USE_TLS` | – | Gmail/Outlook/SES relay (app password) |
| `TWILIO_ACCOUNT_SID/TOKEN/FROM` | – | SMS (sandbox number works) |
| `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_TEMPLATE_*` | – | Meta WhatsApp Cloud API |

Full annotated list: `backend/.env.example`. Anything set wins over `.env`, which wins over defaults (`app/config/settings.py`).

### Going live, channel by channel

1. **E-mail (10 min).** `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, `SMTP_SECURITY=starttls`, `SMTP_USERNAME=you@gmail.com`, `SMTP_PASSWORD=<16-char app password>` (Google requires app passwords with 2FA; "less secure apps" is gone), `MAIL_FROM=you@gmail.com`, `MAIL_FROM_NAME="HieraSync AI"`, `MAIL_SUBJECT_PREFIX=[HieraSync]`. Port 465 hosts use `SMTP_SECURITY=ssl`. Verify: `curl -X POST localhost:8000/api/v1/channels/test -H "Authorization: Bearer <jwt>" -H 'Content-Type: application/json' -d '{"channels":["email"]}'`.
2. **SMS.** Twilio trial: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER=+1…` (trial sandbox auto-targets the verified number). Recipients need a `phone` in E.164 — set in the profile or `PUT /api/v1/channels/preferences`.
3. **WhatsApp.** Meta WhatsApp Cloud API: app → WhatsApp product → get `PHONE_NUMBER_ID` + permanent token; set and **submit the HieraSync message templates for approval**. Business-initiated messages must use an approved template, so `WHATSAPP_TEMPLATES` (a JSON map of message kind → template name, e.g. `{"deadline_risk":"risk_alert","default":"generic_alert"}`) has to reference templates Meta has approved before the provider is reported live. `WHATSAPP_PROVIDER=twilio` is the alternative if you already have a Twilio WhatsApp sandbox. Recipients must set `whatsapp_opt_in=true`.
4. **Firestore.** `DATABASE_BACKEND=firestore` + credentials → same code, no migration script needed (`scripts/export_sqlite_to_firestore.py` is optional for an existing demo corpus).

## 5. Docker

```bash
cp backend/.env.example backend/.env    # credential-free by default: unconfigured channels land in the dev outbox
docker compose up --build               # :8000 API+SPA, :8080 preview of the notification outbox
```

The `outbox-preview` service is a static file server over the mounted `backend/var/outbox` — open `http://localhost:8080` during a defence demo to show real rendered messages. The whole `backend/var` tree is a **named volume** (`hierasync-var`) so a container restart cannot orphan queued messages or the embedded store; `web` (profile `prod`) serves the built SPA through nginx with `/api` proxied, and `dev` (profile `dev`) runs Vite with HMR on :5173.

## 6. Test / production notes

* `pytest` runs hermetically: `SQLITE_PATH` under `tmp_path`, `NOTIFY_MAX_ATTEMPTS=2`, scheduler off, seeded store. No network, no credentials.
* Keep `firebase-admin` installed even in SQLite mode (the driver's import guard expects it present in production images; the shim degrades gracefully).
* Uvicorn: `--workers 1` per instance (in-memory rate limiting + SQLite); scale by adding instances behind a load balancer with `DATABASE_BACKEND=firestore`.
* Rollback safety: v1 collections/fields are untouched; v2 only **adds** documents and fields (`docs/04 §2`), so an older frontend still reads the store.

## 7. Troubleshooting

| Symptom | Cause → fix |
|---|---|
| App dies at boot with `DefaultCredentialsError` | Firestore credentials set but invalid → `DATABASE_BACKEND=sqlite` or fix the path |
| `/channels/email` shows `enabled: false` | dev outbox active (by design) → add SMTP creds or accept simulated delivery |
| WhatsApp never sends | no approved template / `whatsapp_opt_in=false` → check `GET /api/v1/channels/status` `reason` and `last_error` in outbox rows |
| No reminders at 08:00 | `SCHEDULER_ENABLED=false`, or `NOTIFY_TIMEZONE` mismatch, or the dedupe window suppressed a repeat (same title+body within 360 min) |
| `403 "requires capability 'x'"` | correct RBAC behaviour → see `docs/05 §4` / `GET /api/v1/workflow/rbac` |
| "404 document not found" in logs on read | benign: `DocumentSnapshot._get` returns `None` for missing docs |
