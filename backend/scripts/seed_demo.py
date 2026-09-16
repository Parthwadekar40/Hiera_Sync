#!/usr/bin/env python3
"""Seed a realistic AIML department into the running API.

    python scripts/seed_demo.py                       # local uvicorn
    python scripts/seed_demo.py --api-base https://api.example.com/api/v1

Useful for reviewing the app (or a workshop demo) without hand-clicking: it
registers faculty accounts, fills the activity calendar around today's date and
loads the approvals queue. Safe to re-run - existing accounts are reused and
duplicate titles are skipped. In demo mode (no Firebase credentials) everything
lives in memory and resets when the server restarts.
"""

import argparse
import getpass
import json
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta

DEFAULT_USERS = [
    {"name": "Dr. Animesh Tayal", "email": "hod@sbjit.edu.in", "role": "HOD",
     "designation": "Head of Department"},
    {"name": "Dr. Bhushan Mahendra Manjre", "email": "bhushan@sbjit.edu.in", "role": "HOD",
     "designation": "Associate Professor"},
    {"name": "Mrs. Neha Gurnani", "email": "neha@sbjit.edu.in", "role": "TEACHER",
     "designation": "Assistant Professor"},
    {"name": "Ms. Sweta Arun Bokade", "email": "sweta@sbjit.edu.in", "role": "FACULTY",
     "designation": "Assistant Professor"},
    {"name": "Ms. Preeti Deshmukh", "email": "preeti@sbjit.edu.in", "role": "FACULTY",
     "designation": "Lecturer"},
]

# (offset_days, title, type, owner, status, priority, start, end, location)
ACTIVITIES = [
    (-2, "Attendance Audit — BE Semester 5", "Meeting", "Mrs. Neha Gurnani",
     "Assigned", "Medium", None, None, "HOD Cabin"),
    (0, "NAAC Criteria 3 Evidence Review", "Department Activity", "Dr. Animesh Tayal",
     "Assigned", "High", "11:00", "13:00", "Seminar Hall"),
    (1, "Minor Project Internal Review", "Academic", "Mrs. Neha Gurnani",
     "Planned", "High", "09:30", "12:30", "Lab 3"),
    (1, "Research Group: Federated Learning", "Research", "Dr. Bhushan Mahendra Manjre",
     "Planned", "Medium", None, None, "AI Lab"),
    (3, "LLM Fine-tuning Workshop", "Workshop", "Dr. Bhushan Mahendra Manjre",
     "Planned", "Medium", "14:00", "17:00", "AI Lab"),
    (5, "Course File Submission — TYAIML", "Academic", "Ms. Sweta Arun Bokade",
     "Assigned", "High", None, None, "Department Office"),
    (9, "Scopus Paper Draft — Federated Learning", "Research", "Dr. Bhushan Mahendra Manjre",
     "Review", "High", None, None, "Library"),
    (12, "Industry Visit — Nagpur AI Park", "Department Activity", "Ms. Preeti Deshmukh",
     "Planned", "Medium", "08:00", "17:00", "Nagpur"),
    (18, "Mid-Semester Assessment — SYAIML", "Academic", "Ms. Sweta Arun Bokade",
     "Planned", "Medium", None, None, "Hall A"),
]

REQUESTS = [
    ("Final Year Project Review Panel", "Mrs. Neha Gurnani", "Dr. Animesh Tayal", "High", "Pending"),
    ("AI Lab GPU Upgrade Quotation", "Dr. Bhushan Mahendra Manjre", "Dr. Animesh Tayal", "High", "Pending"),
    ("Guest Lecture — Prompt Engineering", "Ms. Preeti Deshmukh", "Dr. Animesh Tayal", "Medium", "Pending"),
    ("Library Book Requisition (24 titles)", "Ms. Sweta Arun Bokade", "Dr. Animesh Tayal", "Low", "Pending"),
]


def call(base, method, path, payload=None, token=None):
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(f"{base}{path}", data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode()
            return response.status, (json.loads(body) if body else {})
    except urllib.error.HTTPError as error:
        raw = error.read().decode()
        try:
            return error.code, json.loads(raw)
        except json.JSONDecodeError:
            return error.code, {"detail": raw}
    except urllib.error.URLError as error:
        print(f"Cannot reach {base} — is the API running? ({error.reason})", file=sys.stderr)
        sys.exit(1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the HieraSync demo department")
    parser.add_argument("--api-base", default="http://127.0.0.1:8000/api/v1")
    parser.add_argument("--password", default=None,
                        help="shared password for the seeded accounts (prompted if omitted)")
    args = parser.parse_args()
    base = args.api_base.rstrip("/")
    password = args.password or getpass.getpass("Password for the seeded accounts: ")

    tokens = {}
    for user in DEFAULT_USERS:
        status, _ = call(base, "POST", "/auth/register", {**user, "password": password,
                                                          "department_id": "AIML"})
        note = "created" if status in (200, 201) else f"reused ({status})"
        login_status, login = call(base, "POST", "/auth/login",
                                   {"email": user["email"], "password": password})
        if login_status != 200:
            print(f"  ! login failed for {user['email']}: {login.get('detail')}")
            continue
        tokens[user["name"]] = login["access_token"]
        print(f"  account {user['email']:28} {note:22} role={user['role']}")

    if not tokens:
        print("No account could sign in — nothing to seed.", file=sys.stderr)
        return 1

    hod_token = tokens.get(DEFAULT_USERS[0]["name"]) or next(iter(tokens.values()))

    _, existing_events = call(base, "GET", "/events", token=hod_token)
    # key on title + date so a same-titled activity on another day can still be added
    known_titles = {f"{event.get('title')}|{event.get('date')}" for event in existing_events}
    today = date.today()
    added = 0
    for offset, title, activity_type, owner, status, priority, start, end, location in ACTIVITIES:
        day = (today + timedelta(days=offset)).isoformat()
        if f"{title}|{day}" in known_titles:
            continue
        payload = {
            "title": title,
            "date": day,
            "type": activity_type,
            "person": owner,
            "status": status,
            "priority": priority,
            "location": location,
            "all_day": start is None,
            "notify_assignee": offset >= 0,
        }
        if start:
            payload["start_time"] = start
            payload["end_time"] = end
        code, body = call(base, "POST", "/events", payload, token=hod_token)
        if code in (200, 201):
            added += 1
            print(f"  activity {day}  {title[:44]:44} {status:9} {priority}")
        else:
            print(f"  ! could not add “{title}”: {body.get('detail')}")
    print(f"{added} activities created ({len(known_titles)} were already present)")

    _, existing_requests = call(base, "GET", "/approvals", token=hod_token)
    known_requests = {item.get("title") for item in existing_requests}
    for title, requester, assignee, priority, _status in REQUESTS:
        if title in known_requests:
            continue  # already in the queue
        code, body = call(base, "POST", "/approvals",
                          {"title": title, "requested": requester, "assigned": assignee,
                           "priority": priority}, token=hod_token)
        if code in (200, 201):
            print(f"  request {title[:52]:52} ({requester})")
        else:
            print(f"  ! could not add request “{title}”: {body.get('detail')}")

    print("\nSign in with any seeded account, e.g.")
    print(f"  {DEFAULT_USERS[0]['email']}  /  {password}")
    print("Then open /calendar — the queue, drag-and-drop, filters and exports all run live.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
