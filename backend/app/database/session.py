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


def _enable_memory_mode(reason: str) -> None:
    global db, using_memory_db

    db = get_memory_client()
    using_memory_db = True
    logger.warning(
        f"{reason} — serving an in-memory demo database. Data resets on restart; "
        "put a valid firebase-credentials.json in backend/ to persist it."
    )


def init_firebase():
    global db, using_memory_db

    if firebase_admin._apps:
        db = firestore.client()
        using_memory_db = False
        return

    try:
        if os.path.exists(settings.FIREBASE_PRIVATE_KEY_PATH):
            logger.info(
                f"Initializing Firebase using {settings.FIREBASE_PRIVATE_KEY_PATH}"
            )

            cred = credentials.Certificate(settings.FIREBASE_PRIVATE_KEY_PATH)

            firebase_admin.initialize_app(cred, {"projectId": settings.FIREBASE_PROJECT_ID})
        else:
            logger.warning(
                "Firebase credentials file not found. Using default credentials."
            )

            firebase_admin.initialize_app(
                options={
                    "projectId": settings.FIREBASE_PROJECT_ID
                }
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
