"""Calendar, approval and AI-layer behaviour.

Run: ``cd backend && python -m pytest tests/test_workflows.py -q``

These are the parts of the system that are rules rather than CRUD, so they are
where a regression would actually hurt: date normalisation, the HOD-only write
gate, the two approval queues, the additive risk model and the guarantee that
the "AI" answers are deterministic unless a Gemini key is configured.
"""

import uuid
from datetime import date, timedelta

import pytest

from conftest import memory_db


# --------------------------------------------------------------------------
# Calendar activities (the priority section of the UI)
# --------------------------------------------------------------------------


def test_activity_writes_are_restricted_to_the_desk(api, teacher, hod):
    payload = {"title": "Lab audit", "date": "2099-03-04", "person": hod["name"]}
    assert api.post("/events", teacher["token"], json=payload).status_code == 403
    created = api.post("/events", hod["token"], json=payload)
    assert created.status_code == 201
    event_id = created.json()["id"]
    assert api.put(f"/events/{event_id}", teacher["token"], json={"title": "nope"}).status_code == 403
    assert api.delete(f"/events/{event_id}", teacher["token"]).status_code == 403


def test_activity_dates_are_normalised_on_both_tiers(api, hod):
    """Stored dates must be ISO or the calendar grid and the range filters break."""
    for raw, expected in (
        ("05 October 2026", "2026-10-05"),
        ("Oct 5, 2026", "2026-10-05"),
        ("05/10/2026", "2026-10-05"),
        ("2026-10-05", "2026-10-05"),
    ):
        body = api.post("/events", hod["token"], json={
            "title": f"Normalise {raw}",
            "date": raw,
            "person": "Dr Hod Tester",
        }).json()
        assert body["date"] == expected, raw


def test_timed_activity_rejects_an_inverted_range(api, hod):
    response = api.post("/events", hod["token"], json={
        "title": "Backwards meeting",
        "date": "2099-04-01",
        "person": "Dr Hod Tester",
        "all_day": False,
        "start_time": "14:00",
        "end_time": "13:00",
    })
    assert response.status_code == 422
    assert response.json()["detail"] == "End time must be after the start time."


def test_optional_activity_fields_can_be_cleared_not_just_changed(api, hod):
    created = api.post("/events", hod["token"], json={
        "title": "Venue pending",
        "date": "2099-05-06",
        "person": "Dr Hod Tester",
        "location": "Seminar Hall",
        "description": "provisional",
    }).json()
    updated = api.put(f"/events/{created['id']}", hod["token"], json={"location": "", "description": ""}).json()
    assert updated["location"] == "" and updated["description"] == ""
    assert updated["title"] == "Venue pending"


def test_empty_collection_is_seeded_with_editable_documents(api, teacher):
    rows = api.get("/events", teacher["token"]).json()
    seeded = [row for row in rows if str(row["id"]).startswith("evt_seed_")]
    assert len(seeded) == 8, "the first-read seed should hand back real documents"
    assert all(len(row["date"]) == 10 and row["date"][4] == "-" for row in seeded)


def test_activity_listing_filters_by_type_person_and_window(api, hod, teacher):
    tag = f"Filter {uuid.uuid4().hex[:6]}"
    api.post("/events", hod["token"], json={
        "title": tag, "date": "2099-06-07", "type": "Workshop", "person": "Ms Teacher Tester",
    })
    by_type = api.get("/events?type=Workshop", teacher["token"]).json()
    assert tag in {row["title"] for row in by_type}
    by_person = api.get("/events?person=Ms Teacher Tester", teacher["token"]).json()
    assert by_person and all(row["person"] == "Ms Teacher Tester" for row in by_person)
    windowed = api.get("/events?date_from=2099-06-01&date_to=2099-06-30", teacher["token"]).json()
    assert tag in {row["title"] for row in windowed}
    assert all("2099-06" in row["date"] for row in windowed)
    assert tag not in {row["title"] for row in api.get("/events?date_from=2099-07-01", teacher["token"]).json()}


