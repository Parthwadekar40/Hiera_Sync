#!/usr/bin/env python
"""
Create or repair an account directly in Firestore - no API, no token, no approval.

The app can lock itself at the door in one specific situation: a brand-new (or
half-seeded) project where every profile is PENDING. Only an active HOD can approve
a profile, and nobody here is one yet. This script settles that with the service
account you already have, because it writes the same fields the API would:

    python scripts/grant_access.py --list
    python scripts/grant_access.py --email hod@sbjit.edu.in --password 'Hiera@2026'
    python scripts/grant_access.py --email new@sbjit.edu.in --password 'x' --department AIML

``--list`` is read-only and answers "which accounts exist, who is active, which
department do they point at". The write path is idempotent: running it twice changes
nothing the second time. Passwords are bcrypt-hashed exactly like /auth/register -
sign-in compares that hash, so the login form accepts the account even if Firebase
Auth itself never heard of it.
"""
import argparse
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth.password import get_password_hash, verify_password  # noqa: E402
from app.config.settings import settings                    # noqa: E402

DEFAULT_DEPARTMENT = "CSE (Artificial Intelligence & Machine Learning)"
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
REVIEW_ROLES = {"HOD", "ADMIN", "PRINCIPAL"}


def connect():
    """Firestore client built from the project's own service-account file."""
    import firebase_admin
    from firebase_admin import credentials, firestore

    key_path = Path(settings.credentials_path())
    if not key_path.exists():
        raise SystemExit(
            f"No service-account file at {key_path} . Run this from backend/, or set "
            "FIREBASE_PRIVATE_KEY_PATH=/full/path/to/firebase-credentials.json."
        )
    app = firebase_admin.initialize_app(credentials.Certificate(str(key_path)))
    return firestore.client(), getattr(app, "project_id", "?")


def _rows(collection, db):
    return [dict(doc.to_dict(), _id=doc.id) for doc in db.collection(collection).stream()]


def _password_matches(plain, hashed):
    """True when the stored hash is already this password (bcrypt salts differ each run)."""
    try:
        return verify_password(plain, hashed)
    except ValueError:
        return False


def _norm(email):
    return (email or "").strip().lower()


def find_user(db, email):
    wanted = _norm(email)
    for row in _rows("users", db):
        if _norm(row.get("email")) == wanted:
            return row
    return None


def department_label(dept):
    return f"{dept.get('name') or dept['_id']}  (id={dept['_id']}, code={dept.get('code') or '-'})"


def resolve_department(db, wanted):
    """Match a department by id, invite code or a case-insensitive fragment of its name."""
    depts = _rows("departments", db)
    if not wanted:
        return (depts[0] if len(depts) == 1 else None), depts
    needle = wanted.strip().lower()
    exact = [d for d in depts if d["_id"].lower() == needle
             or str(d.get("code", "")).lower() == needle]
    matches = exact or [d for d in depts if needle in (d.get("name") or "").lower()]
    if len(matches) == 1:
        return matches[0], depts
    if len(matches) > 1:
        raise SystemExit(
            f"'{wanted}' matches {len(matches)} departments - be more specific:\n  "
            + "\n  ".join(department_label(d) for d in matches)
        )
    raise SystemExit(
        f"No department matching '{wanted}'. Existing:\n  "
        + ("\n  ".join(department_label(d) for d in depts) or "  (none)")
    )


def new_code(db):
    taken = {str(d.get("code", "")) for d in _rows("departments", db)}
    while True:
        code = "".join(CODE_ALPHABET[b % len(CODE_ALPHABET)] for b in uuid.uuid4().bytes[:8])
        if code not in taken:
            return code


def list_accounts(db):
    depts = _rows("departments", db)
    by_id = {d["_id"]: d for d in depts}
    users = _rows("users", db)
    print(f"  {len(users)} account(s):")
    if not users:
        print("    (the 'users' collection is empty - nobody has registered yet)")
    for row in sorted(users, key=lambda u: (u.get("role") or "", _norm(u.get("email")))):
        dept = by_id.get(row.get("department_id"))
        where = dept.get("name") if dept else (row.get("department_id") or "none")
        flag = "" if row.get("hashed_password") else "   <- no password on file, cannot sign in"
        print(f"    {(row.get('email') or '?'):34} {str(row.get('role') or '-'):10} "
              f"{str(row.get('status') or '-'):8} {(where or '-')!s:20.20}{flag}")
    print(f"\n  {len(depts)} department(s):")
    for d in depts:
        hod = next((u for u in users if d.get("hod_id") in (u["_id"], u.get("id"))), None)
        print(f"    {department_label(d)}  hod={(hod or {}).get('email') or d.get('hod_id') or 'unclaimed'}")
    if not depts:
        print("    (none - the first account has to claim one)")
    print("\nSign-in compares the bcrypt hash stored on the profile, so an account created in the\n"
          "Firebase console alone cannot log in until this script or /auth/register gives it one.")
    return 0


