"""Channel-agnostic message + provider contracts."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

CHANNEL_INAPP = "inapp"
CHANNEL_EMAIL = "email"
CHANNEL_SMS = "sms"
CHANNEL_WHATSAPP = "whatsapp"
ALL_CHANNELS = [CHANNEL_INAPP, CHANNEL_EMAIL, CHANNEL_SMS, CHANNEL_WHATSAPP]

SEVERITIES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
SEVERITY_RANK = {s: i for i, s in enumerate(SEVERITIES)}


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso(dt: Optional[datetime] = None) -> str:
    return (dt or now_utc()).isoformat(timespec="seconds")


def severity_rank(sev: str) -> int:
    return SEVERITY_RANK.get((sev or "MEDIUM").upper(), 1)


def truncate(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 12)].rstrip() + " …[trunc]"


def normalize_phone(raw: str, default_country: str = "+91") -> str:
    """Best-effort E.164 normalization for Twilio / Meta Graph API payloads.

    '0 98765 43210', '+91-98765-43210', '9876543210', '919876543210' -> '+919876543210'
    """
    if not raw:
        return ""
    digits = re.sub(r"[^\d+]", "", str(raw))
    if digits.startswith("00"):
        digits = "+" + digits[2:]
    if digits.startswith("+"):
        return digits if len(digits) >= 8 else ""
    digits = re.sub(r"\D", "", digits)
    if not digits:
        return ""
    cc = re.sub(r"\D", "", default_country) or "91"
    # Indian/UK style trunk prefix: "098765 43210" -> drop the leading 0 before the CC.
    if digits.startswith("0") and not digits.startswith("00"):
        digits = digits.lstrip("0")
    if digits.startswith(cc) and len(digits) >= 11:
        return "+" + digits
    if len(digits) == 10:  # national format
        return "+" + cc + digits
    return "+" + digits


@dataclass
class OutboundMessage:
    channel: str
    to: str
    subject: str = ""
    text: str = ""
    html: str = ""
    kind: str = "generic"
    severity: str = "MEDIUM"
    user_id: str = ""
    meta: Dict[str, Any] = field(default_factory=dict)

    def preview(self, size: int = 300) -> str:
        body = " ".join(filter(None, [self.subject, self.text]))
        return body[:size]


@dataclass
class DeliveryResult:
    ok: bool
    channel: str
    provider: str
    to: str
    external_id: Optional[str] = None
    error: Optional[str] = None
    latency_ms: int = 0
    simulated: bool = False
    detail: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "channel": self.channel,
            "provider": self.provider,
            "to": self.to,
            "external_id": self.external_id,
            "error": self.error,
            "latency_ms": self.latency_ms,
            "simulated": self.simulated,
            "detail": self.detail,
        }


class ProviderError(RuntimeError):
    """Raised by providers for retryable delivery failures."""


class BaseProvider:
    channel: str = "generic"
    name: str = "base"

    def __init__(self, settings_obj: Any):
        self.settings = settings_obj

    def is_configured(self) -> bool:  # pragma: no cover - overridden
        return False

    def enabled(self) -> bool:  # pragma: no cover - overridden
        return True

    def send(self, message: OutboundMessage) -> DeliveryResult:  # pragma: no cover
        raise NotImplementedError

    # ---- shared guards
    def describe(self) -> Dict[str, Any]:
        return {
            "channel": self.channel,
            "provider": self.name,
            "configured": self.is_configured(),
            "enabled": self.enabled(),
        }
