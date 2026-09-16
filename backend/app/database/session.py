import os

import firebase_admin
from firebase_admin import credentials, firestore
from fastapi import HTTPException, status  # noqa: F401  (kept for API compatibility)

from app.config.settings import settings
from app.database.memory import MemoryClient, get_memory_client
from app.utils.logging import logger

db = None

# True when the process is running on the volatile in-memory double instead of
# Firestore (missing/invalid service-account credentials).
using_memory_db = False

# Project the client is actually talking to, for /health and startup logs.
resolved_project_id = None


def _enable_memory_mode(reason: str) -> None:
    global db, using_memory_db

    db = get_memory_client()
    using_memory_db = True
    logger.warning(
        f"{reason} — serving an in-memory demo database. Data resets on restart; "
        "put a valid firebase-credentials.json in backend/ to persist it."
    )


def init_firebase():
    global db, using_memory_db, resolved_project_id

    if firebase_admin._apps:
        db = firestore.client()
        using_memory_db = False
        return

    key_path = settings.credentials_path()

    try:
        if key_path and os.path.exists(key_path):
            logger.info(f"Initializing Firebase using {key_path}")

            cred = credentials.Certificate(key_path)

            # Let the service-account file decide the project. Passing
            # settings.FIREBASE_PROJECT_ID here overrode it, so a stale value in
            # backend/.env ("my-firebase-project" by default) silently pointed the
            # app at a different - usually empty - Firestore database.
            resolved_project_id = getattr(cred, "project_id", None)
            expected = (settings.FIREBASE_PROJECT_ID or "").strip()
            if resolved_project_id:
                if expected and expected != resolved_project_id:
                    logger.warning(
                        f"FIREBASE_PROJECT_ID in .env is '{expected}' but the service-account "
                        f"file belongs to '{resolved_project_id}' - using '{resolved_project_id}'."
                    )
                logger.info(f"Firestore project: {resolved_project_id}")

            firebase_admin.initialize_app(cred)
        else:
            logger.warning(
                "No service-account file at "
                f"{key_path or settings.FIREBASE_PRIVATE_KEY_PATH!r} — trying Application "
                "Default Credentials. Put firebase-credentials.json in backend/ (or set "
                "FIREBASE_PRIVATE_KEY_PATH) to persist data."
            )

            resolved_project_id = settings.FIREBASE_PROJECT_ID
            firebase_admin.initialize_app(
                options={"projectId": resolved_project_id} if resolved_project_id else None
            )

        client = firestore.client()

        # Default credentials can look fine until the first RPC fails (no
        # GOOGLE_APPLICATION_CREDENTIALS, no metadata server), which would
        # surface as a 500 on every page. Probe once so we can fall back instead.
        try:
            list(client.collections())
        except Exception as probe_error:
            raise RuntimeError(
                f"Firestore is unreachable ({type(probe_error).__name__}: {probe_error})"
            ) from probe_error

        db = client
        using_memory_db = False
        logger.info("Firestore initialized successfully.")

    except Exception as e:
        logger.error(f"Failed to initialize Firebase: {e}")
        _enable_memory_mode("Firestore is not available")


def get_db():
    if db is None:
        # init_firebase() never ran (or failed before assigning db) - demo mode
        # beats a blanket 503 that makes every page look broken.
        _enable_memory_mode("Firestore was not initialised")

    return db


def is_memory_db() -> bool:
    return using_memory_db or isinstance(db, MemoryClient)