def grant(db, email, password, name, role, wanted_department, create_missing, take_department):
    email = _norm(email)
    if not email:
        raise SystemExit("--email is required")
    users_ref = db.collection("users")
    row = find_user(db, email)
    changes = []

    dept, depts = resolve_department(db, wanted_department)
    if dept is None and not depts and create_missing:
        dept_id = str(uuid.uuid4())
        code = new_code(db)
        db.collection("departments").document(dept_id).set({
            "id": dept_id,
            "name": DEFAULT_DEPARTMENT,
            "code": code,
            "hod_id": None,
            "is_hod": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        dept = {"_id": dept_id, "name": DEFAULT_DEPARTMENT, "code": code, "hod_id": None}
        changes.append(f"created department '{DEFAULT_DEPARTMENT}' - invite code {code}")
    elif dept is None and not depts:
        raise SystemExit("No department exists yet - re-run with --create-department to make one.")
    elif dept is None:
        raise SystemExit(
            f"{len(depts)} departments exist; pick one with --department <id|code|name>:\n  "
            + "\n  ".join(department_label(d) for d in depts)
        )

    patch = {
        "email": email,
        "status": "ACTIVE",
        "role": role,
        "department_id": dept["_id"],
        "hashed_password": get_password_hash(password),
        "is_hod": role in REVIEW_ROLES,
    }
    if name:
        patch["name"] = name
    if row and _password_matches(password, row.get("hashed_password") or ""):
        patch.pop("hashed_password")   # keep the existing hash, so a re-run changes nothing

    if row:
        doc_id = row["_id"]
        for field, value in patch.items():
            if row.get(field) != value:
                changes.append(f"{field}: {str(row.get(field))!r} -> {value!r}")
        users_ref.document(doc_id).set(dict(patch, id=row.get("id") or doc_id), merge=True)
        print(f"Repaired the existing profile {doc_id}.")
    else:
        doc_id = str(uuid.uuid4())
        patch.update({
            "id": doc_id,
            "name": name or email.split("@")[0].replace(".", " ").replace("_", " ").title(),
            "designation": "Assistant Professor",
            "area_of_interest": None,
            "joining_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "association": "Regular",
            "avatar_url": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        users_ref.document(doc_id).set(patch)
        _mirror_in_firebase_auth(email, password, patch["name"])
        print(f"Created the profile {doc_id}.")

    # A department with no head is a department nobody can approve anyone into.
    if role in REVIEW_ROLES and not dept.get("hod_id"):
        db.collection("departments").document(dept["_id"]).set({"hod_id": doc_id}, merge=True)
        changes.append(f"department '{dept.get('name')}': hod_id was empty, now this account")
    elif role in REVIEW_ROLES and dept.get("hod_id") not in (None, doc_id):
        if take_department:
            db.collection("departments").document(dept["_id"]).set({"hod_id": doc_id}, merge=True)
            changes.append(f"department '{dept.get('name')}': HOD moved onto this account")
        else:
            holder = next((u for u in _rows("users", db) if u["_id"] == dept["hod_id"]), None)
            print(f"Left the department's own HOD alone ({(holder or {}).get('email') or dept['hod_id']}). "
                  "Pass --take-department only if you mean to move it.")

    print("\n" + ("Changes applied:" if changes else "Nothing to change - the account already had this "
                  "password, role and department."))
    for line in changes:
        print(f"  - {line}")
    print(f"\nSign in with:\n  {email}  /  {password}")
    return 0


def _mirror_in_firebase_auth(email, password, name):
    """Best effort: keep Firebase Auth in step, but never fail the run over it."""
    try:
        from firebase_admin import auth as firebase_auth

        firebase_auth.create_user(email=email, password=password, display_name=name)
        print(f"Also created the Firebase Auth user {email}.")
    except Exception as error:  # noqa: BLE001 - signing in does not depend on this
        print(f"(No Firebase Auth user: {error.__class__.__name__}: {str(error)[:110]}. "
              "Fine - the app signs people in from the department database.)")


def main():
    parser = argparse.ArgumentParser(
        description="Create or repair a HieraSync account straight in Firestore.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  python scripts/grant_access.py --list\n"
            "  python scripts/grant_access.py --email hod@sbjit.edu.in --password 'Hiera@2026'\n"
            "  python scripts/grant_access.py --email new@sbjit.edu.in --password 'x' --department AIML\n"
        ),
    )
    parser.add_argument("--list", action="store_true", help="print every account and department; changes nothing")
    parser.add_argument("--email", help="account to create or repair")
    parser.add_argument("--password", help="password for it (bcrypt-hashed, never stored as text)")
    parser.add_argument("--name", help="display name for a new profile")
    parser.add_argument("--role", default="HOD",
                        choices=sorted(REVIEW_ROLES | {"FACULTY", "TEACHER", "STUDENT", "COORDINATOR"}),
                        help="role to grant (default HOD, so the account can approve people)")
    parser.add_argument("--department", help="department id, invite code, or a fragment of its name")
    parser.add_argument("--create-department", action="store_true",
                        help="create the default AIML department when none exists")
    parser.add_argument("--take-department", action="store_true",
                        help="move an already-claimed department's HOD role onto this account")
    args = parser.parse_args()

    db, project = connect()
    print(f"Project: {project}\n")

    if args.list:
        return list_accounts(db)
    if not args.email or not args.password:
        raise SystemExit("Pass --email and --password (or run --list first to see what is there).")
    return grant(db, args.email, args.password, args.name, args.role.upper(), args.department,
                 args.create_department, args.take_department)


if __name__ == "__main__":
    sys.exit(main())
