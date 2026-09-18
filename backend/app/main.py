"""HieraSync AI - FastAPI application entry point.

Three-tier cloud stack from the design doc (Slide 10): Tier 1 React SPA, Tier 2 this
service, Tier 3 Firestore (or the embedded document store for offline/CI runs).
"""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.api.router import api_router
from app.config.settings import settings
from app.database.session import active_backend, backend_info, get_db, init_db
from app.scheduler.jobs import scheduler_status, start_scheduler, stop_scheduler
from app.utils.logging import logger

# Firestore-specific exception handlers are optional: the app must boot even where the
# cloud SDK is absent (offline mode / CI containers).
_GOOGLE_HANDLERS: tuple = ()
try:  # pragma: no cover - environment dependent
    from google.api_core.exceptions import GoogleAPICallError, RetryError

    _GOOGLE_HANDLERS = (GoogleAPICallError, RetryError)
except Exception:  # pragma: no cover
    _GOOGLE_HANDLERS = ()


@asynccontextmanager
async def lifespan(app: FastAPI):
    started = time.time()
    logger.info(f"Starting {settings.PROJECT_NAME} API v{settings.APP_VERSION} ...")
    try:
        init_db()
    except Exception as exc:
        logger.error(f"persistence init failed ({exc}); falling back to embedded store")
        init_db(force="sqlite")

    db = get_db()
    seeded = None
    if settings.SEED_DEMO_DATA and active_backend() == "sqlite":
        try:
            from app.db.seed import seed_if_empty

            seeded = seed_if_empty(db)
        except Exception as exc:  # pragma: no cover
            logger.warning(f"seed skipped: {exc}")

    try:
        from app.engine.calibrate import calibrate_db

        report = calibrate_db(db, persist=True)
        if report.get("persisted"):
            logger.info(f"risk engine calibrated: AUC {report['auc_before']} -> {report['auc_after']} on {report['samples']} samples")
    except Exception as exc:  # pragma: no cover
        logger.debug(f"auto-calibration skipped: {exc}")

    start_scheduler()
    from app.notify.providers import provider_status

    live = [c for c, s in provider_status(settings).items() if s["live"]]
    logger.info(
        f"ready in {time.time() - started:.2f}s | backend={active_backend()} | "
        f"live channels={','.join(live) or 'none (dev outbox)'} | seed={seeded or 'skipped'}"
    )
    yield
    stop_scheduler()
    logger.info("shutdown complete.")


app = FastAPI(
    title=settings.API_TITLE,
    description=settings.DESCRIPTION,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-Id", "X-Elapsed-Ms"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    """Correlation id + latency header: makes the audit log joinable with web-server logs."""
    rid = request.headers.get("X-Request-Id") or uuid.uuid4().hex[:12]
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        elapsed = (time.perf_counter() - start) * 1000
        logger.exception(f"unhandled error on {request.method} {request.url.path} after {elapsed:.0f}ms [{rid}]")
        raise
    response.headers["X-Request-Id"] = rid
    response.headers["X-Elapsed-Ms"] = f"{(time.perf_counter() - start) * 1000:.1f}"
    return response


if _GOOGLE_HANDLERS:

    @app.exception_handler(_GOOGLE_HANDLERS[0])
    async def _google_api_handler(request: Request, exc):  # pragma: no cover
        logger.error(f"Google API Error: {exc}")
        return JSONResponse(status_code=503, content={"message": "Datastore temporarily unavailable. Try again shortly.", "detail": str(exc)[:200]})

    @app.exception_handler(_GOOGLE_HANDLERS[1])
    async def _google_retry_handler(request: Request, exc):  # pragma: no cover
        logger.error(f"Google API Retry Error: {exc}")
        return JSONResponse(status_code=503, content={"message": "Datastore retry budget exhausted.", "detail": str(exc)[:200]})


app.include_router(api_router, prefix="/api/v1")


@app.get("/", tags=["meta"])
def root():
    return {
        "platform": settings.PROJECT_NAME,
        "tagline": "Smart Academic Workflow & Event Management System",
        "institution": settings.INSTITUTION,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "openapi": "/openapi.json",
        "health": "/health",
        "persistence": active_backend(),
    }


@app.get("/health", tags=["meta"])
def health():
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "persistence": backend_info(),
        "scheduler": scheduler_status(),
    }


@app.get("/health/deep", tags=["meta"])
def health_deep(request: Request = None):
    """Everything an examiner checks before saying 'it runs': data, channels, jobs, RBAC."""
    from app.notify.queue import outbox_stats
    from app.notify.providers import provider_status
    from app.auth.rbac import matrix_table

    db = get_db()
    try:
        stats = db.stats() if hasattr(db, "stats") else {"firestore": "collection counts not enumerated"}
        doc = db.collection("tasks").limit(1)
        _ = len(list(doc.stream()))
        datastore = "ok"
    except Exception as exc:  # pragma: no cover
        datastore = f"degraded: {exc}"
    return {
        "status": "ok" if datastore == "ok" else "degraded",
        "datastore": datastore,
        "backend": active_backend(),
        "collections": stats,
        "outbox": outbox_stats(db),
        "channels": provider_status(settings),
        "scheduler": scheduler_status(),
        "roles_modelled": len(matrix_table()),
        "routers_mounted": len(app.routes),
    }


# ----------------------------------------------------------------- SPA hosting (optional)
if settings.STATIC_DIR:
    import os

    _static = os.path.abspath(settings.STATIC_DIR)
    _index = os.path.join(_static, "index.html")
    if os.path.exists(_index):

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa(full_path: str):
            """Serve the built React SPA so the whole product runs from one process."""
            candidate = os.path.join(_static, full_path)
            if full_path and os.path.isfile(candidate):
                return FileResponse(candidate)
            return FileResponse(_index)

        logger.info(f"Serving built SPA from {_static}")
    else:
        logger.warning(f"STATIC_DIR set to {settings.STATIC_DIR} but index.html missing; API-only mode")