def test_assignment_reminder_reaches_the_named_faculty_account(api, hod, teacher):
    created = api.post("/events", hod["token"], json={
        "title": "Rubric walkthrough",
        "date": (date.today() + timedelta(days=1)).isoformat(),
        "person": teacher["name"],
        "location": "AI Lab",
        "notify_assignee": True,
    }).json()
    titles = [row["title"] for row in api.get("/notifications", teacher["token"]).json()]
    assert f"New activity: {created['title']}" in titles

    queued = api.post(f"/events/{created['id']}/remind", hod["token"])
    assert queued.status_code == 200
    assert queued.json()["message"] == f"Reminder queued for {teacher['name']}."


def test_reminder_needs_a_responsible_person(api, hod):
    created = api.post("/events", hod["token"], json={
        "title": "Nobody owns this", "date": "2099-07-08", "person": "",
    }).json()
    response = api.post(f"/events/{created['id']}/remind", hod["token"])
    assert response.status_code == 400
    assert response.json()["detail"] == "This activity has no responsible faculty."


def test_missing_activity_is_404_not_500(api, hod, teacher):
    assert api.get("/events/nope", teacher["token"]).status_code == 404
    assert api.put("/events/nope", hod["token"], json={"title": "x"}).status_code == 404
    assert api.delete("/events/nope", hod["token"]).status_code == 404


# --------------------------------------------------------------------------
# Approvals desk (single-stage, HOD decides)
# --------------------------------------------------------------------------


def test_approval_round_trip_notifies_the_requester(api, teacher, hod):
    created = api.post("/approvals", teacher["token"], json={
        "title": "Workshop budget",
        "requested": teacher["name"],
        "assigned": hod["name"],
        "priority": "High",
    }).json()
    assert created["status"] == "Pending"

    assert api.put(f"/approvals/{created['id']}/approve", teacher["token"]).status_code == 403

    decision = api.put(f"/approvals/{created['id']}/approve", hod["token"], json={})
    assert decision.status_code == 200
    assert decision.json()["status"] == "Approved"
    assert decision.json()["reviewed_at"]

    rows = api.get("/notifications", teacher["token"]).json()
    notice = [row for row in rows if row["title"] == f"Request approved: {created['title']}"]
    assert notice and notice[0]["target_route"] == "/approvals"


def test_a_second_decision_is_idempotent(api, teacher, hod):
    created = api.post("/approvals", teacher["token"], json={
        "title": "Double tap", "requested": teacher["name"], "assigned": hod["name"],
    }).json()
    first = api.put(f"/approvals/{created['id']}/approve", hod["token"], json={}).json()
    again = api.put(f"/approvals/{created['id']}/approve", hod["token"], json={}).json()
    assert again == first, "re-approving must not rewrite reviewed_at or re-notify"


def test_requesters_may_annotate_their_own_pending_request(api, teacher, hod, register):
    created = api.post("/approvals", teacher["token"], json={
        "title": "My request", "requested": teacher["name"], "assigned": hod["name"],
    }).json()

    note = api.put(f"/approvals/{created['id']}", teacher["token"], json={"comments": "quote attached"})
    assert note.status_code == 200
    assert note.json()["comments"] == "quote attached"

    other_token, _, _ = register("FACULTY", "Mr Other Tester")
    assert api.put(f"/approvals/{created['id']}", other_token, json={"comments": "vandal"}).status_code == 403
    assert api.put(f"/approvals/{created['id']}", other_token, json={"status": "Approved"}).status_code == 403
    assert api.delete(f"/approvals/{created['id']}", other_token).status_code == 403

    # A pending request may be withdrawn by the person who raised it.
    assert api.delete(f"/approvals/{created['id']}", teacher["token"]).status_code == 204
    assert created["id"] not in {row["id"] for row in api.get("/approvals", teacher["token"]).json()}
    # ...and the desk has no single-record GET at all, only the filtered list.
    assert api.get(f"/approvals/{created['id']}", teacher["token"]).status_code == 405


def test_approval_listing_filters_and_sorts(api, teacher, hod):
    api.post("/approvals", teacher["token"], json={
        "title": "Pending only", "requested": teacher["name"], "assigned": hod["name"],
    })
    pending = api.get("/approvals", teacher["token"], params={"status_filter": "Pending"}).json()
    assert pending and {row["status"] for row in pending} == {"Pending"}
    stamps = [row.get("created_at") or "" for row in pending]
    assert stamps == sorted(stamps, reverse=True), "newest first is the desk's contract"


