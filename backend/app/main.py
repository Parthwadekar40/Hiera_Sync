from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import api_router
from app.scheduler.jobs import start_scheduler, stop_scheduler
from app.utils.logging import logger
from app.database.session import init_firebase
from fastapi.responses import JSONResponse
from app.config.settings import settings
import sys
from contextlib import asynccontextmanager
from google.api_core.exceptions import GoogleAPICallError, RetryError

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting HieraSync API...")
    init_firebase()
    start_scheduler()
    yield
    stop_scheduler()
    logger.info("CampusPulse API shutdown complete.")

app = FastAPI(
    title="HiéraSync AI API",
    description="SBJIT Nagpur — academic workflow, calendar & approvals API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
# Origins come from settings (CORS_ORIGINS in .env) - a wildcard combined with
# allow_credentials is rejected by browsers and is unsafe for production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")

@app.exception_handler(GoogleAPICallError)
async def google_api_exception_handler(request: Request, exc: GoogleAPICallError):
    logger.error(f"Google API Error: {exc}")
    return JSONResponse(
        status_code=503,
        content={"message": "Service temporarily unavailable due to backend failure."}
    )

@app.exception_handler(RetryError)
async def google_retry_exception_handler(request: Request, exc: RetryError):
    logger.error(f"Google API Retry Error: {exc}")
    return JSONResponse(
        status_code=503,
        content={"message": "Service temporarily unavailable due to backend failure."}
    )

@app.get("/")
async def root():
    return {"message": "HiéraSync AI API is running", "docs": "/docs"}
