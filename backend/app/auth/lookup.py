"""
Email lookups for the ``users`` collection.

Sign-up used to store the address exactly as it was typed, so a profile saved as
``Hod@SBJIT.edu.in`` never matched a lowercase login - the API answered
"Incorrect email or password" while the password was perfectly correct. Emails are
normalised on write now; this module keeps every read path working for the rows
that were created before that, so nobody is locked out of an existing account.
"""
from typing import Any, Dict, Optional

from google.cloud.firestore import Client


def normalize_email(email: Optional[str]) -> str:
    """Trim and lowercase - the form every comparison uses."""
    return (email or "").strip().lower()


def find_user_by_email(db: Client, email: Optional[str]) -> Optional[Dict[str, Any]]:
    """Return the profile document for ``email``, whatever case it was stored in."""
    wanted = normalize_email(email)
    if not wanted:
        return None

    users_ref = db.collection("users")
    # Exactly as typed first (that is how older rows were written), then normalised.
    for value in dict.fromkeys([email.strip(), wanted]):
        docs = list(users_ref.where("email", "==", value).limit(1).stream())
        if docs:
            return _with_id(docs[0])

    # Legacy row stored with different casing or with stray spaces around it.
    for doc in users_ref.stream():
        if normalize_email(doc.to_dict().get("email")) == wanted:
            return _with_id(doc)
    return None


def _with_id(doc) -> Dict[str, Any]:
    """Profile payload, guaranteed to carry the id of the document it came from."""
    data = doc.to_dict()
    data.setdefault("id", doc.id)
    return data


def user_exists(db: Client, email: Optional[str]) -> bool:
    return find_user_by_email(db, email) is not None