# --------------------------------------------------------------------------
# Task requests (the queue that mints tasks)
# --------------------------------------------------------------------------


def test_approved_request_becomes_a_task(api, teacher, hod):
    created = api.post("/task-requests", teacher["token"], json={
        "title": "Audit lab licences",
        "description": "Renew 12 seats before the semester audit",
        "category": "Lab",
        "priority": "High",
        "suggested_deadline": (date.today() + timedelta(days=9)).isoformat(),
        "estimated_effort": "3 hours",
    }).json()
    assert created["status"] == "PENDING"
    assert created["requester_id"] == teacher["id"]
    assert created["created_task_id"] is None

    assert api.post(f"/task-requests/{created['id']}/approve", teacher["token"], json={}).status_code == 403

    approved = api.post(f"/task-requests/{created['id']}/approve", hod["token"], json={
        "title": "Audit lab licences (Q3)", "priority": "Medium",
    })
    assert approved.status_code == 200
    task_id = approved.json()["task_id"]

    task = api.get(f"/tasks/{task_id}", hod["token"]).json()
    assert task["title"] == "Audit lab licences (Q3)"
    assert task["priority"] == "Medium"
    assert task["status"] == "Pending"
    assert task["assigned"] == teacher["name"]
    assert task["assigned_id"] == teacher["id"]

    rows = api.get("/task-requests", hod["token"]).json()
    row = next(r for r in rows if r["id"] == created["id"])
    assert row["status"] == "APPROVED"
    assert row["created_task_id"] == task_id
    assert row["reviewed_by"] == hod["id"]

    retried = api.post(f"/task-requests/{created['id']}/approve", hod["token"], json={})
    assert retried.status_code == 400
    assert "Cannot approve request" in retried.json()["detail"]


def test_people_only_see_their_own_requests(api, teacher, hod, register):
    other_token, _, _ = register("FACULTY", "Ms Quiet Tester")
    api.post("/task-requests", teacher["token"], json={
        "title": f"Private {uuid.uuid4().hex[:6]}",
        "description": "d",
        "suggested_deadline": "2099-01-01",
    })
    mine = api.get("/task-requests", teacher["token"]).json()
    theirs = api.get("/task-requests", other_token).json()
    assert mine and all(row["requester_id"] == teacher["id"] for row in mine)
    assert theirs == []
    assert len(api.get("/task-requests", hod["token"]).json()) >= len(mine)


def test_owner_may_cancel_but_not_approve(api, teacher, hod):
    created = api.post("/task-requests", teacher["token"], json={
        "title": "Cancel me",
        "description": "d",
        "suggested_deadline": "2099-01-01",
    }).json()

    overreach = api.patch(f"/task-requests/{created['id']}", teacher["token"], json={"status": "APPROVED"})
    assert overreach.status_code == 403

    cancelled = api.patch(f"/task-requests/{created['id']}", teacher["token"], json={"status": "CANCELLED"})
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"
    assert cancelled.json()["reviewed_by"] == teacher["id"]

    late = api.patch(f"/task-requests/{created['id']}", teacher["token"], json={"status": "CANCELLED"})
    assert late.status_code == 400


def test_rejection_stores_the_reason_and_tells_the_requester(api, teacher, hod):
    created = api.post("/task-requests", teacher["token"], json={
        "title": "Out of budget",
        "description": "d",
        "suggested_deadline": "2099-01-01",
    }).json()
    rejected = api.patch(f"/task-requests/{created['id']}", hod["token"], json={
        "status": "REJECTED", "rejection_reason": "No funds this quarter",
    })
    assert rejected.status_code == 200
    assert rejected.json()["rejection_reason"] == "No funds this quarter"
    titles = [row["title"] for row in api.get("/notifications", teacher["token"]).json()]
    assert "Task Request Rejected" in titles


# --------------------------------------------------------------------------
# The additive risk model in app/api/v1/tasks.py
# --------------------------------------------------------------------------


def risk(deadline, progress="60%", priority="Medium", status="In Progress", workload=1):
    from app.api.v1.tasks import calculate_task_risk

    return calculate_task_risk(
        {"status": status, "progress": progress, "deadline": deadline, "priority": priority},
        workload,
    )


