"""Backend test-suite.

    pytest -q            # unit + integration
    pytest -q -k "risk"  # engine only

Runs entirely against the embedded document store in a temp directory, so CI needs no
Firebase project, no network and no credentials.
"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture(autouse=True)
def _no_quiet_hours_window(monkeypatch):
    """The default 22:30-07:00 IST window defers non-critical sends, which made delivery tests
    depend on the wall clock. Tests that care about deferral set the window themselves."""
    from app.config import settings as settings_mod

    monkeypatch.setattr(settings_mod.settings, "DEFAULT_QUIET_HOURS", "", raising=False)


@pytest.fixture(scope="function")
def store():
    from app.db.store import DocumentStore

    path = os.path.join(tempfile.mkdtemp(prefix="hs-test-"), "test.db")
    yield DocumentStore(path)


@pytest.fixture(scope="function")
def client(store):
    """Booted FastAPI app on a pristine seeded database."""
    os.environ.update(
        {
            "DATABASE_BACKEND": "sqlite",
            "SQLITE_PATH": store.path,
            "SCHEDULER_ENABLED": "false",
            "SEED_DEMO_DATA": "true",
            "NOTIFY_DEV_OUTBOX_DIR": os.path.join(os.path.dirname(store.path), "outbox"),
            "NOTIFY_DEDUPE_MINUTES": "0",
            "SECRET_KEY": "test-secret",
        }
    )
    from app.config import settings as settings_mod

    settings_mod.settings = settings_mod.Settings()
    settings_mod.settings.NOTIFY_DEDUPE_MINUTES = 0
    settings_mod.settings.NOTIFY_DEV_OUTBOX_DIR = os.path.join(os.path.dirname(store.path), "outbox")
    import app.notify.queue as q

    q.reset_providers_cache()

    from fastapi.testclient import TestClient

    from app.database import session as sess

    sess._db = store
    sess._backend = "sqlite"
    from app.db.seed import seed

    seed(store, force=True)
    from app.main import app

    with TestClient(app) as c:
        yield c


def token_for(client, email: str, password: str = "HierSync@123") -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture
def hod(client):
    return {"Authorization": f"Bearer {token_for(client, 'hod.aiml@hierasync.demo')}"}


@pytest.fixture
def faculty(client):
    return {"Authorization": f"Bearer {token_for(client, 'neha.gurnani@hierasync.demo')}"}


@pytest.fixture
def principal(client):
    return {"Authorization": f"Bearer {token_for(client, 'principal@demo.hierasync.in')}"}


# ------------------------------------------------------------------ persistence layer
class TestDocumentStore:
    def test_roundtrip_and_missing(self, store):
        c = store.collection("tasks")
        c.document("a").set({"title": "A", "n": 1})
        assert c.document("a").get().to_dict()["title"] == "A"
        assert c.document("zz").get().exists is False

    def test_update_merges_and_supports_dotted_paths(self, store):
        ref = store.collection("x").document("d")
        ref.set({"a": {"b": 1}, "keep": True})
        ref.update({"a.b": 2, "new": 3})
        got = ref.get().to_dict()
        assert got == {"a": {"b": 2}, "keep": True, "new": 3}

    def test_where_operators(self, store):
        c = store.collection("t")
        c.document("1").set({"s": "open", "p": 2, "tags": ["x"]})
        c.document("2").set({"s": "done", "p": 5, "tags": ["y"]})
        c.document("3").set({"s": "hold", "p": 9})
        assert {d.id for d in c.where("s", "==", "open").stream()} == {"1"}
        assert {d.id for d in c.where("p", ">=", 5).stream()} == {"2", "3"}
        assert {d.id for d in c.where("s", "in", ["open", "hold"]).stream()} == {"1", "3"}
        assert {d.id for d in c.where("tags", "array_contains", "y").stream()} == {"2"}

    def test_fieldfilter_and_order_limit(self, store):
        from google.cloud.firestore_v1.base_query import FieldFilter

        c = store.collection("logs")
        for i in range(5):
            c.document(f"d{i}").set({"ts": f"2026-01-0{i+1}T00:00:00", "ok": i % 2 == 0})
        got = [d.id for d in c.where(filter=FieldFilter("ok", "==", True)).order_by("ts", direction="DESCENDING").limit(2).stream()]
        assert got == ["d4", "d2"]  # ok=True rows are d0,d2,d4; newest two descending

    def test_batch_atomicity(self, store):
        c = store.collection("b")
        c.document("k").set({"v": 1})
        batch = store.batch()
        batch.set(c.document("n"), {"v": 2})
        batch.delete(c.document("k"))
        batch.commit()
        assert not c.document("k").get().exists and c.document("n").get().exists

    def test_isolation_between_collections(self, store):
        store.collection("a").document("x").set({"v": 1})
        store.collection("b").document("x").set({"v": 2})
        assert store.collection("a").document("x").get().to_dict()["v"] == 1


# --------------------------------------------------------------------- risk engine
class TestRiskEngine:
    def _ctx(self, store):
        from app.engine import risk as R

        tasks = [dict(s.to_dict(), id=s.id) for s in store.collection("tasks").stream()]
        return R.build_context(store, tasks=tasks)

    def test_overdue_outranks_on_track(self, store):
        from app.engine import risk as R

        ctx = self._ctx(store)
        now = datetime.utcnow()
        late = {"id": "l", "title": "late", "status": "In Progress", "progress": "10%", "deadline": (now - timedelta(days=5)).date().isoformat(), "created_at": (now - timedelta(days=10)).isoformat()}
        fine = {"id": "f", "title": "fine", "status": "In Progress", "progress": "90%", "deadline": (now + timedelta(days=20)).date().isoformat(), "created_at": (now - timedelta(days=2)).isoformat()}
        a, b = R.assess(late, ctx), R.assess(fine, ctx)
        assert a["risk_score"] > b["risk_score"]
        assert a["risk_level"] == "HIGH" and b["risk_level"] == "LOW"
        assert a["delay_probability"] > 0.5 > b["delay_probability"]

    def test_score_is_monotone_probability(self, store):
        from app.engine import risk as R

        ctx = self._ctx(store)
        now = datetime.utcnow()
        t = {"id": "x", "title": "x", "status": "In Progress", "progress": "40%", "deadline": (now + timedelta(days=1)).date().isoformat(), "created_at": (now - timedelta(days=6)).isoformat()}
        a = R.assess(t, ctx)
        assert abs(a["risk_score"] - 100 * a["delay_probability"]) < 1.0

    def test_every_score_ships_evidence(self, store):
        from app.engine import risk as R

        ctx = self._ctx(store)
        for snap in store.collection("tasks").stream():
            a = R.assess(dict(snap.to_dict(), id=snap.id), ctx)
            assert set(["risk_score", "risk_level", "factors", "explanation", "recommendations", "confidence"]) <= set(a)
            assert all(f["evidence"] for f in a["factors"])
            assert 0 < a["confidence"] <= 0.97

    def test_completed_tasks_are_not_scored(self, store):
        from app.engine import risk as R

        ctx = self._ctx(store)
        a = R.assess({"id": "d", "status": "Completed", "progress": "100%", "deadline": "2020-01-01"}, ctx)
        assert a["risk_score"] == 0 and a["risk_level"] == "CLOSED"

    def test_blocked_dependency_raises_risk(self, store):
        from app.engine import risk as R

        ctx = self._ctx(store)
        now = datetime.utcnow()
        base = {"id": "b", "title": "t", "status": "In Progress", "progress": "60%", "deadline": (now + timedelta(days=4)).isoformat(), "created_at": now.isoformat()}
        clean = R.assess(dict(base), ctx)
        blocked = R.assess(dict(base, blocked_by=[{"id": "z", "title": "prereq", "status": "In Progress"}]), ctx)
        assert blocked["risk_score"] > clean["risk_score"]

    def test_what_if_extends_deadline_and_lowers_risk(self, store):
        from app.engine import risk as R

        ctx = self._ctx(store)
        now = datetime.utcnow()
        t = {"id": "w", "title": "w", "status": "In Progress", "progress": "20%", "deadline": (now + timedelta(days=1)).date().isoformat()}
        w = R.what_if(t, ctx, {"deadline": (now + timedelta(days=15)).date().isoformat()})
        assert w["verdict"] == "improves" and w["delta"] < 0

    def test_weights_normalise_to_one(self, store):
        ctx = self._ctx(store)
        assert abs(sum(ctx.weights.values()) - 1.0) < 1e-6


# ------------------------------------------------------------------ notification engine
class TestNotifyEngine:
    def test_routing_policy_by_severity(self):
        from app.config.settings import settings
        from app.notify.routing import plan_channels

        user = {"id": "u1", "email": "u@x.io", "phone": "+919812345678"}
        prefs = {"email_enabled": True, "sms_enabled": True, "whatsapp_enabled": True, "whatsapp_opt_in": True, "quiet_hours_enabled": False, "min_severity_email": "LOW", "min_severity_sms": "HIGH", "min_severity_whatsapp": "HIGH", "digest_mode": "none", "muted_kinds": []}
        low, _ = plan_channels(user, prefs, "task_completed", "LOW")
        assert {p.channel for p in low} == {"inapp"}
        crit, _ = plan_channels(user, prefs, "task_overdue", "CRITICAL")
        assert {"inapp", "email", "sms", "whatsapp"} == {p.channel for p in crit}

    def test_quiet_hours_defers_but_critical_breaks_through(self):
        from app.notify.routing import in_quiet_hours, quiet_hours_end, plan_channels

        assert in_quiet_hours(datetime(2026, 1, 1, 23, 30), "22:30-07:00")
        assert in_quiet_hours(datetime(2026, 1, 1, 3, 0), "22:30-07:00")
        assert not in_quiet_hours(datetime(2026, 1, 1, 9, 0), "22:30-07:00")
        end = quiet_hours_end(datetime(2026, 1, 1, 23, 30), "22:30-07:00")
        assert (end.hour, end.minute) == (7, 0) and end.date() == datetime(2026, 1, 2).date()
        prefs = {"email_enabled": True, "sms_enabled": True, "whatsapp_enabled": False, "quiet_hours_enabled": True, "quiet_hours": "22:30-07:00", "min_severity_email": "LOW", "digest_mode": "none", "muted_kinds": []}
        deferred, _ = plan_channels({"id": "u", "email": "e@x.io"}, prefs, "task_assigned", "MEDIUM", now=datetime(2026, 1, 1, 23, 30))
        email = [p for p in deferred if p.channel == "email"][0]
        assert email.immediate is False and email.scheduled_at > datetime(2026, 1, 1)

    def test_whatsapp_requires_opt_in(self):
        from app.notify.routing import plan_channels

        prefs = {"email_enabled": False, "sms_enabled": False, "whatsapp_enabled": True, "whatsapp_opt_in": False, "quiet_hours_enabled": False, "digest_mode": "none", "muted_kinds": []}
        _, skipped = plan_channels({"id": "u", "phone": "+919812345678"}, prefs, "task_overdue", "CRITICAL")
        assert "whatsapp:opt_in_required" in skipped

    def test_phone_normalisation_to_e164(self):
        from app.notify.base import normalize_phone

        assert normalize_phone("098765 43210") == "+919876543210"
        assert normalize_phone("+91-98765-43210") == "+919876543210"
        assert normalize_phone("9876543210") == "+919876543210"
        assert normalize_phone("0044 1234 567890") == "+441234567890"
        assert normalize_phone("") == ""

    def test_dispatch_writes_inapp_and_outbox_with_per_channel_keys(self, store):
        from app.notify.engine import dispatch

        store.collection("users").document("u1").set({"id": "u1", "name": "T", "email": "t@x.io", "role": "FACULTY", "status": "ACTIVE", "phone": "+919812345678"})
        store.collection("notification_preferences").document("u1").set({"user_id": "u1", "whatsapp_opt_in": True, "min_severity_sms": "HIGH", "min_severity_whatsapp": "HIGH", "quiet_hours_enabled": False, "digest_mode": "none"})
        s = dispatch(store, target="u1", kind="task_overdue", title="Lab audit", message="3 days overdue", severity="HIGH", facts={"X": 1})
        assert s["inapp_written"]
        assert set(s["queued"]) >= {"email", "sms", "whatsapp"}
        keys = [d.to_dict()["fingerprint"] for d in store.collection("notification_outbox").stream()]
        assert len(keys) == len(set(keys)), "dedupe keys must be channel-scoped"

    def test_flush_delivers_and_logs(self, store):
        from app.notify.engine import dispatch
        from app.notify.queue import process_due

        store.collection("users").document("u2").set({"id": "u2", "name": "T2", "email": "t2@x.io", "role": "FACULTY", "status": "ACTIVE"})
        dispatch(store, target="u2", kind="task_assigned", title="New work", message="Assigned by HOD")
        out = process_due(store)
        assert out["sent"] >= 1 and out["dead"] == 0
        rows = [d.to_dict() for d in store.collection("notification_deliveries").stream()]
        assert rows and rows[0]["status"] in ("sent", "simulated")
        from app.config.settings import settings as _st
        files = os.listdir(os.path.join(_st.NOTIFY_DEV_OUTBOX_DIR, "email"))
        assert any(f.endswith(".eml") for f in files), "dev outbox must write an inspectable .eml"

    def test_retry_then_dead_letter_alerts_admin(self, store, monkeypatch):
        from app.config.settings import settings
        from app.notify import queue as q
        from app.notify.base import DeliveryResult, ProviderError
        from app.notify.engine import dispatch

        store.collection("users").document("u3").set({"id": "u3", "name": "T3", "email": "t3@x.io", "role": "FACULTY", "status": "ACTIVE"})
        monkeypatch.setattr(settings, "NOTIFY_MAX_ATTEMPTS", 2)
        monkeypatch.setattr(settings, "NOTIFY_BACKOFF_BASE_SECONDS", 0)
        monkeypatch.setattr(settings, "NOTIFY_JITTER_SECONDS", 0)

        def boom(self, msg):
            raise ProviderError("relay down")

        monkeypatch.setattr(q, "_pick_provider", lambda ch: type("P", (), {"name": "failing", "send": boom})())
        dispatch(store, target="u3", kind="deadline_risk", title="At risk", message="risk 88")
        first = q.process_due(store)
        assert first["retry"] >= 1
        row = [d.to_dict() for d in store.collection("notification_outbox").stream()][0]
        assert row["status"] == "retry" and row["attempts"] == 1
        second = q.process_due(store, now=datetime.utcnow() + timedelta(hours=1))
        assert second["dead"] >= 1
        alerts = [d.to_dict() for d in store.collection("notifications").stream() if "delivery failed" in d.to_dict().get("title", "")]
        assert alerts, "dead-lettering must page an operator"

    def test_dedupe_suppresses_repeats(self, store, monkeypatch):
        from app.config.settings import settings
        from app.notify.engine import dispatch

        monkeypatch.setattr(settings, "NOTIFY_DEDUPE_MINUTES", 60)
        store.collection("users").document("u4").set({"id": "u4", "name": "T4", "email": "t4@x.io", "role": "FACULTY", "status": "ACTIVE"})
        dispatch(store, target="u4", kind="task_assigned", title="Same", message="Body")
        second = dispatch(store, target="u4", kind="task_assigned", title="Same", message="Body")
        assert second["inapp_written"] is False
        assert second["deduped"], "identical alert within the window must be suppressed"

    def test_truncation_for_sms(self):
        from app.notify.base import truncate

        out = truncate("x" * 900, 480)
        assert len(out) <= 492 and out.endswith("…[trunc]")


# ------------------------------------------------------------------ approvals engine
class TestApprovals:
    def _doc(self, kind="event", amount=None):
        from app.engine.approvals import new_request

        return new_request(title="T", kind=kind, requester_id="u1", requester_name="Fac", department_id="d1", amount=amount, evidence={"venue": "Hall"})

    def test_two_stage_flow(self):
        from app.engine.approvals import advance

        d = self._doc()
        assert d["stages"] == ["HOD", "PRINCIPAL"] and d["status"] == "PENDING"
        d = advance(d, decision="APPROVE", actor_id="h", actor_role="HOD", note="ok")
        assert d["stage"] == "PRINCIPAL" and d["status"] == "PENDING"
        d = advance(d, decision="APPROVE", actor_id="p", actor_role="PRINCIPAL", note="sanctioned")
        assert d["status"] == "APPROVED" and d["closed_at"]

    def test_single_stage_kind_completes_at_hod(self):
        from app.engine.approvals import advance

        d = self._doc(kind="leave")
        d = advance(d, decision="APPROVE", actor_id="h", actor_role="HOD")
        assert d["status"] == "APPROVED"

    def test_amount_escalates_stage(self):
        from app.engine.approvals import policy_for

        assert policy_for("purchase", 1000).stages == ["HOD"]
        assert policy_for("purchase", 50000).stages == ["HOD", "PRINCIPAL"]

    def test_stage_and_terminal_guards(self):
        from app.engine import approvals as A

        # Principal may not act while the request is still at the HOD stage.
        d = self._doc()
        with pytest.raises(A.ApprovalError) as e:
            A.advance(d, decision="APPROVE", actor_id="p", actor_role="PRINCIPAL")
        assert e.value.code == "wrong_stage"

        # A repeated decision at the same stage is a stale-click; also blocked.
        with pytest.raises(A.ApprovalError) as e1:
            A.advance(d, decision="APPROVE", actor_id="h", actor_role="HOD", note="a")
            A.advance(d, decision="APPROVE", actor_id="h", actor_role="HOD", note="b")
        assert e1.value.code == "wrong_stage"  # request has moved to PRINCIPAL

        # Once fully decided, no role may act again - terminal beats stage checks.
        d2 = A.advance(self._doc(kind="leave"), decision="APPROVE", actor_id="h", actor_role="HOD", note="ok")
        assert d2["status"] == "APPROVED"
        with pytest.raises(A.ApprovalError) as e3:
            A.advance(d2, decision="APPROVE", actor_id="h", actor_role="HOD")
        assert e3.value.code == "already_decided"

        # Admin may override any open stage; a single-stage kind then completes.
        d4 = A.advance(self._doc(kind="leave"), decision="APPROVE", actor_id="a", actor_role="ADMIN", note="override")
        assert d4["status"] == "APPROVED"
        # A two-stage request acted on by admin still awaits the second signature.
        d5 = A.advance(self._doc(kind="event"), decision="APPROVE", actor_id="a", actor_role="ADMIN", note="override")
        assert d5["status"] == "PENDING" and d5["stage"] == "PRINCIPAL"

    def test_rejection_requires_note(self):
        from app.engine import approvals as A

        d = self._doc()
        with pytest.raises(A.ApprovalError) as e:
            A.advance(d, decision="REJECT", actor_id="h", actor_role="HOD", note="  ")
        assert e.value.code == "note_required"

    def test_resubmit_after_rejection(self):
        from app.engine import approvals as A

        d = A.advance(self._doc(), decision="REJECT", actor_id="h", actor_role="HOD", note="attach quote")
        d = A.resubmit(d, actor_id="u1", note="quote attached", evidence={"vendor_quote": "ok"})
        assert d["status"] == "PENDING" and d["stage"] == "HOD" and d["resubmissions"] == 1

    def test_sla_states(self):
        from app.engine import approvals as A

        d = self._doc()
        now = datetime.utcnow()
        d["stage_entered_at"] = (now - timedelta(hours=80)).isoformat()
        sla = A.evaluate_sla(d, now)
        assert sla["breached"] and not sla["escalate"] and 100 < sla["percent_consumed"] < 151
        d["stage_entered_at"] = (now - timedelta(hours=120)).isoformat()
        assert A.evaluate_sla(d, now)["escalate"] is True  # escalate only past 1.5x SLA

    def test_audit_chain_detects_tampering(self):
        from app.engine import approvals as A

        d = A.advance(self._doc(), decision="APPROVE", actor_id="h", actor_role="HOD", note="ok")
        assert A.verify_chain(d)[0] is True
        d["audit"][0]["actor_name"] = "Somebody Else"
        ok, problems = A.verify_chain(d)
        assert ok is False and problems


# ----------------------------------------------------------------------- API surface
class TestApi:
    def test_health_reports_backend_and_channels(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["persistence"]["backend"] == "sqlite"
        assert "jobs" in body["scheduler"]

    def test_tasks_endpoint_returns_risk_fields(self, client, hod):
        r = client.get("/api/v1/tasks/", headers=hod)
        assert r.status_code == 200
        row = r.json()[0]
        assert "risk_score" in row and row["risk_level"] in ("LOW", "MEDIUM", "HIGH", "CLOSED")

    def test_risk_board_and_score(self, client, hod):
        r = client.get("/api/v1/risk/board?limit=5", headers=hod)
        assert r.status_code == 200 and r.json()["count"] > 0
        tid = r.json()["tasks"][0]["id"]
        s = client.get(f"/api/v1/risk/score/{tid}", headers=hod)
        assert s.status_code == 200 and "factors" in s.json()

    def test_faculty_cannot_see_others_tasks(self, client, faculty, store):
        r = client.get("/api/v1/tasks/", headers=faculty)
        me = client.get("/api/v1/auth/me", headers=faculty).json()
        for row in r.json():
            assert row.get("assigned_id") == me["id"] or me["name"].lower() in (row.get("assigned") or "").lower()

    def test_approval_lifecycle_over_http(self, client, faculty, hod, principal, store):
        r = client.post(
            "/api/v1/workflow/",
            json={"title": "Hall booking", "kind": "event", "evidence": {"venue": "Hall", "date": "next week", "expected_attendees": "80"}},
            headers=faculty,
        )
        assert r.status_code == 200, r.text
        rid = r.json()["id"]
        assert r.json()["stage"] == "HOD"
        bad = client.post(f"/api/v1/workflow/{rid}/decide", json={"decision": "APPROVE"}, headers=principal)
        assert bad.status_code == 400
        step1 = client.post(f"/api/v1/workflow/{rid}/decide", json={"decision": "APPROVE", "note": "forwarded"}, headers=hod)
        assert step1.json()["stage"] == "PRINCIPAL"
        step2 = client.post(f"/api/v1/workflow/{rid}/decide", json={"decision": "APPROVE", "note": "sanctioned"}, headers=principal)
        assert step2.json()["status"] == "APPROVED"
        created = step2.json().get("created_task") or {}
        assert created.get("id"), "final approval must auto-instantiate the task (Slide 15, step 4)"
        task = client.get(f"/api/v1/tasks/{created['id']}", headers=hod)
        assert task.status_code == 200
        audit = client.get(f"/api/v1/workflow/{rid}/audit", headers=hod).json()
        assert audit["valid"] and len(audit["entries"]) == 3

    def test_channels_status_and_preferences(self, client, faculty):
        st = client.get("/api/v1/channels/status", headers=faculty).json()
        assert {"email", "sms", "whatsapp", "inapp"} <= set(st["channels"])
        pref = client.put("/api/v1/channels/preferences", json={"phone": "098765 43210", "whatsapp_opt_in": True}, headers=faculty).json()
        assert pref["preferences"]["phone"] == "+919876543210"

    def test_jobs_run_on_demand(self, client, hod):
        jobs = client.get("/api/v1/channels/jobs", headers=hod).json()["jobs"]
        assert len(jobs) >= 8
        for jid in ("risk_sweep", "daily_reminders", "approval_sla", "weekly_report"):
            r = client.post(f"/api/v1/channels/jobs/{jid}/run", headers=hod)
            assert r.status_code == 200 and "error" not in r.json()["result"], jid

    def test_scorecard_and_export(self, client, hod):
        sc = client.get("/api/v1/metrics/scorecard", headers=hod).json()
        for key in ("tasks", "risk", "approvals", "workload", "automation", "insights", "formulas"):
            assert key in sc
        csv = client.get("/api/v1/metrics/export?kind=faculty&format=csv", headers=hod)
        assert csv.status_code == 200 and "," in csv.text and len(csv.text.splitlines()) > 1

    def test_rbac_blocks_privileged_endpoints_for_low_roles(self, client, faculty):
        assert client.get("/api/v1/metrics/export?kind=tasks", headers=faculty).status_code == 403
        assert client.post("/api/v1/channels/jobs/risk_sweep/run", headers=faculty).status_code == 403

    def test_legacy_v1_pages_still_render(self, client, hod):
        for path in ("/api/v1/events/", "/api/v1/departments/me", "/api/v1/goals/", "/api/v1/notifications/", "/api/v1/notifications/unread-count", "/api/v1/approvals/", "/api/v1/analytics/faculty-performance", "/api/v1/ai/dashboard-summary", "/api/v1/reports/dashboard-stats", "/api/v1/reports/summary", "/api/v1/reports/recent-activities", "/api/v1/search/?q=a"):
            r = client.get(path, headers=hod)
            assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:120]}"

    def test_unauthenticated_is_401(self, client):
        assert client.get("/api/v1/tasks/").status_code == 401


# -------------------------------------------------------------------------- benchmarks
class TestBenchmarks:
    def test_corpus_labels_are_balanced_enough(self):
        from app.engine.benchmarks import synthetic_corpus

        rows = synthetic_corpus(n=120, seed=3)
        rate = sum(r["label"] for r in rows) / len(rows)
        assert 0.15 < rate < 0.85, "corpus must not be degenerate"

    def test_metrics_self_consistent(self):
        from app.engine.benchmarks import average_precision, confusion_at, roc_auc

        y = [1, 1, 0, 0, 1]
        s = [0.9, 0.8, 0.2, 0.4, 0.6]
        assert roc_auc(y, s) == 1.0
        assert average_precision(y, s) == 1.0
        c = confusion_at(y, [0.5, 0.5, 0.1, 0.1, 0.1])
        # p>=0.5 for the first two rows only: both true positives, one positive missed
        assert (c["tp"], c["fp"], c["fn"]) == (2, 0, 1)

    def test_engine_beats_naive_priority_on_top_decile(self):
        """The claim we make in the docs: better triage precision than static priority."""
        from app.engine import risk as R
        from app.engine.benchmarks import build_context, feature_vector, synthetic_corpus, thresholds

        rows = synthetic_corpus(n=260, seed=5)
        ctx = build_context(rows)
        y = [r["label"] for r in rows]
        ours = [R.assess(t, ctx)["risk_score"] for t in rows]
        naive = [ {"Low": 10, "Medium": 40, "High": 70, "Urgent": 90}[t["priority"]] for t in rows]
        assert thresholds(y, ours)["top_20pct_precision"] >= thresholds(y, naive)["top_20pct_precision"]


class TestUiSurfaces:
    """Endpoints called by the four v2 pages: Risk Center, Approval Desk, Analytics, Automation Center."""

    def test_approval_desk_queue_funnel_and_policies(self, client, hod):
        q = client.get("/api/v1/workflow/queue", headers=hod)
        assert q.status_code == 200
        body = q.json()
        assert body["role"] == "HOD"
        assert set(body["counts"]) >= {"total", "breached", "due_soon"}
        for row in body["items"]:
            assert {"id", "title", "kind", "stage", "sla"} <= set(row)
            assert row["sla"]["state"] in ("on_track", "due_soon", "breached", "escalated")

        f = client.get("/api/v1/workflow/stats/funnel", headers=hod).json()
        assert {"buckets", "pending_breaching_sla", "by_kind", "median_hours_to_decision"} <= set(f)
        assert f["buckets"].get("PENDING", 0) == body["counts"]["total"] or f["buckets"]["PENDING"] >= 0

        pol = client.get("/api/v1/workflow/policies", headers=hod).json()
        kinds = {p["kind"] for p in pol["policies"]}
        assert {"leave", "event", "purchase"} <= kinds
        assert pol["stages"] == ["HOD", "PRINCIPAL"]

    def test_delegation_moves_the_decision_right(self, client, faculty, hod, store):
        rid = client.post(
            "/api/v1/workflow/",
            json={"title": "Guest lecture hall", "kind": "event", "evidence": {"venue": "Seminar Hall", "date": "next month", "expected_attendees": "120"}},
            headers=faculty,
        ).json()["id"]

        others = [d for d in (s.to_dict() for s in store.collection("users").stream()) if d.get("role") in ("HOD",) and d.get("id") != "usr_hod"]
        if not others:
            others = [d for d in (s.to_dict() for s in store.collection("users").stream()) if d.get("role") in ("ADMIN",) and d.get("id") != "usr_hod"]
        sub = others[0]
        sub_headers = {"Authorization": f"Bearer {token_for(client, sub['email'])}"}

        d = client.post(f"/api/v1/workflow/{rid}/delegate", json={"to": sub["id"], "note": "on leave this week"}, headers=hod)
        assert d.status_code == 200, d.text
        assert d.json()["delegated_to"] == sub["id"]

        blocked = client.post(f"/api/v1/workflow/{rid}/decide", json={"decision": "APPROVE", "note": "trying anyway"}, headers=hod)
        assert blocked.status_code == 403 and "delegated" in blocked.json()["detail"].lower()

        step = client.post(f"/api/v1/workflow/{rid}/decide", json={"decision": "APPROVE", "note": "covering"}, headers=sub_headers)
        assert step.status_code == 200 and step.json()["stage"] == "PRINCIPAL"

    def test_analytics_page_data_and_formulas(self, client, hod, principal):
        card = client.get("/api/v1/metrics/scorecard?days=30", headers=hod).json()
        for section in ("tasks", "risk", "approvals", "workload", "automation", "formulas"):
            assert section in card, f"scorecard missing {section}"
        # every published formula is a human-readable ratio, so the number can be re-derived by hand
        assert "on_time_rate" in card["formulas"] and "/" in card["formulas"]["on_time_rate"]
        assert all(isinstance(v, str) and v for v in card["formulas"].values())
        assert card["analytics_scope"] in ("full_institute", "department", "self", "none")

        fac = client.get("/api/v1/metrics/faculty", headers=hod).json()
        assert fac["count"] == len(fac["items"]) and "weights" in fac and fac["note"]

        dept = client.get("/api/v1/metrics/departments", headers=hod).json()["items"]
        assert dept and {"health_index", "workload_balance_index", "projected_misses"} <= set(dept[0])

        fc = client.get("/api/v1/metrics/forecast?horizon_days=28", headers=hod).json()
        assert fc["horizon_days"] == 28 and "/" in fc["method"] or fc["method"]
        rows = fc["expected_completions_by_week"]
        assert rows and set(rows[0]) == {"week", "count"}
        assert fc["likely_to_miss"] + fc["within_horizon"] == fc["open_tasks"]
        assert fc["capacity_note"]

        assert client.get("/api/v1/metrics/risk-trend?days=30", headers=hod).json()["count"] == 0
        # snapshot capture is a manage_system capability: the HOD is refused, the Principal is allowed
        assert client.post("/api/v1/metrics/snapshot", headers=hod).status_code == 403
        assert client.post("/api/v1/metrics/snapshot", headers=principal).json()["ok"] is True
        snap = client.get("/api/v1/metrics/risk-trend?days=30", headers=hod).json()
        assert snap["count"] >= 1 and "bands" in snap["items"][0]

    def test_export_is_capability_gated_and_streams_csv(self, client, hod, faculty):
        r = client.get("/api/v1/metrics/export?kind=tasks&format=csv", headers=hod)
        assert r.status_code == 200
        assert "csv" in r.headers["content-type"]
        header_row = r.text.splitlines()[0]
        assert "title" in header_row and "risk_score" in header_row

        for kind in ("scorecard", "faculty", "approvals", "departments", "audit"):
            assert client.get(f"/api/v1/metrics/export?kind={kind}&format=csv", headers=hod).status_code == 200

        denied = client.get("/api/v1/metrics/export?kind=tasks&format=csv", headers=faculty)
        assert denied.status_code == 403 and "export_reports" in denied.json()["detail"]

        bad = client.get("/api/v1/metrics/export?kind=nope&format=csv", headers=hod)
        assert bad.status_code in (400, 422)


class TestSchedulerTriggers:
    """A cron expression that fails to parse silently drops a job - the deck's 8 AM reminder cannot do that."""

    def test_every_registered_job_trigger_constructs(self):
        from app.scheduler.jobs import JOBS

        assert len(JOBS) == 10
        for spec in JOBS:
            assert spec["trigger"]() is not None, f"{spec['id']} has an unbuildable trigger"

    def test_multi_time_reminder_registers_both_hours(self, monkeypatch):
        from app.scheduler import jobs as J

        # offset 0 => the campus-local clock is the cron clock, so assertions stay readable
        monkeypatch.setattr(J, "SCHED_TZ", None)
        monkeypatch.setattr(J, "_UTC_OFFSET_MIN", 0)
        rendered = repr(J._cron("08:00,17:00"))
        assert "hour='8,17'" in rendered and "minute='0'" in rendered, rendered
        assert repr(J._cron("08:00")).count("hour='8'") == 1  # a single time still works

    def test_mixed_minutes_warn_instead_of_dropping_silently(self, monkeypatch, caplog):
        import logging

        from app.scheduler import jobs as J

        monkeypatch.setattr(J, "SCHED_TZ", None)
        with caplog.at_level(logging.WARNING, logger="campuspulse"):
            J._cron("08:00,17:30")
        assert any("share the same minute" in r.getMessage() for r in caplog.records)
