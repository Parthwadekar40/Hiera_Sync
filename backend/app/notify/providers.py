"""Concrete delivery providers.

Every provider degrades gracefully: when its credentials are absent the engine falls
back to `DevOutboxProvider`, which persists a real, inspectable artifact (RFC-822 .eml
for mail, .txt for SMS/WhatsApp) plus a delivery record. That keeps the whole automation
pipeline demonstrable, testable and auditable offline, and the switch to production is
purely configuration - no code path changes.
"""

from __future__ import annotations

import base64
import json
import os
import smtplib
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from typing import Any, Dict, List, Optional

from app.notify.base import (
    BaseProvider,
    DeliveryResult,
    OutboundMessage,
    ProviderError,
    truncate,
)


class DevOutboxProvider(BaseProvider):
    """File-based sink used when a live channel is unconfigured (or NOTIFY_FORCE_DEV)."""

    def __init__(self, settings_obj: Any, channel: str = "email"):
        super().__init__(settings_obj)
        self.channel = channel
        self.name = f"dev-outbox:{channel}"

    def is_configured(self) -> bool:
        return True

    def enabled(self) -> bool:
        return True

    def _dir(self) -> str:
        path = os.path.join(self.settings.NOTIFY_DEV_OUTBOX_DIR, self.channel)
        os.makedirs(path, exist_ok=True)
        return path

    def send(self, msg: OutboundMessage) -> DeliveryResult:
        start = time.time()
        stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
        safe_to = re_sub(msg.to)
        fname = f"{stamp}-{safe_to}-{msg.kind}"
        if msg.channel == "email":
            eml = build_eml(msg, self.settings)
            with open(os.path.join(self._dir(), fname + ".eml"), "w", encoding="utf-8") as fh:
                fh.write(eml)
            with open(os.path.join(self._dir(), fname + ".html"), "w", encoding="utf-8") as fh:
                fh.write(msg.html or f"<pre>{msg.text}</pre>")
        else:
            with open(os.path.join(self._dir(), fname + ".txt"), "w", encoding="utf-8") as fh:
                fh.write(f"TO: {msg.to}\nSUBJECT: {msg.subject}\n\n{msg.text}\n")
        with open(os.path.join(self._dir(), fname + ".json"), "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "channel": msg.channel,
                    "to": msg.to,
                    "subject": msg.subject,
                    "text": msg.text,
                    "kind": msg.kind,
                    "severity": msg.severity,
                    "user_id": msg.user_id,
                    "meta": msg.meta,
                    "written_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                },
                fh,
                indent=2,
            )
        return DeliveryResult(
            ok=True,
            channel=msg.channel,
            provider=self.name,
            to=msg.to,
            simulated=True,
            latency_ms=int((time.time() - start) * 1000),
            detail=f"var/outbox/{msg.channel}/{fname}",
        )


def re_sub(value: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in (value or "anon"))[-40:] or "anon"


def build_eml(msg: OutboundMessage, settings: Any) -> str:
    """Render a full RFC-822 message (used by both the SMTP and the dev providers)."""
    lines = [
        f"From: {formataddr((settings.MAIL_FROM_NAME, settings.MAIL_FROM))}",
        f"To: <{msg.to}>",
        f"Subject: {settings.MAIL_SUBJECT_PREFIX} {msg.subject}".strip(),
        f"Message-ID: {make_msgid(domain='hierasync.local')}",
        "Date: " + time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime()),
        "MIME-Version: 1.0",
        'Content-Type: text/plain; charset="utf-8"',
        "Content-Transfer-Encoding: 7bit",
        "",
        msg.text or "",
        "",
        "-- HieraSync automated notification · kind=" + msg.kind + " --",
    ]
    return "\n".join(lines)