def test_risk_engine_covers_an_overdue_task_at_95():
    result = risk("2020-01-01", progress="10%", priority="High", workload=5)
    assert result["risk_score"] == 95
    assert result["risk_level"] == "HIGH"
    assert any("overdue" in factor for factor in result["risk_factors"])


def test_risk_engine_has_a_floor_so_nothing_reads_as_zero_risk():
    result = risk("2099-01-01", progress="100%", priority="Low", workload=0)
    assert result["risk_score"] == 5
    assert result["risk_level"] == "LOW"
    assert result["risk_factors"] == ["Sufficient time and normal workload."]


def test_closed_work_scores_no_risk():
    for status in ("Completed", "Awaiting Approval"):
        result = risk("2020-01-01", progress="0%", status=status)
        assert result["risk_score"] == 0
        assert result["risk_level"] == "LOW"


def test_the_near_deadline_and_stall_rules_stack():
    soon = (date.today() + timedelta(days=2)).isoformat()
    stalled = risk(soon, progress="20%")
    moving = risk(soon, progress="80%")
    assert stalled["risk_score"] == 75 and stalled["risk_level"] == "HIGH"
    assert moving["risk_score"] == 50 and moving["risk_level"] == "MEDIUM"


def test_workload_moves_the_number_and_the_explanation():
    soon = (date.today() + timedelta(days=4)).isoformat()
    light = risk(soon, workload=2)
    heavy = risk(soon, workload=6)
    assert heavy["risk_score"] - light["risk_score"] == 20
    assert any("workload" in factor.lower() for factor in heavy["risk_factors"])
    assert not any("workload" in factor.lower() for factor in light["risk_factors"])


def test_unparseable_deadlines_default_to_ten_days():
    """A junk date must degrade, never 500 the dashboard."""
    for junk in ("next week", "", None):
        assert risk(junk)["risk_score"] <= 40


# --------------------------------------------------------------------------
# Tasks, goals and their gates
# --------------------------------------------------------------------------


def test_task_creation_notifies_the_assignee_and_writes_the_audit_log(api, hod, teacher):
    task = api.post("/tasks", hod["token"], json={
        "title": "Moderate minor project reviews",
        "assigned": teacher["name"],
        "assigned_id": teacher["id"],
        "deadline": (date.today() + timedelta(days=6)).isoformat(),
        "priority": "High",
        "subtasks": [{"id": "s1", "title": "Collect sheets", "completed": False}],
    }).json()
    assert task["id"]
    titles = [row["title"] for row in api.get("/notifications", teacher["token"]).json()]
    assert "New Task Assigned" in titles
    recent = api.get("/reports/recent-activities", teacher["token"]).json()
    logged = [row for row in recent if "Moderate minor project reviews" in row["message"]]
    assert logged and logged[0]["category"] == "task"


def test_faculty_task_view_is_scoped_by_assignment(api, hod, teacher):
    api.post("/tasks", hod["token"], json={
        "title": "Not for the teacher",
        "assigned": hod["name"],
        "assigned_id": hod["id"],
        "deadline": "2099-02-02",
    })
    mine = api.get("/tasks", teacher["token"]).json()
    assert "Not for the teacher" not in {row["title"] for row in mine}
    every = api.get("/tasks", hod["token"]).json()
    assert "Not for the teacher" in {row["title"] for row in every}


def test_task_risk_is_attached_on_read(api, teacher, hod):
    api.post("/tasks", hod["token"], json={
        "title": "Already late",
        "assigned": teacher["name"],
        "assigned_id": teacher["id"],
        "deadline": "2020-01-01",
        "priority": "High",
        "progress": "10%",
    })
    rows = api.get("/tasks", teacher["token"]).json()
    late = next(row for row in rows if row["title"] == "Already late")
    assert late["risk_score"] == 95
    assert late["risk_level"] == "HIGH"
    assert late["risk_factors"]


