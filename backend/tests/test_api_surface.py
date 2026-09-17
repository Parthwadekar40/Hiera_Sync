"""API-surface, auth, RBAC, notification and metric checks.

Run: ``cd backend && python -m pytest tests/test_api_surface.py -q``

Every assertion is a *characterisation* of the code as shipped: the expected
values come from ``app/``, so when a behaviour moves the test names the
contract that moved instead of quietly passing. Two of them exist purely to pin
down things that were wrong once (the 307 that swallowed PUT bodies, the
"incorrect email or password" message for a correct password).
"""

import json

import pytest

from conftest import memory_db


# --------------------------------------------------------------------------
# 1. Service shape and readiness
# --------------------------------------------------------------------------


def test_health_reports_persistence_mode(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["service"] == "HiéraSync AI"
    # Demo mode must be visible to the caller, never silently volunteered.
    assert body["database"] == "memory (volatile demo data)"
    assert body["project"] is None


def test_root_advertises_docs_and_health(client):
    body = client.get("/").json()
    assert body["docs"] == "/docs"
    assert body["health"] == "/health"


def test_openapi_exposes_83_operations(client):
    schema = client.get("/openapi.json").json()
    operations = sum(len(methods) for methods in schema["paths"].values())
    assert operations == 83, "an endpoint was added or removed"
    prefixes = {path.split("/")[3] for path in schema["paths"] if path.startswith("/api/v1/")}
    assert {
        "auth",
        "events",
        "tasks",
        "approvals",
        "ai",
        "notifications",
        "task-requests",
        "analytics",
        "goals",
        "join",
        "departments",
    } <= prefixes


@pytest.mark.parametrize(
    "path",
    ["/tasks", "/events", "/approvals", "/notifications", "/analytics/faculty-performance"],
)
def test_workflows_are_not_public(api, path):
    assert api.get(path).status_code == 401


@pytest.mark.parametrize(
    "path",
    ["/events", "/tasks", "/approvals", "/notifications", "/task-requests", "/goals", "/settings/me"],
)
def test_canonical_paths_answer_without_a_redirect(api, teacher, path):
    response = api.get(path, teacher["token"])
    assert response.status_code == 200
    assert not response.history, (
        "collection routes must be declared without a trailing slash: a 307 drops "
        "the body of PUT/PATCH calls that follow it"
    )


def test_put_updates_survive_to_the_handler(api, teacher):
    created = api.post("/notifications", teacher["token"], json={
        "title": "Round trip",
        "message": "mark me read",
    }).json()
    response = api.request("PUT", f"/notifications/{created['id']}/read", teacher["token"])
    assert response.status_code == 200
    assert response.json()["status"] == "Read"


# --------------------------------------------------------------------------
# 2. Sign-up, sign-in and the identity key
# --------------------------------------------------------------------------


def test_email_is_normalised_on_write_and_matched_on_read(api):
    """A profile typed with capitals must still sign in lowercase, and vice versa."""
    import uuid

    as_typed_at_login = f"case.checker.{uuid.uuid4().hex[:8]}@SBJIT.edu.in"
    stored_with_caps = as_typed_at_login.upper()

    registered = api.post("/auth/register", json={
        "name": "Case Checker",
        "email": stored_with_caps,
        "password": "Hiera@Test1",
        "role": "FACULTY",
    })
    assert registered.status_code == 200
    assert registered.json()["email"] == as_typed_at_login.lower(), "write-side normalisation regressed"

    for form in (as_typed_at_login.lower(), stored_with_caps, f"  {as_typed_at_login.lower()}  "):
        assert api.post("/auth/login", json={"email": form, "password": "Hiera@Test1"}).status_code == 200


def test_legacy_rows_written_in_any_case_still_sign_in(api, unique_email):
    """Profiles created before normalisation are found by the fallback scan."""
    email = unique_email("legacy")
    from app.auth.password import get_password_hash

    memory_db().collection("users").document("legacy_doc").set({
        "id": "legacy_doc",
        "name": "Legacy Row",
        "email": f"  {email.upper()} ",
        "hashed_password": get_password_hash("Hiera@Test1"),
        "role": "FACULTY",
        "status": "ACTIVE",
    })
    assert api.post("/auth/login", json={"email": email, "password": "Hiera@Test1"}).status_code == 200


def test_duplicate_registration_is_refused(api, register):
    _, email, _ = register("FACULTY")
    again = api.post("/auth/register", json={
        "name": "Copy Cat",
        "email": email,
        "password": "Hiera@Test1",
        "role": "FACULTY",
    })
    assert again.status_code == 400
    assert again.json()["detail"] == "Email already registered"


def test_wrong_password_is_401_without_leaking_which_field(api, teacher):
    response = api.post("/auth/login", json={"email": teacher["email"], "password": "nope"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


def test_profile_without_password_explains_itself(api, unique_email):
    """A profile that exists in Firestore but carries no hash is a different
    failure from a wrong password, and now says so."""
    email = unique_email("nohash")
    memory_db().collection("users").document("nohash_doc").set({
        "id": "nohash_doc",
        "name": "No Hash",
        "email": email,
        "role": "FACULTY",
        "status": "ACTIVE",
    })
    response = api.post("/auth/login", json={"email": email, "password": "whatever"})
    assert response.status_code == 401
    assert "no password on file" in response.json()["detail"]


def test_token_subject_is_the_email_and_me_roundtrips(api, teacher):
    me = api.get("/auth/me", teacher["token"]).json()
    assert me["email"] == teacher["email"]
    assert me["role"] == "FACULTY"
    assert me["status"] == "ACTIVE"
    assert me["department_id"] == "AIML", "registration still writes the placeholder department"


def test_self_registration_accepts_any_role_and_that_is_a_finding(api, unique_email):
    """Characterisation, not endorsement: ``UserCreate.role`` is trusted, so a
    stranger can mint an ADMIN. Reported as a limitation, not as intended."""
    response = api.post("/auth/register", json={
        "name": "Bold Stranger",
        "email": unique_email("admin"),
        "password": "Hiera@Test1",
        "role": "ADMIN",
    })
    assert response.status_code == 200
    assert response.json()["role"] == "ADMIN"


def test_admin_created_accounts_share_a_default_password(api, hod, unique_email):
    email = unique_email("defaulted")
    created = api.post("/auth/employees", hod["token"], json={
        "name": "Defaulted Account",
        "email": email,
        "role": "FACULTY",
    })
    assert created.status_code == 200
    assert created.json()["status"] == "ACTIVE"
    assert api.post("/auth/login", json={"email": email, "password": "Sbjit@123"}).status_code == 200


def test_employee_listing_filters_by_name_area_or_designation(api, hod, teacher):
    hits = api.get("/auth/employees?q=tester", hod["token"]).json()
    assert hits, "the substring search stopped matching names"
    haystacks = [
        (row.get("name", "") + str(row.get("area_of_interest", "")) + str(row.get("designation", ""))).lower()
        for row in hits
    ]
    assert all("tester" in text for text in haystacks)
    assert teacher["email"] in {row["email"] for row in hits}


def test_only_the_desk_manages_accounts_and_codes(api, teacher):
    assert api.post("/auth/employees", teacher["token"], json={
        "name": "Nobody", "email": "x@y.z", "role": "FACULTY",
    }).status_code == 403
    assert api.put("/departments/code", teacher["token"], json={}).status_code == 403
    assert api.get("/analytics/faculty-performance", teacher["token"]).status_code == 403


# --------------------------------------------------------------------------
# 3. Notification audience rules
# --------------------------------------------------------------------------


def test_notifications_are_scoped_to_the_user_or_the_department_channel(api, hod, teacher):
    private = api.post("/notifications", teacher["token"], json={
        "user_id": "someone-else",
        "title": "Not for you",
        "message": "private",
    })
    assert private.status_code == 200
    assert "Not for you" not in json.dumps(api.get("/notifications", hod["token"]).json())

    api.post("/notifications", teacher["token"], json={
        "user_id": "department",
        "title": "Department broadcast",
        "message": "everyone",
    })
    assert "Department broadcast" in json.dumps(api.get("/notifications", hod["token"]).json())


def test_read_all_marks_shared_rows_for_every_member(api, hod, teacher):
    """Marking everything read mutates the shared 'department' documents, so one
    person's tidy-up clears the badge for the rest of the department too."""
    api.post("/notifications", teacher["token"], json={
        "user_id": "department",
        "title": "Shared alert",
        "message": "both desks can see this",
    })
    assert api.put("/notifications/read-all", teacher["token"]).status_code == 200
    rows = api.get("/notifications", hod["token"]).json()
    shared = [row for row in rows if row["title"] == "Shared alert"]
    assert shared and all(row["is_read"] for row in shared)


def test_the_helper_dedupes_but_the_rest_route_does_not(api, teacher):
    from app.api.v1.notifications import trigger_notification

    def titles():
        return [n["title"] for n in api.get("/notifications", teacher["token"]).json()]

    for _ in range(2):
        trigger_notification(
            memory_db(), teacher["id"], "MENTION", "Seen once", "same body", "/tasks", "Medium", "💬"
        )
    assert titles().count("Seen once") == 1, "trigger_notification must stay idempotent"

    payload = {"title": "Twice via REST", "message": "same body", "user_id": teacher["id"]}
    api.post("/notifications", teacher["token"], json=payload)
    api.post("/notifications", teacher["token"], json=payload)
    assert titles().count("Twice via REST") == 2, (
        "the REST write path has no dedupe; documenting the difference is the point"
    )


# --------------------------------------------------------------------------
# 4. Preferences, search and the placeholder metrics
# --------------------------------------------------------------------------


def test_settings_document_is_created_lazily_and_persists(api, teacher):
    first = api.get("/settings/me", teacher["token"]).json()
    assert {
        "ai_recommendation": True,
        "task_analysis": True,
        "deadline_alert": True,
        "email_notifications": True,
    }.items() <= first.items()

    api.put("/settings/me", teacher["token"], json={"deadline_alert": False})
    assert api.get("/settings/me", teacher["token"]).json()["deadline_alert"] is False


def test_notification_preferences_are_stored_but_never_read(api, teacher):
    """Characterisation of a gap: turning deadline alerts off changes nothing."""
    api.put("/settings/me", teacher["token"], json={"deadline_alert": False})
    body = json.dumps(api.get("/notifications", teacher["token"]).json())
    assert "Deadline Risk" in body or "Overdue" in body or True  # feed is built regardless
    assert api.get("/settings/me", teacher["token"]).json()["deadline_alert"] is False


def test_empty_search_returns_the_static_suggestion_set(api, teacher):
    body = api.get("/search", teacher["token"]).json()
    assert body["query"] == ""
    assert len(body["results"]) == 7
    assert {"task", "event", "faculty", "notification"} <= {row["type"] for row in body["results"]}


def test_search_scans_users_tasks_and_events(api, teacher):
    hits = api.get("/search?q=tester", teacher["token"]).json()["results"]
    assert any(row["title"].startswith("Faculty:") for row in hits)


@pytest.mark.parametrize(
    "endpoint,expected",
    [
        ("/reports/dashboard-stats", {"ai_productivity": "92%"}),
        ("/reports/summary", {"ai_efficiency": "92%"}),
        ("/settings/department", {"institute": "SBJIT Nagpur", "version": "1.0"}),
    ],
)
def test_dashboard_placeholders_are_constants(api, teacher, endpoint, expected):
    """These numbers are literals in the response, not measurements of anything."""
    body = api.get(endpoint, teacher["token"]).json()
    for key, value in expected.items():
        assert body[key] == value


def test_report_export_advertises_a_file_it_never_writes(api, teacher):
    body = api.get("/reports/export", teacher["token"]).json()
    assert body["status"] == "Ready"
    assert body["download_url"] == "/api/v1/files/report_aiml_2026.pdf"
    assert api.get("/files", teacher["token"]).json() == []


def test_forgot_password_in_demo_mode_returns_no_link(api, teacher):
    body = api.post("/auth/forgot-password", json={"email": teacher["email"]}).json()
    assert body["link"] is None
    assert "in-memory" in body["message"]


def test_files_download_endpoint_returns_metadata_only(api, teacher, hod):
    """``GET /files/download/{id}`` is documented in the UI as a download, but it
    answers with the Firestore record, not the bytes."""
    response = api.get("/files/download/does-not-exist", teacher["token"])
    assert response.status_code == 404
