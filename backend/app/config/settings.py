"""Central application configuration for HieraSync.

Everything is environment-driven (12-factor). The module is intentionally the single
source of truth for credentials, delivery policy, scheduling and persistence so that
deployment differences never leak into business logic.

Backward compatibility: legacy names (FIREBASE_*, SECRET_KEY, ALGORITHM, ...) are kept,
so existing routers keep importing `app.config.settings.settings` unchanged.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator

try:  # pydantic-settings v2
    from pydantic_settings import BaseSettings, SettingsConfigDict

    _HAS_PS = True
except Exception:  # pragma: no cover - fallback for minimal installs
    from pydantic import BaseModel as BaseSettings  # type: ignore

    _HAS_PS = False


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


class Settings(BaseSettings):
    # ----------------------------------------------------------------- identity
    PROJECT_NAME: str = "HieraSync"
    API_TITLE: str = "HieraSync API"
    INSTITUTION: str = "SBJIT Campus"
    APP_VERSION: str = "2.0.0"
    DESCRIPTION: str = (
        "Hierarchical academic workflow synchronization platform: task orchestration, "
        "heuristic AI deadline-risk engine, multi-stage approvals, analytics and "
        "multi-channel notification automation."
    )

    # --------------------------------------------------------------- persistence
    # auto      -> Firestore when credentials exist, otherwise local store
    # sqlite    -> force the embedded Firestore-compatible document store
    # firestore -> force Google Cloud Firestore
    DATABASE_BACKEND: str = "auto"
    SQLITE_PATH: str = "var/hierasync.db"

    FIREBASE_PROJECT_ID: str = _env("FIREBASE_PROJECT_ID", "hiera-sync")
    FIREBASE_PRIVATE_KEY_PATH: str = _env(
        "FIREBASE_PRIVATE_KEY_PATH", "firebase-credentials.json"
    )
    FIRESTORE_DATABASE: str = "(default)"

    # ------------------------------------------------------------------ security
    SECRET_KEY: str = _env("SECRET_KEY", "dev-only-insecure-secret-change-me")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 720
    PASSWORD_MIN_LENGTH: int = 8
    BCROUNDS: int = 12

    # ---------------------------------------------------------------------- cors
    CORS_ORIGINS: str = "*"

    # --------------------------------------------------------------------- logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = ""  # empty -> stdout only

    # ----------------------------------------------------------------------- ai/ml
    GEMINI_API_KEY: str = _env("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = "gemini-1.5-flash"
    AI_ENABLED: bool = True  # deterministic heuristics always work offline

    # --------------------------------------------------------- scheduler / automation
    SCHEDULER_ENABLED: bool = True
    NOTIFY_TIMEZONE: str = "Asia/Kolkata"
    # UTC offset in minutes used when tz database is unavailable (IST = +330)
    NOTIFY_TZ_OFFSET_MINUTES: int = 330
    OUTBOX_POLL_SECONDS: int = 60
    RISK_SWEEP_MINUTES: int = 15
    APPROVAL_SLA_MINUTES: int = 30

    DEADLINE_REMINDER_TIMES: str = "08:00"
    OVERDUE_ESCALATION_TIME: str = "09:00"
    DIGEST_DAILY_TIME: str = "08:05"
    WEEKLY_REPORT_TIME: str = "Mon:07:00"
    RETENTION_PURGE_TIME: str = "02:00"

    # --------------------------------------------------------------- notification core
    NOTIFY_ENABLED: bool = True
    NOTIFY_INAPP_ENABLED: bool = True
    NOTIFY_FAIL_SOFT: bool = True  # a failed send must never break a business txn
    NOTIFY_MAX_ATTEMPTS: int = 4
    NOTIFY_BACKOFF_BASE_SECONDS: int = 60  # 60s, 2m, 4m, 8m (+ jitter)
    NOTIFY_BACKOFF_MAX_SECONDS: int = 3600
    NOTIFY_JITTER_SECONDS: int = 15
    NOTIFY_DEDUPE_MINUTES: int = 360  # suppress identical alert within window
    NOTIFY_RATE_LIMIT_PER_MIN: int = 40  # per provider, protects free tiers
    NOTIFY_RETENTION_DAYS: int = 90
    NOTIFY_SMS_MAX_CHARS: int = 480  # ~3 SMS segments
    NOTIFY_WHATSAPP_MAX_CHARS: int = 1600

    # Channel policy: which channels each severity must use. Overridable via env as JSON.
    POLICY_CRITICAL: str = "inapp,email,sms,whatsapp"
    POLICY_HIGH: str = "inapp,email,sms,whatsapp"
    POLICY_MEDIUM: str = "inapp,email"
    POLICY_LOW: str = "inapp"

    DEFAULT_QUIET_HOURS: str = "22:30-07:00"  # local; critical always breaks through
    NOTIFY_DEV_OUTBOX_DIR: str = "var/outbox"
    BROADCAST_TARGETS: str = "HOD,ADMIN,PRINCIPAL"  # recipients of 'department' alerts

    # ------------------------------------------------------------------------ email
    SMTP_ENABLED: bool = True
    SMTP_HOST: str = _env("SMTP_HOST", "")
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = _env("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = _env("SMTP_PASSWORD", "")
    SMTP_SECURITY: str = "starttls"  # none | starttls | ssl
    SMTP_TIMEOUT: int = 20
    SMTP_LOCAL_ADDRESS: str = ""  # for IPv4-forced hosts (Gmail on some VPS)
    MAIL_FROM: str = _env("MAIL_FROM", "no-reply@hierasync.local")
    MAIL_FROM_NAME: str = "HieraSync Automation"
    MAIL_REPLY_TO: str = ""
    MAIL_SUBJECT_PREFIX: str = "[HieraSync]"
    MAIL_HTML: bool = True
    MAIL_EMBED_TEXT_PLAIN: bool = True

    # ------------------------------------------------------------------- sms (twilio)
    SMS_ENABLED: bool = True
    TWILIO_ACCOUNT_SID: str = _env("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN: str = _env("TWILIO_AUTH_TOKEN", "")
    TWILIO_FROM_NUMBER: str = _env("TWILIO_FROM_NUMBER", "")
    TWILIO_MESSAGING_SERVICE_SID: str = ""
    SMS_PROVIDER: str = "twilio"  # twilio | messagebird | mock

    # ------------------------------------------------------------------- whatsapp
    WHATSAPP_ENABLED: bool = True
    WHATSAPP_PROVIDER: str = "meta"  # meta | twilio
    WHATSAPP_ACCESS_TOKEN: str = _env("WHATSAPP_ACCESS_TOKEN", "")
    WHATSAPP_PHONE_NUMBER_ID: str = _env("WHATSAPP_PHONE_NUMBER_ID", "")
    WHATSAPP_TWILIO_FROM: str = _env("WHATSAPP_TWILIO_FROM", "")  # whatsapp:+15005550001
    WHATSAPP_TEMPLATE_LANGUAGE: str = "en_US"
    WHATSAPP_GRAPH_VERSION: str = "v21.0"
    # Business-initiated WhatsApp requires approved template names per message kind
    WHATSAPP_TEMPLATES: str = (
        '{"deadline_risk":"risk_alert","task_overdue":"task_overdue",'
        '"approval_request":"approval_request","escalation":"escalation",'
        '"daily_digest":"daily_digest","default":"generic_alert"}'
    )

    # ------------------------------------------------------------ misc / demo helpers
    SEED_DEMO_DATA: bool = True
    DEMO_PASSWORD: str = "HierSync@123"
    STATIC_DIR: str = ""  # e.g. "../frontend/dist" to serve the SPA from FastAPI
    APP_PUBLIC_URL: str = "http://localhost:5173"  # used inside notification links

    # --------------------------------------------------------------- risk engine knobs
    RISK_OVERDUE_CAP: int = 45
    RISK_URGENCY_CAP: int = 25
    RISK_STAGNATION_CAP: int = 15
    RISK_LOAD_CAP: int = 20
    RISK_DEPENDENCY_CAP: int = 12

    @field_validator("DATABASE_BACKEND")
    @classmethod
    def _norm_backend(cls, v: str) -> str:
        v = (v or "auto").strip().lower()
        return v if v in {"auto", "sqlite", "firestore"} else "auto"

    # ------------------------------------------------------------------- helpers
    @property
    def cors_origin_list(self) -> List[str]:
        raw = (self.CORS_ORIGINS or "*").strip()
        return ["*"] if raw in {"*", ""} else [o.strip() for o in raw.split(",") if o.strip()]

    @property
    def broadcast_roles(self) -> List[str]:
        return [r.strip().upper() for r in (self.BROADCAST_TARGETS or "").split(",") if r.strip()]

    def policy_for(self, severity: str) -> List[str]:
        table = {
            "CRITICAL": self.POLICY_CRITICAL,
            "HIGH": self.POLICY_HIGH,
            "MEDIUM": self.POLICY_MEDIUM,
            "LOW": self.POLICY_LOW,
        }
        raw = table.get((severity or "MEDIUM").upper(), self.POLICY_MEDIUM)
        return [c.strip().lower() for c in raw.split(",") if c.strip()]

    @property
    def firestore_credentials_present(self) -> bool:
        return bool(self.FIREBASE_PRIVATE_KEY_PATH) and os.path.exists(
            self.FIREBASE_PRIVATE_KEY_PATH
        )

    @property
    def channel_status(self) -> dict:
        """Which real delivery channels are usable right now."""
        return {
            "inapp": {"enabled": self.NOTIFY_INAPP_ENABLED, "configured": True, "provider": "firestore/sqlite store"},
            "email": {
                "enabled": self.SMTP_ENABLED,
                "configured": bool(self.SMTP_HOST and self.MAIL_FROM),
                "provider": f"smtp:{self.SMTP_HOST or 'unset'}:{self.SMTP_PORT}/{self.SMTP_SECURITY}",
            },
            "sms": {
                "enabled": self.SMS_ENABLED,
                "configured": bool(self.TWILIO_ACCOUNT_SID and self.TWILIO_AUTH_TOKEN and (self.TWILIO_FROM_NUMBER or self.TWILIO_MESSAGING_SERVICE_SID)),
                "provider": self.SMS_PROVIDER,
            },
            "whatsapp": {
                "enabled": self.WHATSAPP_ENABLED,
                "configured": bool(
                    (self.WHATSAPP_PROVIDER == "meta" and self.WHATSAPP_ACCESS_TOKEN and self.WHATSAPP_PHONE_NUMBER_ID)
                    or (self.WHATSAPP_PROVIDER == "twilio" and self.WHATSAPP_TWILIO_FROM and self.TWILIO_ACCOUNT_SID)
                ),
                "provider": self.WHATSAPP_PROVIDER,
            },
            "dev_outbox": {"enabled": True, "configured": True, "provider": f"file:{self.NOTIFY_DEV_OUTBOX_DIR}"},
        }

    if _HAS_PS:
        model_config = SettingsConfigDict(
            env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
        )
    else:  # pragma: no cover

        class Config:
            env_file = ".env"
            extra = "ignore"


@lru_cache
def _load() -> Settings:
    return Settings()


try:  # pydantic v1 style: instances are not immutable, so a plain module singleton is fine
    settings: Settings = _load()
except Exception:  # pragma: no cover
    settings = Settings()  # type: ignore