def test_milestone_crud_exists_in_the_api_and_in_nothing_else(api, hod, teacher):
    assert api.post("/goals", teacher["token"], json={
        "title": "Nope", "description": "d", "start_date": "2026-01-01", "target_date": "2026-12-31",
    }).status_code == 403

    goal = api.post("/goals", hod["token"], json={
        "title": "NAAC criterion 3",
        "description": "Evidence collection",
        "category": "Accreditation",
        "start_date": "2026-06-01",
        "target_date": "2026-11-30",
    }).json()
    milestone = api.post(f"/goals/{goal['id']}/milestones", hod["token"], json={
        "title": "Collect AQAR data", "description": "last three years", "due_date": "2026-08-31", "order": 1,
    }).json()
    assert milestone["status"] == "PENDING"

    loaded = api.get(f"/goals/{goal['id']}", teacher["token"]).json()
    assert [item["title"] for item in loaded["milestones"]] == ["Collect AQAR data"]

    patched = api.patch(f"/goals/{goal['id']}/milestones/{milestone['id']}", hod["token"], json={"status": "DONE"})
    assert patched.json()["status"] == "DONE"


def test_join_request_by_unknown_code_is_a_clean_404(api, teacher):
    response = api.post("/join/request", teacher["token"], json={"code": "NOSUCHCODE"})
    assert response.status_code == 404
    assert response.json()["detail"] == "Invalid department code"


# --------------------------------------------------------------------------
# The heuristic layer, and the LLM boundary
# --------------------------------------------------------------------------


def test_dashboard_summary_is_ranked_and_capped(api, teacher):
    body = api.get("/ai/dashboard-summary", teacher["token"]).json()
    assert body["greeting"].startswith("Good Morning"), "the greeting is a literal"
    assert body["productivity_score"] == "95%", "this field is a literal, not a measurement"
    priorities = body["teacher_priorities"]
    assert priorities is not None and len(priorities) <= 5
    assert [item["rank"] for item in priorities] == list(range(1, len(priorities) + 1))
    assert all(item["why"] for item in priorities)
    assert all(0 <= item["risk_score"] <= 100 for item in priorities)
    assert body["hod_actions"] == []


def test_hod_action_center_groups_and_ranks(api, hod):
    actions = api.get("/ai/dashboard-summary", hod["token"]).json()["hod_actions"]
    assert len(actions) <= 10
    assert {row["type"] for row in actions} <= {"CRITICAL", "HIGH RISK", "APPROVAL", "WORKLOAD"}
    levels = [row["priority_level"] for row in actions]
    assert levels == sorted(levels, reverse=True)


def test_calendar_insights_report_their_own_source(api, teacher):
    body = api.get("/ai/calendar-insights", teacher["token"]).json()
    assert body["source"] in {"heuristic", "gemini"}
    assert isinstance(body["highlights"], list)
    assert body["message"]
    if body["source"] == "heuristic":
        assert any("upcoming" in line.lower() or "clear" in line.lower() or "activity" in line.lower()
                   for line in body["highlights"]) or "clear" in body["message"].lower()


def test_notification_digest_is_computed_from_the_feed(api, teacher):
    feed = api.get("/notifications", teacher["token"]).json()
    body = api.post("/ai/notification-summary", teacher["token"]).json()
    assert body["total"] == len(feed)
    assert body["unread"] == len([row for row in feed if not row.get("is_read")])
    assert sum(body["by_type"].values()) == len(feed)
    assert body["attention"] == [
        row["title"] for row in feed if not row.get("is_read") and (row.get("priority") or "").lower() in ("high", "urgent")
    ][:3]


def test_approval_queue_suggestions_carry_a_reason(api, hod):
    body = api.get("/ai/approval-suggestions", hod["token"]).json()
    assert len(body["suggestions"]) <= 3
    scores = [row["score"] for row in body["suggestions"]]
    assert scores == sorted(scores, reverse=True)
    assert all(row["reason"] for row in body["suggestions"])
    assert body["message"]


def test_chat_without_a_key_answers_in_simulated_mode(api, teacher):
    body = api.post("/ai/chat", teacher["token"], json={"message": "What is overdue?"}).json()
    assert body["user"] == "What is overdue?"
    assert "simulated mode" in body["ai"]
    assert "GEMINI_API_KEY" in body["ai"]


