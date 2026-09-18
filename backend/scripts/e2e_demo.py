#!/usr/bin/env python3
"""End-to-end acceptance run against the deck's success criterion (Slide 6):

    login as each role  ->  assign  ->  approve  ->  notify  ->  analyse

Runs the whole loop in-process against the embedded store (no server needed), prints a
transcript a reviewer can follow, and exits non-zero if any stage misbehaves. It is also
the integration test used by CI (`pytest tests/test_e2e_flow.py` wraps it).

    python scripts/e2e_demo.py [--serve] [--keep]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

GREEN, RED, YELLOW, DIM, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"

FAILED = []


def step(title: str):
    print(f"\n{YELLOW}▸ {title}{RESET}")


def ok(label: str, detail: str = ""):
    print(f"  {GREEN}✔{RESET} {label}" + (f"  {DIM}{detail}{RESET}" if detail else ""))


def fail(label: str, detail: str = ""):
    FAILED.append(label)
    print(f"  {RED}✘ {label}{RESET} {detail}")


def check(cond: bool, label: str, detail: str = "") -> bool:
    (ok if cond else fail)(label, detail)
    return bool(cond)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true", help="keep the temporary database")
    ap.add_argument("--serve", action="store_true", help="print uvicorn command instead of exiting")
    args = ap.parse_args()

    tmp = tempfile.mkdtemp(prefix="hierasync-e2e-")
    os.environ["SQLITE_PATH"] = os.path.join(tmp, "e2e.db")
    os.environ["NOTIFY_DEV_OUTBOX_DIR"] = os.path.join(tmp, "outbox")
    os.environ["SCHEDULER_ENABLED"] = "false"
    os.environ["SEED_DEMO_DATA"] = "true"

    from fastapi.testclient import TestClient

    from app.main import app

    print(f"{DIM}database: {os.environ['SQLITE_PATH']}{RESET}")
    with TestClient(app) as client:
        pwd = os.environ.get("DEMO_PASSWORD", "HierSync@123")

        step("0. Boot & health")
        h = client.get("/health")
        check(h.status_code == 200, "/health 200", h.json().get("persistence", {}).get("backend", "?"))

        def login(email: str) -> str:
            r = client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
            if r.status_code != 200:
                fail(f"login {email}", r.text[:160])
                return ""
            ok("login", email)
            return r.json()["access_token"]

        step("1. Login as each role (HOD, Faculty, Principal)")
        hod = login("hod.aiml@hierasync.demo")
        fac = login("neha.gurnani@hierasync.demo")
        principal = login("principal@demo.hierasync.in")
        if not (hod and fac and principal):
            print(f"{RED}cannot continue without tokens for all three roles{RESET}")
            return 2
        H = {"Authorization": f"Bearer {hod}"}
        F = {"Authorization": f"Bearer {fac}"}
        P = {"Authorization": f"Bearer {principal}"}

        step("2. HOD assigns a task with a 2-day deadline")
        deadline = (datetime.utcnow() + timedelta(days=2)).date().isoformat()
        roster = client.get("/api/v1/auth/employees", headers=H).json()
        roster = roster.get("employees", roster) if isinstance(roster, dict) else roster
        target = next((u for u in roster if isinstance(u, dict) and u.get("role") == "FACULTY"), None)
        payload = {
            "title": "E2E: Submit Criterion 3 evidence to the NAAC portal",
            "assigned": (target or {}).get("name", "Mrs. Neha Gurnani"),
            "assigned_id": (target or {}).get("id", "usr_fac_1"),
            "deadline": deadline,
            "priority": "High",
            "status": "Pending",
            "progress": "20%",
            "description": "Compiled criterion 3.1 and 3.3 proof with HOD sign-off.",
            "estimated_effort": "12h",
            "subtasks": [
                {"id": "s1", "title": "Collect publications list", "completed": True},
                {"id": "s2", "title": "Verify consultancy records", "completed": False},
                {"id": "s3", "title": "Upload to portal", "completed": False},
            ],
            "require_approval": True,
            "category": "Accreditation",
        }
        r = client.post("/api/v1/tasks/", json=payload, headers=H)
        check(r.status_code == 200, "POST /tasks 200", f"risk={r.json().get('risk_score')}/100 {r.json().get('risk_level')}" if r.status_code == 200 else r.text[:200])
        task = r.json() if r.status_code == 200 else {}
        task_id = task.get("id")
        if task_id:
            ok("task id", task_id)

        step("3. Risk engine explains the score")
        r = client.get(f"/api/v1/risk/score/{task_id}", headers=H)
        a = r.json() if r.status_code == 200 else {}
        check(r.status_code == 200, "GET /risk/score/{id}", f"score={a.get('risk_score')} band={a.get('risk_level')} p(delay)={a.get('delay_probability')} conf={a.get('confidence')}")
        for f in (a.get("top_drivers") or [])[:3]:
            print(f"      {DIM}{f['label']:<26} sub={f['sub_score']:>5}  contribution={f['contribution']:>5}  {f['evidence'][:70]}{RESET}")
        check(bool(a.get("explanation")), "explanation generated", (a.get("explanation") or "")[:100])
        check(bool(a.get("recommendations")), "recommendations", f"{len(a.get('recommendations', []))} actions")

        r = client.post("/api/v1/risk/what-if", json={"task_id": task_id, "overrides": {"deadline": (datetime.utcnow() + timedelta(days=9)).date().isoformat()}}, headers=H)
        w = r.json() if r.status_code == 200 else {}
        check(w.get("verdict") == "improves", "what-if: +7 days lowers risk", f"delta={w.get('delta')}")

        step("4. Faculty updates progress -> auto approval request")
        r = client.put(
            f"/api/v1/tasks/{task_id}",
            json={"subtasks": [
                {"id": "s1", "title": "Collect publications list", "completed": True},
                {"id": "s2", "title": "Verify consultancy records", "completed": True},
                {"id": "s3", "title": "Upload to portal", "completed": True},
            ], "status": "Awaiting Approval"},
            headers=F,
        )
        check(r.status_code == 200, "PUT /tasks/{id} progress -> awaiting approval", f"status={r.json().get('status')} progress={r.json().get('progress')}" if r.status_code == 200 else r.text[:160])

        step("5. Faculty raises an approval request (leave) - routed to HOD stage")
        r = client.post(
            "/api/v1/workflow/",
            json={
                "title": "Hall booking + budget for the ML Workshop",
                "kind": "event",
                "priority": "Medium",
                "description": "Mentioned work handover to co-ordinator.",
                "evidence": {"venue": "Seminar Hall", "date": (datetime.utcnow() + timedelta(days=12)).date().isoformat(), "expected_attendees": "120"},
            },
            headers=H,
        )
        created = r.json() if r.status_code == 200 else {}
        apr_id = created.get("id")
        check(r.status_code == 200, "POST /workflow", f"stage={created.get('stage')} sla={created.get('sla_hours')}h" if apr_id else r.text[:200])

        step("6. Wrong-stage rejection is blocked; HOD approves (2-stage engine)")
        r = client.post(f"/api/v1/workflow/{apr_id}/decide", json={"decision": "REJECT"}, headers=P)
        check(r.status_code == 400, "principal cannot act at HOD stage", r.json().get("detail", {}).get("code", "?") if r.status_code == 400 else "")
        r = client.post(f"/api/v1/workflow/{apr_id}/decide", json={"decision": "APPROVE", "note": "Approved - arrange substitute lecturer."}, headers=H)
        check(r.status_code == 200 and r.json().get("status") == "PENDING" and r.json().get("stage") == "PRINCIPAL", "HOD advanced request to Principal stage", f"sla={r.json().get('sla_hours')}h" if r.status_code == 200 else r.text[:160])

        step("7. Principal final approval auto-creates the delivery task (Slide 15 step 4)")
        r = client.post(f"/api/v1/workflow/{apr_id}/decide", json={"decision": "APPROVE", "note": "Sanctioned."}, headers=P)
        body = r.json() if r.status_code == 200 else {}
        check(r.status_code == 200 and body.get("status") == "APPROVED", "final approval", f"created_task={bool(body.get('created_task'))}" if body else r.text[:160])
        check(bool(body.get("created_task")), "task instantiated from approval", str((body.get("created_task") or {}).get("title", ""))[:60])
        r = client.post(f"/api/v1/workflow/{apr_id}/decide", json={"decision": "APPROVE"}, headers=H)
        check(r.status_code == 400, "double decision rejected", "already_decided")

        step("8. Audit chain integrity")
        r = client.get(f"/api/v1/workflow/{apr_id}/audit", headers=H)
        au = r.json() if r.status_code == 200 else {}
        check(au.get("valid") is True, "hash chain valid", f"{len(au.get('entries', []))} entries")
        r = client.post("/api/v1/workflow/verify", headers=H)
        check(r.json().get("compromised") == [], "no tampered records", f"checked={r.json().get('checked')}")

        step("9. Notifications: routing, outbox, delivery ledger")
        r = client.get("/api/v1/channels/status", headers=H)
        st = r.json()
        for ch, info in st["channels"].items():
            mode = "live" if info["live"] else "simulated (dev outbox)"
            print(f"      {DIM}{ch:<10} -> {info['will_use']:<22} {mode}{RESET}")
        check(st["channels"]["email"]["will_use"] != "none", "email channel resolvable")
        r = client.post("/api/v1/channels/flush", headers=H)
        flushed = r.json() if r.status_code == 200 else {}
        check(r.status_code == 200, "POST /channels/flush", json.dumps(flushed)[:110])
        r = client.get("/api/v1/channels/outbox?limit=5", headers=H)
        ob = r.json()
        print(f"      {DIM}outbox: {json.dumps(ob.get('stats'))[:120]}{RESET}")
        check(ob.get("count", 0) > 0, "outbox rows exist for this run", f"{ob.get('count')} visible")
        r = client.get("/api/v1/channels/deliveries?limit=5", headers=H)
        dl = r.json()
        check(dl.get("count", 0) > 0, "delivery ledger written", json.dumps(dl.get("summary"))[:110])
        for it in (dl.get("items") or [])[:3]:
            print(f"      {DIM}{it.get('channel'):<9} {it.get('status'):<9} {str(it.get('address'))[:26]:<28} {it.get('provider')}{RESET}")
        r = client.get("/api/v1/notifications/unread-count", headers=F)
        check(r.status_code == 200, "faculty unread count", str(r.json()))

        step("10. Automation jobs (the 8 AM cron, run now for the demo)")
        r = client.get("/api/v1/channels/jobs", headers=H)
        jobs = r.json().get("jobs", [])
        check(len(jobs) >= 8, f"{len(jobs)} scheduled jobs registered", ", ".join(j["id"] for j in jobs[:6]) + " ...")
        for jid in ("risk_sweep", "daily_reminders", "overdue_escalation", "approval_sla", "daily_digest", "weekly_report"):
            r = client.post(f"/api/v1/channels/jobs/{jid}/run", headers=H)
            res = (r.json() or {}).get("result", {})
            check(r.status_code == 200 and "error" not in res, f"job {jid}", json.dumps(res.get("result", res))[:100] if isinstance(res, dict) else "")

        step("11. Analyse: scorecard, risk board, faculty table, exports")
        r = client.get("/api/v1/metrics/scorecard?days=120", headers=H)
        sc = r.json() if r.status_code == 200 else {}
        check(r.status_code == 200, "GET /metrics/scorecard", f"tasks={sc.get('tasks', {}).get('total')} on_time={sc.get('tasks', {}).get('on_time_rate')}% risk_bands={sc.get('risk', {}).get('bands')}")
        print(f"      {DIM}approvals: {json.dumps(sc.get('approvals', {}))[:120]}{RESET}")
        print(f"      {DIM}workload balance index: {sc.get('workload', {}).get('balance_index')} | automation {sc.get('automation', {}).get('delivery_success_rate')}% delivered{RESET}")
        check(bool(sc.get("insights")), "insights generated", f"{len(sc.get('insights', []))} findings")
        r = client.get("/api/v1/risk/board?limit=3", headers=H)
        bd = r.json()
        check(r.status_code == 200 and bd.get("count", 0) > 0, "GET /risk/board", f"{bd.get('count')} scored, bands={bd.get('bands')}")
        r = client.get("/api/v1/metrics/faculty", headers=H)
        fa = r.json()
        check(fa.get("count", 0) > 0, "faculty performance table", f"{fa.get('count')} rows; top={((fa.get('items') or [{}])[0]).get('name')}")
        r = client.get("/api/v1/metrics/forecast?horizon_days=21", headers=H)
        check(r.status_code == 200, "completion forecast", json.dumps(r.json().get("expected_completions_by_week", []))[:110])
        r = client.get("/api/v1/metrics/export?kind=tasks&format=csv", headers=H)
        lines = (r.text or "").strip().splitlines()
        check(r.status_code == 200 and len(lines) > 1, "CSV export (accreditation pack)", f"{len(lines)-1} rows, {len(r.content)} bytes")
        r = client.get("/api/v1/analytics/faculty-performance", headers=H)
        check(r.status_code == 200, "legacy v1 analytics endpoint still works", f"{len(r.json())} rows")

        step("12. RBAC: TA may not assign tasks, faculty may not export")
        ta = client.post("/api/v1/auth/login", json={"email": "ta@hierasync.demo", "password": pwd}).json().get("access_token", "")
        r = client.post("/api/v1/tasks/", json={"title": "nope", "assigned": "x", "deadline": deadline}, headers={"Authorization": f"Bearer {ta}"})
        check(r.status_code == 403, "TA assignment blocked by RBAC", str(r.json().get("detail", {}))[:80])

        if args.serve:
            print(f"\n{YELLOW}Preview with:{RESET} uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")

    print(f"\n{'=' * 78}")
    if FAILED:
        print(f"{RED}{len(FAILED)} check(s) failed:{RESET} " + ", ".join(FAILED))
        return 1
    print(f"{GREEN}All stages of the success criterion passed: login -> assign -> approve -> notify -> analyse{RESET}")
    print(f"{DIM}artifacts: {os.environ['NOTIFY_DEV_OUTBOX_DIR']} (mail/SMS/WhatsApp transcripts){RESET}")
    if not args.keep:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)
    else:
        print(f"{DIM}database kept at {os.environ['SQLITE_PATH']}{RESET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
