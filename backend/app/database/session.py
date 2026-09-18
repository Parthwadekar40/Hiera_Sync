"""Driver-selectable document-store access.

`get_db()` is the single dependency every router already uses, so switching between the
embedded store and Cloud Firestore is a deployment decision, not a code change.

    DATABASE_BACKEND=auto       Firestore when credentials exist, else embedded store
    DATABASE_BACKEND=sqlite     force embedded (offline dev, CI, demos, tests)
    DATABASE_BACKEND=firestore  force Cloud Firestore (fail fast if creds are missing)
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from app.config.settings import settings
from app.db.store import DocumentStore
from app.utils.logging import logger

_db: Any = None
_backend: Optional[str] = None  # "sqlite" | "firestore"


def _init_firestore() -> Optional[Any]:
    """Initialise firebase-admin and return a Firestore client, or None on failure."""
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
    except Exception as exc:  # pragma: no cover - SDK absent
        logger.warning(f"firebase-admin not importable: {exc}")
        return None

    try:
        if not firebase_admin._apps:
            if settings.firestore_credentials_present:
                logger.info(f"Initializing Firestore via {settings.FIREBASE_PRIVATE_KEY_PATH}")
                cred = credentials.Certificate(settings.FIREBASE_PRIVATE_KEY_PATH)
                firebase_admin.initialize_app(cred, {"projectId": settings.FIREBASE_PROJECT_ID})
            else:
                logger.warning("No service-account file found; trying Application Default Credentials.")
                firebase_admin.initialize_app(options={"projectId": settings.FIREBASE_PROJECT_ID})
        return firestore.client(database=settings.FIRESTORE_DATABASE)
    except Exception as exc:
        logger.error(f"Firestore initialization failed: {exc}")
        return None


def _init_sqlite() -> DocumentStore:
    path = settings.SQLITE_PATH
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    store = DocumentStore(path)
    logger.info(f"Embedded document store ready at {os.path.abspath(path)}")
    return store


def init_db(force: Optional[str] = None) -> Any:
    """Boot the persistence layer. Idempotent."""
    global _db, _backend

    if _db is not None and force is None:
        return _db

    mode = (force or settings.DATABASE_BACKEND or "auto").lower()

    if mode == "firestore":
        client = _init_firestore()
        if client is None:
            raise RuntimeError(
                "DATABASE_BACKEND=firestore but Firestore could not be initialised. "
                f"Provide {settings.FIREBASE_PRIVATE_KEY_PATH} or use DATABASE_BACKEND=sqlite."
            )
        _db, _backend = client, "firestore"
        return _db

    if mode == "sqlite":
        _db, _backend = _init_sqlite(), "sqlite"
        return _db

    # ---- auto: prefer the cloud when it is genuinely configured, else embedded
    if settings.firestore_credentials_present:
        client = _init_firestore()
        if client is not None:
            _db, _backend = client, "firestore"
            return _db
        logger.warning("Firestore configured but unavailable - falling back to embedded store.")
    _db, _backend = _init_sqlite(), "sqlite"
    return _db


def init_firebase() -> Any:
    """Backward-compatible alias kept for the existing lifespan hook."""
    return init_db()


def get_db() -> Any:
    global _db
    if _db is None:  # lazy safety net for scripts/tests that skip the lifespan hook
        init_db()
    if _db is None:  # pragma: no cover
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Persistence layer is not initialized.",
        )
    return _db


def active_backend() -> str:
    return _backend or "uninitialized"


def is_cloud() -> bool:
    return _backend == "firestore"


def backend_info() -> Dict[str, Any]:
    info: Dict[str, Any] = {"backend": active_backend()}
    if _backend == "sqlite":
        info["path"] = os.path.abspath(settings.SQLITE_PATH)
        try:
            info["collections"] = _db.stats()
        except Exception:  # pragma: no cover
            info["collections"] = {}
    elif _backend == "firestore":
        info["project"] = settings.FIREBASE_PROJECT_ID
        info["database"] = settings.FIRESTORE_DATABASE
    return info


def close_db() -> None:  # used by tests
    global _db, _backend
    try:
        if isinstance(_db, DocumentStore):
            _db.close()
    finally:
        _db = None
        _backend = None