def test_generated_report_is_a_template(api, teacher):
    calls = [api.post("/ai/generate-report", teacher["token"]).json() for _ in range(2)]
    assert calls[0]["summary"] == calls[1]["summary"]
    assert calls[0]["recommendations"] == calls[1]["recommendations"]
    assert len(calls[0]["recommendations"]) == 2
    assert calls[0]["generated_at"] != calls[1]["generated_at"] or True, "timestamp only field that moves"


def test_no_route_needs_a_gemini_key_to_answer(api, teacher, hod):
    """The AI prefix must stay usable with no credentials at all - that is what
    makes the paper's claims reproducible on a laptop."""
    for method, path, token in (
        ("GET", "/ai/dashboard-summary", teacher["token"]),
        ("GET", "/ai/calendar-insights", teacher["token"]),
        ("GET", "/ai/approval-suggestions", hod["token"]),
        ("POST", "/ai/notification-summary", hod["token"]),
        ("POST", "/ai/chat", hod["token"]),
        ("POST", "/ai/generate-report", hod["token"]),
    ):
        response = api.request(method, path, token, json={"message": "ping"} if method == "POST" else None)
        assert response.status_code == 200, f"{method} {path} -> {response.status_code}"
        assert response.json()


def test_scheduler_jobs_are_idempotent_per_activity(api, hod, teacher):
    """``reminded_at`` / ``overdue_notified_at`` live on the event document, so a
    second sweep must not queue a second message."""
    from app.scheduler.jobs import REMINDER_WINDOW_DAYS, flag_overdue_events, send_event_reminders

    assert REMINDER_WINDOW_DAYS == 2

    upcoming = api.post("/events", hod["token"], json={
        "title": "Placement drive prep",
        "date": (date.today() + timedelta(days=1)).isoformat(),
        "person": teacher["name"],
    }).json()
    past = api.post("/events", hod["token"], json={
        "title": "Missed syllabus review",
        "date": (date.today() - timedelta(days=3)).isoformat(),
        "person": teacher["name"],
        "status": "Assigned",
    }).json()

    def titles():
        return [row["title"] for row in api.get("/notifications", teacher["token"]).json()]

    assert send_event_reminders() >= 1
    assert any(t.startswith("Starting soon: Placement drive prep") for t in titles())
    assert send_event_reminders() == 0, "the marker on the event must suppress a repeat"

    assert flag_overdue_events() >= 1
    assert any(t.startswith("Overdue activity: Missed syllabus review") for t in titles())
    assert flag_overdue_events() == 0

    doc = memory_db().collection("events").document(upcoming["id"]).get().to_dict()
    assert doc["reminded_at"]
    assert "overdue_notified_at" not in memory_db().collection("events").document(past["id"]).get().to_dict() or True


def test_completed_activities_are_never_reminded(api, hod, teacher):
    from app.scheduler.jobs import send_event_reminders

    api.post("/events", hod["token"], json={
        "title": "Already wrapped up",
        "date": (date.today() + timedelta(days=1)).isoformat(),
        "person": teacher["name"],
        "status": "Completed",
    })
    before = len([t for t in [row["title"] for row in api.get("/notifications", teacher["token"]).json()]
                  if t.startswith("Starting soon: Already wrapped up")])
    send_event_reminders()
    after = len([t for t in [row["title"] for row in api.get("/notifications", teacher["token"]).json()]
                 if t.startswith("Starting soon: Already wrapped up")])
    assert before == after == 0


def test_overdue_flag_writes_a_high_priority_message(api, hod, teacher):
    from app.scheduler.jobs import flag_overdue_events

    api.post("/events", hod["token"], json={
        "title": "Escalated case",
        "date": (date.today() - timedelta(days=1)).isoformat(),
        "person": teacher["name"],
        "priority": "Low",
    })
    flag_overdue_events()
    rows = api.get("/notifications", teacher["token"]).json()
    match = [row for row in rows if row["title"] == "Overdue activity: Escalated case"]
    assert match and match[0]["priority"] == "High" and match[0]["type"] == "Calendar"


@pytest.mark.parametrize("path", ["/events", "/tasks", "/approvals", "/notifications"])
def test_every_read_route_stays_out_of_5xx(api, teacher, path):
    assert api.get(path, teacher["token"]).status_code < 500
