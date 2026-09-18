"""Demo corpus: a believable AIML department, generated relative to *today*.

The deck's success criterion is "login as each role -> assign -> approve -> notify ->
analyse", and the risk engine needs spread (on plan / slipping / overdue / blocked) to be
worth looking at. Static fixtures from a PDF submission go stale the moment the deadline
dates pass, so every date here is relative to the run date and the dataset is deterministic
(seeded RNG) for reproducible demos and CI.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Any, Dict, List

import bcrypt

from app.config.settings import settings

SEED_MARKER = "seed_meta"

FACULTY_NAMES = [
    ("Mrs. Neha Gurnani", "Assistant Professor", "AI/ML"),
    ("Dr. Vikram Sinha", "Professor", "Data Science"),
    ("Dr. Bhushan Mahendra Manjre", "Associate Professor", "Computer Vision"),
    ("Ms. Sweta Arun Bokade", "Assistant Professor", "NLP"),
    ("Mr. Rohit Deshmukh", "Assistant Professor", "IoT & Embedded"),
    ("Mrs. Pooja Wankhede", "Assistant Professor", "Deep Learning"),
    ("Dr. Kiran Bhaskar", "Professor", "Cyber Security"),
    ("Ms. Aarti Chaudhari", "Assistant Professor", "Web Technologies"),
]

TASK_TEMPLATES = [
    ("AI Lab Maintenance & Licence Renewal", "Verify GPU workstations, update CUDA drivers, renew MATLAB/Nessus licences.", "Lab", "High", ["Inventory audit", "Driver updates", "Licence renewal"]),
    ("Final Year Project Review - Phase 1", "Review 24 FYP proposals, allot guides, publish evaluation rubric.", "Academic", "High", ["Rubric", "Guide allotment", "Panel scheduling"]),
    ("Student Research Tracking (Scopus cycle)", "Log 12 faculty papers, update ORCID records, prepare department research summary.", "Research", "Medium", ["Paper log", "ORCID sync", "Summary memo"]),
    ("NAAC Criterion 3 Evidence Collection", "Compile publications, patents and consultancy records for Criterion 3.3.", "Accreditation", "High", ["Criterion 3.1", "Criterion 3.3", "Files upload"]),
    ("NBA SOP Mapping Workshop", "Map course COs to POs for AY 2026-27 with the outcome-based rubric.", "Accreditation", "High", ["Draft CO-PO", "Faculty review", "Programme approval"]),
    ("National Conference - Invited Speaker", "Confirm two keynote speakers, arrange TA, publish the schedule.", "Event", "Medium", ["Speaker list", "Travel arrangements", "Poster"]),
    ("Machine Learning Workshop (3-day)", "Design curriculum, lab setup for 60 seats, student selection.", "Event", "Medium", ["Curriculum", "Lab booking", "Selection"]),
    (" FDP on Generative AI - Budget Note", "Prepare the head-of-account note and vendor quotations for the 5-day FDP.", "Finance", "High", ["Budget note", "Quotes", "Approval trail"]),
    ("Internship Drive - Company Onboarding", "Onboard 8 recruiters, schedule pre-placement talks, collect offers.", "Placement", "Medium", ["Outreach", "Scheduling", "Offers logged"]),
    ("Semester Question Paper Moderation", "Draft, moderate and lock 9 papers for End-Sem I with the moderation report.", "Academic", "High", ["Drafting", "Moderation", "Locking"]),
    ("Course File Completion (AY 2026-27)", "Complete course files with lesson plans, CO attainment and tutorial lists.", "Academic", "Medium", ["Lesson plan", "CO attainment", "Tutorial list"]),
    ("Library Book Requisition - AI/ML Titles", "Raise the requisition for 40 new titles with quotations and vendor comparison.", "Administration", "Low", ["Title list", "Quotations", "Requisition"]),
    ("Attendance Defaulter Analysis", "Run the defaulter report, counsel the top 15, notify parents via coordinators.", "Academic", "High", ["Report", "Counselling", "Parent notice"]),
    ("Hackathon Venue & Permissions", "Book the seminar hall, arrange permissions, define the judging panel.", "Event", "Medium", ["Venue", "Permissions", "Judges"]),
    ("Alumni Interaction - Placement Session", "Invite 6 alumni, prepare question set, publish the outcome note.", "Alumni", "Low", ["Invites", "Question set", "Note"]),
    ("Anti-Ragging Committee Report", "Compile awareness-session proof and submit to the state portal.", "Administration", "Medium", ["Awareness proof", "Portal upload"]),
    ("Outcome-Based Teaching Audit", "Sample 10 course files, prepare the OBT compliance note.", "Academic", "High", ["Sampling", "Compliance note"]),
    ("Lab Equipment Purchase Request", "Raise the purchase request for 10 Raspberry Pi kits with three quotations.", "Finance", "Medium", ["Specification", "Quotations"]),
    ("Student Mentoring Log (Odd Sem)", "Update mentoring logs for 180 students; flag at-risk mentees.", "Mentoring", "Medium", ["Log update", "At-risk list"]),
    ("Curriculum Feedback Analysis", "Analyse student and employer feedback; prepare the revision proposal.", "Academic", "Low", ["Survey", "Analysis", "Proposal"]),
    ("Placement Training - Aptitude Module", "Run 12 aptitude sessions, track pre-placement test scores.", "Placement", "Medium", ["Sessions", "PPT tracker"]),
    ("Research Grant Application (SERB)", "Draft and submit the SERB CRG proposal with institute endorsement.", "Research", "High", ["Draft", "Endorsement", "Submission"]),
    ("Laboratory Safety Audit", "Conduct chemical/electrical safety audit and close the findings.", "Administration", "Medium", ["Audit", "Findings closed"]),
    ("Department Newsletter - Issue 4", "Collect contributions, design, publish and archive the newsletter.", "Communication", "Low", ["Contributions", "Layout", "Publish"]),
    ("Student No-Due Process Automation", "Digitise the no-due flow with library, accounts and hostel sign-off.", "Administration", "Medium", ["Flow design", "Pilot"]),
    ("Faculty Development Programme - Invite", "Send invitation letters to resource persons and publish the brochure.", "Event", "Low", ["Letters", "Brochure"]),
    ("Student Discipline Committee Note", "Prepare the inquiry note and recommended action for 3 cases.", "Administration", "High", ["Inquiry", "Recommendation"]),
    ("Courseware Upload to LMS", "Publish 4 courses of lecture notes, slides and assignment links.", "Academic", "Low", ["Slides", "Assignments"]),
]

GOALS = [
    ("NAAC A+ Reaccreditation readiness", "Accreditation", 180, ["Criterion 1 evidence", "Criterion 2 evidence", "Criterion 3 evidence", "Criterion 4 evidence", "DVV submission"]),
    ("NBA accreditation for CSE (AI&ML)", "Accreditation", 240, ["SOP drafting", "CO-PO mapping", "Programme outcomes workshop", "IRC file"]),
    ("Placement rate 90% for graduating batch", "Placements", 120, ["Aptitude drive", "Soft-skills module", "12 recruiters onboarded", "Offer tracking"]),
    ("Research output: 15 Scopus papers", "Research", 300, ["Paper drafting sprints", "Reviewer pool", "Grant submissions"]),
]

EVENTS = [
    ("Machine Learning Workshop (3-day)", "Workshop", 6, "Seminar Hall", "Dr. Animesh Tayal"),
    ("National Conference on Applied AI", "Conference", 21, "Main Auditorium", "Dr. Bhushan Mahendra Manjre"),
    ("Smart India Hackathon - Campus Round", "Competition", 2, "AI Lab", "Mr. Rohit Deshmukh"),
    ("Alumni Career Panel", "Alumni", 12, "Seminar Hall", "Ms. Aarti Chaudhari"),
    ("Industry Visit - Automation Plant", "Industrial Visit", 30, "MIDC Butibori", "Mrs. Pooja Wankhede"),
    ("FDP on Generative AI in Teaching", "Faculty Development", 45, "Computer Centre", "Dr. Kiran Bhaskar"),
]

APPROVALS = [
    ("Leave Application - 3 days (Diwali)", "leave", "Medium", {"from_date": "2026-11-09", "to_date": "2026-11-11", "leave_type": "Casual"}, None),
    ("Purchase: 10 Raspberry Pi 5 kits", "purchase", "High", {"item": "Raspberry Pi 5 (8GB)", "quantity": "10", "vendor_quote": "3 quotations attached"}, 48000),
    ("Hall Booking - ML Workshop", "event", "High", {"venue": "Seminar Hall", "date": "in 6 days", "expected_attendees": "60"}, 15000),
    ("No Objection Certificate - Internship", "no_objection", "Medium", {"purpose": "Summer internship at a Bengaluru startup"}, None),
    ("Budget: Conference Refreshments", "budget", "Medium", {"head": "Event - Hospitality", "amount": "22000", "justification": "200 delegates x 2 days"}, 22000),
    ("Equipment: Oscilloscopes for Lab 3", "purchase", "Low", {"item": "Digital storage oscilloscope", "quantity": "4", "vendor_quote": "EmmeTech quote attached"}, 96000),
    ("Deadline Extension - NAAC Evidence", "deadline_change", "High", {"old_deadline": "next Friday", "new_deadline": "in 12 days", "reason": "Awaiting HOD sign-off on Criterion 3"}, None),
    ("Student Event: AI Quiz Night", "event", "Low", {"venue": "Classroom 302", "date": "in 9 days", "expected_attendees": "120"}, 8000),
]


def _hash(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt(rounds=12)).decode()


def build_dataset(now: datetime) -> Dict[str, List[Dict[str, Any]]]:
    rnd = random.Random(20260127)
    dept = {"id": "dept_aiml", "name": "Computer Science & Engineering (Artificial Intelligence & Machine Learning)", "code": "AIML", "created_at": (now - timedelta(days=400)).isoformat(timespec="seconds")}
    dept2 = {"id": "dept_it", "name": "Information Technology", "code": "IT", "created_at": (now - timedelta(days=380)).isoformat(timespec="seconds")}

    principal_id = "usr_principal"
    hod_id = "usr_hod"
    users: List[Dict[str, Any]] = [
        {
            "id": principal_id,
            "name": "Dr. S. R. Kulkarni",
            "email": "principal@demo.hierasync.in",
            "role": "PRINCIPAL",
            "department_id": None,
            "designation": "Principal",
            "status": "ACTIVE",
            "phone": "+919822011223",
        },
        {
            "id": hod_id,
            "name": "Dr. Animesh Tayal",
            "email": "hod.aiml@hierasync.demo",
            "role": "HOD",
            "department_id": dept["id"],
            "designation": "Head of Department",
            "status": "ACTIVE",
            "phone": "+919850112233",
        },
    ]
    # A second HOD so the Information Technology department has a real stage-1 approver:
    # _approver_for() routes by departments/<id>.hod_id, and that user must hold approve_hod.
    hod_it_id = "usr_hod_it"
    users.append(
        {
            "id": hod_it_id,
            "name": "Dr. Prashant Deshpande",
            "email": "hod.it@hierasync.demo",
            "role": "HOD",
            "department_id": dept2["id"],
            "designation": "Head of Department",
            "status": "ACTIVE",
            "phone": "+919850223344",
        }
    )

    for i, (name, desig, area) in enumerate(FACULTY_NAMES):
        slug = name.lower().replace("mrs. ", "").replace("dr. ", "").replace("ms. ", "").replace("mr. ", "").replace(" ", ".")
        users.append(
            {
                "id": f"usr_fac_{i+1}",
                "name": name,
                "email": f"{slug}@hierasync.demo",
                "role": "FACULTY",
                "department_id": dept["id"] if i % 4 else dept2["id"],
                "designation": desig,
                "area_of_interest": area,
                "joining_date": (now - timedelta(days=rnd.randint(400, 2400))).date().isoformat(),
                "association": "Regular",
                "status": "ACTIVE",
                # phones spread across formats on purpose: exercises E.164 normalisation
                "phone": rnd.choice(["+91981234560{}".format(i), "0981234561{}".format(i), "981234561{}".format(i)]),
            }
        )
    # TEACHER is a distinct role from FACULTY in the deck's list of 10; it needs its own demo user
    # so role-aware UI, RBAC and the alias map (PROFESSOR -> TEACHER) can be exercised by logging in.
    users.append(
        {
            "id": "usr_teacher",
            "name": "Dr. Kavita Ramesh Joshi",
            "email": "teacher@hierasync.demo",
            "role": "TEACHER",
            "department_id": dept["id"],
            "designation": "Senior Teacher",
            "area_of_interest": "Compiler Design",
            "status": "ACTIVE",
            "phone": "+919876543210",
        }
    )
    users.append({"id": "usr_ta", "name": "Ayush Pande", "email": "ta@hierasync.demo", "role": "TA", "department_id": dept["id"], "designation": "Project TA", "status": "ACTIVE", "phone": "+919899000111"})
    users.append({"id": "usr_lab", "name": "Sachin Uike", "email": "lab.assistant@hierasync.demo", "role": "LAB_ASSISTANT", "department_id": dept["id"], "designation": "Lab Assistant", "status": "ACTIVE"})
    users.append({"id": "usr_staff", "name": "Meena Kakade", "email": "office.staff@hierasync.demo", "role": "STAFF", "department_id": dept["id"], "designation": "Department Secretary", "status": "ACTIVE"})
    users.append({"id": "usr_rep", "name": "Rutuja Shende", "email": "student.rep@hierasync.demo", "role": "STUDENT_REP", "department_id": dept["id"], "designation": "Class Representative - TE", "status": "ACTIVE"})
    users.append({"id": "usr_student", "name": "Aditya Rane", "email": "student@hierasync.demo", "role": "STUDENT", "department_id": dept["id"], "designation": "BE (AI & ML), Batch 2027", "status": "ACTIVE"})
    users.append({"id": "usr_admin", "name": "System Administrator", "email": "admin@hierasync.demo", "role": "ADMIN", "department_id": None, "designation": "Platform Admin", "status": "ACTIVE", "phone": "+919000000000"})

    for u in users:
        u["hashed_password"] = _hash(settings.DEMO_PASSWORD)
        u.setdefault("avatar_url", None)

    # HOD of record + principal id references
    dept["hod_id"] = hod_id
    dept2["hod_id"] = hod_it_id

    tasks: List[Dict[str, Any]] = []
    faculty = [u for u in users if u["role"] in ("FACULTY", "TA")]
    # (offset_days_from_today, progress, status) triples -> guarantees a spread of bands
    plans = [
        (-9, 60, "In Progress"), (-4, 35, "In Progress"), (-1, 80, "In Progress"), (0, 45, "In Progress"),
        (1, 30, "In Progress"), (1, 85, "In Progress"), (2, 15, "TODO"), (2, 70, "In Progress"),
        (3, 55, "In Progress"), (3, 20, "Blocked"), (4, 65, "In Progress"), (5, 40, "In Progress"),
        (6, 75, "In Progress"), (7, 25, "TODO"), (9, 50, "In Progress"), (12, 10, "TODO"),
        (14, 60, "In Progress"), (2, 100, "Awaiting Approval"), (1, 100, "Awaiting Approval"), (-6, 100, "Completed"),
        (-14, 100, "Completed"), (-21, 100, "Completed"), (-2, 100, "Completed"), (-30, 100, "Completed"),
        (20, 5, "TODO"), (25, 0, "TODO"), (30, 12, "In Progress"), (8, 90, "In Progress"),
        (11, 33, "In Progress"), (16, 48, "In Progress"),
    ]
    for idx, (title, desc, category, priority, subs) in enumerate(TASK_TEMPLATES):
        days_left, progress, status = plans[idx % len(plans)]
        assignee = faculty[idx % len(faculty)]
        deadline = now + timedelta(days=days_left, hours=rnd.choice([9, 17]))
        created = deadline - timedelta(days=rnd.choice([5, 7, 10, 14]))
        done_count = int(round(len(subs) * progress / 100.0))
        tasks.append(
            {
                "id": f"tsk_{idx+1:03d}",
                "title": title,
                "description": desc,
                "category": category,
                "priority": priority,
                "status": status,
                "deadline": deadline.date().isoformat(),
                "start_date": created.date().isoformat(),
                "created_at": created.isoformat(timespec="seconds"),
                "updated_at": (now - timedelta(days=rnd.randint(0, 9), hours=rnd.randint(0, 20))).isoformat(timespec="seconds"),
                "completed_at": (deadline + timedelta(days=rnd.choice([-2, -1, 0, 0, 3]))).isoformat(timespec="seconds") if status == "Completed" else None,
                "progress": f"{progress}%",
                "progress_pct": float(progress),
                "assigned": assignee["name"],
                "assigned_id": assignee["id"],
                "assignee_id": assignee["id"],
                "creator_id": hod_id,
                "department_id": assignee["department_id"],
                "goal_id": f"goal_{(idx % len(GOALS)) + 1}",
                "require_approval": True,
                "estimated_effort": rnd.choice(["6h", "12h", "16h", "24h", "", ""]),
                "subtasks": [{"id": f"st_{idx}_{j}", "title": st, "completed": j < done_count} for j, st in enumerate(subs)],
                "is_recurring": idx % 9 == 0,
                "recurrence_pattern": "monthly" if idx % 9 == 0 else None,
                "blocked": status == "Blocked",
                "blocked_by": [{"id": f"dep_{idx}", "title": TASK_TEMPLATES[(idx + 3) % len(TASK_TEMPLATES)][0], "status": "In Progress"}] if status == "Blocked" else [],
                "source": "seed",
            }
        )

    goals: List[Dict[str, Any]] = []
    for gi, (title, cat, horizon, miles) in enumerate(GOALS):
        target = now + timedelta(days=horizon)
        done = rnd.randint(1, max(1, len(miles) - 1))
        goals.append(
            {
                "id": f"goal_{gi+1}",
                "title": title,
                "category": cat,
                "department_id": dept["id"],
                "owner_id": hod_id if gi % 2 == 0 else faculty[gi % len(faculty)]["id"],
                "target_date": target.date().isoformat(),
                "milestones": [{"id": f"m_{gi}_{j}", "title": m, "done": j < done} for j, m in enumerate(miles)],
                "progress": int(done / len(miles) * 100),
                "created_at": (now - timedelta(days=60)).isoformat(timespec="seconds"),
            }
        )

    events: List[Dict[str, Any]] = []
    for ei, (title, etype, in_days, loc, person) in enumerate(EVENTS):
        start = (now + timedelta(days=in_days)).replace(hour=rnd.choice([9, 10, 14]), minute=0, second=0, microsecond=0)
        events.append(
            {
                "id": f"evt_{ei+1:03d}",
                "title": title,
                "type": etype,
                "event_type": etype,
                "date": start.date().isoformat(),
                "start_time": start.isoformat(timespec="seconds"),
                "end_time": (start + timedelta(hours=rnd.choice([2, 3, 6]))).isoformat(timespec="seconds"),
                "location": loc,
                "person": person,
                "organizer": person,
                "organizer_id": next((u["id"] for u in users if u["name"] == person), None),
                "department_id": dept["id"],
                "creator_id": hod_id,
                "description": f"{etype} organised by the AIML department.",
                "created_at": (now - timedelta(days=rnd.randint(5, 40))).isoformat(timespec="seconds"),
            }
        )

    approvals: List[Dict[str, Any]] = []
    import uuid as _uuid

    from app.engine.approvals import new_request, advance

    requesters = [u for u in users if u["role"] in ("FACULTY", "TA", "STAFF", "STUDENT_REP")]
    for ai, (title, kind, priority, evidence, amount) in enumerate(APPROVALS):
        who = requesters[ai % len(requesters)]
        created = now - timedelta(days=rnd.randint(1, 12), hours=rnd.randint(0, 10))
        doc = new_request(
            title=title,
            kind=kind,
            requester_id=who["id"],
            requester_name=who["name"],
            department_id=who["department_id"],
            description=f"Raised from the department desk. {list(evidence.values())[0] if evidence else ''}".strip(),
            amount=amount,
            evidence=evidence,
            priority=priority,
            hod_id=hod_id,
            principal_id=principal_id,
            now=created,
        )
        # vary the stage so the queue, the breach path and the auto-task flow are all visible
        if ai in (2, 5):
            doc = advance(doc, decision="APPROVE", actor_id=hod_id, actor_role="HOD", actor_name="Dr. Animesh Tayal", note="Recommend, forwarded for sanction.", now=created + timedelta(hours=20))
        elif ai == 3:
            doc = advance(doc, decision="REJECT", actor_id=hod_id, actor_role="HOD", actor_name="Dr. Animesh Tayal", note="Submit through the placement cell portal instead.", now=created + timedelta(hours=9))
        approvals.append({**doc, "id": f"apr_{ai+1:03d}", "requested": who["name"], "assigned": who["name"]})

    notif_prefs = [
        {"user_id": "usr_fac_1", "email": "nehagurnani@hierasync.demo", "phone": "+919812345601", "whatsapp_opt_in": True, "digest_mode": "none", "quiet_hours_enabled": True, "min_severity_sms": "HIGH", "min_severity_whatsapp": "HIGH"},
        {"user_id": "usr_hod", "email": "hod.aiml@hierasync.demo", "phone": "+919850112233", "whatsapp_opt_in": True, "digest_mode": "daily", "quiet_hours_enabled": False, "min_severity_sms": "MEDIUM", "min_severity_whatsapp": "HIGH"},
        {"user_id": "usr_principal", "email": "principal@demo.hierasync.in", "phone": "+919822011223", "whatsapp_opt_in": False, "digest_mode": "daily", "quiet_hours_enabled": True},
    ]

    settings_docs = [
        {"user_id": u["id"], "ai_recommendation": True, "task_analysis": True, "deadline_alert": True, "email_notifications": True}
        for u in users
    ]

    return {
        "departments": [dept, dept2],
        "users": users,
        "tasks": tasks,
        "goals": goals,
        "events": events,
        "approvals": approvals,
        "notification_preferences": notif_prefs,
        "settings": settings_docs,
    }


def seed(db: Any, *, force: bool = False) -> Dict[str, Any]:
    now = datetime.utcnow()
    existing = db.collection(SEED_MARKER).document("last")
    if existing.get().exists and not force:
        return {"seeded": False, "reason": "already seeded", "at": existing.to_dict().get("at")}
    for snap in list(db.collection(SEED_MARKER).stream()):
        snap.reference.delete()

    data = build_dataset(now)
    counts = {}
    for collection, rows in data.items():
        for row in rows:
            row = dict(row)
            # Keep the id inside the document body as well as being the key: v1 routers
            # (and `User(**doc)`) read `id` from the payload, and Firestore does not inject it.
            rid = str(row.get("id") or row.get("user_id") or f"{collection[:3]}_{abs(hash(str(row))) % 10**8}")
            row["id"] = rid
            db.collection(collection).document(rid).set(row)
        counts[collection] = len(rows)
    db.collection(SEED_MARKER).document("last").set({"at": now.isoformat(timespec="seconds"), "counts": counts, "engine": "hierasync-v2"})
    logger_msg = f"Seeded {sum(counts.values())} documents: {counts}"
    from app.utils.logging import logger

    logger.info(logger_msg)
    return {"seeded": True, "counts": counts}


def seed_if_empty(db: Any) -> Dict[str, Any]:
    """Boot-time helper: only populate a pristine database, never overwrite real usage."""
    try:
        has_users = any(True for _ in db.collection("users").stream())
    except Exception:
        has_users = True
    if has_users:
        return {"seeded": False, "reason": "existing data present"}
    if not settings.SEED_DEMO_DATA:
        return {"seeded": False, "reason": "SEED_DEMO_DATA=false"}
    return seed(db)