class SmtpEmailProvider(BaseProvider):
    channel = "email"
    name = "smtp"

    def is_configured(self) -> bool:
        return bool(self.settings.SMTP_HOST)

    def enabled(self) -> bool:
        return bool(self.settings.SMTP_ENABLED and self.is_configured())

    def _connect(self):
        s = self.settings
        host, port = s.SMTP_HOST, int(s.SMTP_PORT or (465 if s.SMTP_SECURITY == "ssl" else 587))
        if s.SMTP_SECURITY == "ssl":
            ctx = ssl.create_default_context()
            return smtplib.SMTP_SSL(host, port, timeout=s.SMTP_TIMEOUT, context=ctx)
        smtp = smtplib.SMTP(host, port, timeout=s.SMTP_TIMEOUT)
        # Gmail/Office365 over IPv6 can hang; bind to v4 when requested.
        if s.SMTP_LOCAL_ADDRESS:
            try:
                smtp.sock = socket.create_connection((host, port), timeout=s.SMTP_TIMEOUT, source_address=(s.SMTP_LOCAL_ADDRESS, 0))
            except OSError:  # pragma: no cover
                pass
        if s.SMTP_SECURITY == "starttls":
            smtp.ehlo()
            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()
        if s.SMTP_USERNAME:
            smtp.login(s.SMTP_USERNAME, s.SMTP_PASSWORD)
        return smtp

    def _compose(self, msg: OutboundMessage) -> EmailMessage:
        s = self.settings
        em = EmailMessage()
        em["From"] = formataddr((s.MAIL_FROM_NAME, s.MAIL_FROM))
        em["To"] = msg.to
        em["Subject"] = f"{s.MAIL_SUBJECT_PREFIX} {msg.subject}".strip()
        if s.MAIL_REPLY_TO:
            em["Reply-To"] = s.MAIL_REPLY_TO
        em["X-HieraSync-Kind"] = msg.kind
        em["X-HieraSync-Severity"] = msg.severity
        em.set_content(msg.text or msg.subject)
        if s.MAIL_HTML and msg.html:
            em.add_alternative(msg.html, subtype="html")
        return em

    def send(self, msg: OutboundMessage) -> DeliveryResult:
        if not msg.to or "@" not in msg.to:
            return DeliveryResult(ok=False, channel="email", provider=self.name, to=msg.to, error="invalid recipient address")
        start = time.time()
        em = self._compose(msg)
        try:
            smtp = self._connect()
            try:
                smtp.send_message(em)
            finally:
                try:
                    smtp.quit()
                except Exception:
                    pass
        except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError, socket.timeout, TimeoutError, OSError) as exc:
            raise ProviderError(f"smtp transport error: {exc}") from exc
        except smtplib.SMTPAuthenticationError as exc:
            return DeliveryResult(ok=False, channel="email", provider=self.name, to=msg.to, error=f"smtp auth rejected: {exc}")
        except smtplib.SMTPRecipientsRefused as exc:
            return DeliveryResult(ok=False, channel="email", provider=self.name, to=msg.to, error=f"recipient refused: {exc}")
        except smtplib.SMTPException as exc:
            raise ProviderError(f"smtp protocol error: {exc}") from exc
        return DeliveryResult(
            ok=True,
            channel="email",
            provider=self.name,
            to=msg.to,
            external_id=em.get("Message-ID"),
            latency_ms=int((time.time() - start) * 1000),
            detail="queued by smtp relay",
        )


class TwilioSmsProvider(BaseProvider):
    channel = "sms"
    name = "twilio-sms"

    def is_configured(self) -> bool:
        s = self.settings
        return bool(s.TWILIO_ACCOUNT_SID and s.TWILIO_AUTH_TOKEN and (s.TWILIO_FROM_NUMBER or s.TWILIO_MESSAGING_SERVICE_SID))

    def enabled(self) -> bool:
        return bool(self.settings.SMS_ENABLED and self.is_configured())

    def _endpoint(self) -> str:
        return f"https://api.twilio.com/2010-04-01/Accounts/{self.settings.TWILIO_ACCOUNT_SID}/Messages.json"

    def send(self, msg: OutboundMessage) -> DeliveryResult:
        if not msg.to:
            return DeliveryResult(ok=False, channel="sms", provider=self.name, to=msg.to, error="no phone number on file")
        start = time.time()
        body = truncate(msg.text or msg.subject, self.settings.NOTIFY_SMS_MAX_CHARS)
        form: Dict[str, str] = {"To": msg.to, "Body": body}
        if self.settings.TWILIO_MESSAGING_SERVICE_SID:
            form["MessagingServiceSid"] = self.settings.TWILIO_MESSAGING_SERVICE_SID
        else:
            form["From"] = self.settings.TWILIO_FROM_NUMBER
        return _twilio_post(self.settings, self._endpoint(), form, msg.channel, self.name, start)


class MetaWhatsAppProvider(BaseProvider):
    """Meta (WhatsApp Business) Cloud API - template or free-form session messages."""

    channel = "whatsapp"
    name = "meta-whatsapp-cloud"

    def is_configured(self) -> bool:
        s = self.settings
        return bool(s.WHATSAPP_ACCESS_TOKEN and s.WHATSAPP_PHONE_NUMBER_ID)

    def enabled(self) -> bool:
        return bool(self.settings.WHATSAPP_ENABLED and self.is_configured())

    def _endpoint(self) -> str:
        return f"https://graph.facebook.com/{self.settings.WHATSAPP_GRAPH_VERSION}/{self.settings.WHATSAPP_PHONE_NUMBER_ID}/messages"

    def send(self, msg: OutboundMessage) -> DeliveryResult:
        if not msg.to:
            return DeliveryResult(ok=False, channel="whatsapp", provider=self.name, to=msg.to, error="no WhatsApp number on file")
        start = time.time()
        body = truncate(msg.text or msg.subject, self.settings.NOTIFY_WHATSAPP_MAX_CHARS)
        payload: Dict[str, Any] = {"messaging_product": "whatsapp", "to": msg.to.lstrip("+")}
        template_name = (msg.meta or {}).get("whatsapp_template")
        if template_name:
            payload["type"] = "template"
            payload["template"] = {
                "name": template_name,
                "language": {"code": self.settings.WHATSAPP_TEMPLATE_LANGUAGE},
                "components": [
                    {
                        "type": "body",
                        "parameters": [{"type": "text", "text": line} for line in body.split("\n")[:5]]
                        or [{"type": "text", "text": msg.subject or "Notification"}],
                    }
                ],
            }
        else:
            payload["type"] = "text"
            payload["text"] = {"preview_url": False, "body": body}

        req = urllib.request.Request(
            self._endpoint(),
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {self.settings.WHATSAPP_ACCESS_TOKEN}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read().decode()
            data = json.loads(raw or "{}")
            ext = ((data.get("messages") or [{}])[0]).get("id")
            return DeliveryResult(ok=True, channel="whatsapp", provider=self.name, to=msg.to, external_id=ext, latency_ms=int((time.time() - start) * 1000), detail="accepted by Meta Graph API")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode()[:400] if hasattr(exc, "read") else str(exc)
            retryable = exc.code in (429, 500, 502, 503, 504) or "rate" in detail.lower()
            if retryable:
                raise ProviderError(f"whatsapp transient {exc.code}: {detail}") from exc
            return DeliveryResult(ok=False, channel="whatsapp", provider=self.name, to=msg.to, error=f"graph api {exc.code}: {detail}")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ProviderError(f"whatsapp network error: {exc}") from exc


class TwilioWhatsAppProvider(TwilioSmsProvider):
    name = "twilio-whatsapp"
    channel = "whatsapp"

    def is_configured(self) -> bool:
        s = self.settings
        return bool(s.WHATSAPP_TWILIO_FROM and s.TWILIO_ACCOUNT_SID and s.TWILIO_AUTH_TOKEN)

    def enabled(self) -> bool:
        return bool(self.settings.WHATSAPP_ENABLED and self.is_configured())

    def send(self, msg: OutboundMessage) -> DeliveryResult:
        if not msg.to:
            return DeliveryResult(ok=False, channel="whatsapp", provider=self.name, to=msg.to, error="no WhatsApp number on file")
        start = time.time()
        body = truncate(msg.text or msg.subject, self.settings.NOTIFY_WHATSAPP_MAX_CHARS)
        form = {"To": f"whatsapp:{msg.to}", "From": self.settings.WHATSAPP_TWILIO_FROM, "Body": body}
        return _twilio_post(self.settings, self._endpoint(), form, "whatsapp", self.name, start)


def _twilio_post(settings: Any, url: str, form: Dict[str, str], channel: str, provider: str, start: float) -> DeliveryResult:
    data = urllib.parse.urlencode(form).encode()
    token = base64.b64encode(f"{settings.TWILIO_ACCOUNT_SID}:{settings.TWILIO_AUTH_TOKEN}".encode()).decode()
    req = urllib.request.Request(url, data=data, headers={"Authorization": f"Basic {token}"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode() or "{}")
        return DeliveryResult(
            ok=True,
            channel=channel,
            provider=provider,
            to=form.get("To", ""),
            external_id=payload.get("sid"),
            latency_ms=int((time.time() - start) * 1000),
            detail=payload.get("status", "queued"),
        )
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()[:400] if hasattr(exc, "read") else str(exc)
        if exc.code in (429, 500, 502, 503, 504):
            raise ProviderError(f"twilio transient {exc.code}: {detail}") from exc
        return DeliveryResult(ok=False, channel=channel, provider=provider, to=form.get("To", ""), error=f"twilio {exc.code}: {detail}")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ProviderError(f"twilio network error: {exc}") from exc


class WebhookProvider(BaseProvider):
    """Generic outbound webhook (MS Teams / Slack / college ERP listener)."""

    channel = "webhook"
    name = "webhook"

    def __init__(self, settings_obj: Any, url: str = ""):
        super().__init__(settings_obj)
        self.url = url or getattr(settings_obj, "WEBHOOK_URL", "")

    def is_configured(self) -> bool:
        return bool(self.url)

    def enabled(self) -> bool:
        return self.is_configured()

    def send(self, msg: OutboundMessage) -> DeliveryResult:
        start = time.time()
        body = json.dumps(
            {
                "text": f"{msg.subject}\n{msg.text}",
                "kind": msg.kind,
                "severity": msg.severity,
                "user_id": msg.user_id,
                "meta": msg.meta,
            }
        ).encode()
        req = urllib.request.Request(self.url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp.read()
            return DeliveryResult(ok=True, channel="webhook", provider=self.name, to=self.url, latency_ms=int((time.time() - start) * 1000), detail="2xx")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            raise ProviderError(f"webhook error: {exc}") from exc


def build_providers(settings: Any) -> Dict[str, List[BaseProvider]]:
    """Ordered provider chains per channel; first configured+enabled wins."""
    return {
        "email": [SmtpEmailProvider(settings), DevOutboxProvider(settings, "email")],
        "sms": [TwilioSmsProvider(settings), DevOutboxProvider(settings, "sms")],
        "whatsapp": (
            [MetaWhatsAppProvider(settings), TwilioWhatsAppProvider(settings), DevOutboxProvider(settings, "whatsapp")]
            if getattr(settings, "WHATSAPP_PROVIDER", "meta") == "meta"
            else [TwilioWhatsAppProvider(settings), MetaWhatsAppProvider(settings), DevOutboxProvider(settings, "whatsapp")]
        ),
        "webhook": [WebhookProvider(settings), DevOutboxProvider(settings, "webhook")],
    }


def provider_status(settings: Any) -> Dict[str, Dict[str, Any]]:
    """Human/JSON-readable report of which sender will actually be used."""
    out: Dict[str, Dict[str, Any]] = {}
    for channel, chain in build_providers(settings).items():
        # A real sender only counts when it is configured AND is not the dev sink.
        active = next(
            (p for p in chain if p.enabled() and p.is_configured() and not isinstance(p, DevOutboxProvider)),
            None,
        )
        fallback = next((p for p in chain if isinstance(p, DevOutboxProvider)), None)
        chosen = active or fallback
        out[channel] = {
            "channel": channel,
            "will_use": chosen.name if chosen else "none",
            "live": bool(active),
            "simulated_only": active is None,
            "chain": [p.describe() for p in chain],
        }
    return out
