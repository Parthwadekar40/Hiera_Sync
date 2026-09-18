"""Per-channel message templates (subject / plain text / branded HTML / WhatsApp).

Templates are pure functions of (kind, context) so they can be unit-tested, rendered in
the API preview, and reused by the digest builder without touching providers.
"""

from __future__ import annotations

from typing import Any, Dict, List

BRAND = "#4f46e5"
SEVERITY_COLOR = {"CRITICAL": "#b91c1c", "HIGH": "#ea580c", "MEDIUM": "#0369a1", "LOW": "#4b5563"}
SEVERITY_ICON = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🔵", "LOW": "⚪"}

TITLE_BY_KIND = {
    "task_assigned": "New task assigned",
    "deadline_reminder": "Deadline approaching",
    "deadline_risk": "Deadline risk alert",
    "task_overdue": "Task overdue",
    "task_completed": "Task completed",
    "revision_required": "Revision requested",
    "approval_request": "Approval awaiting your decision",
    "approval_approved": "Approval granted",
    "approval_rejected": "Approval rejected",
    "approval_escalated": "Approval escalated",
    "approval_sla_breach": "Approval SLA breached",
    "join_request_new": "Department join request",
    "join_approved": "Join request approved",
    "join_rejected": "Join request declined",
    "event_reminder": "Event reminder",
    "goal_checkin": "Goal progress check-in",
    "daily_digest": "Your daily briefing",
    "weekly_report": "Weekly department report",
    "escalation": "Escalation notice",
    "system_alert": "System notice",
    "ai_insight": "HieraSync insight",
}

CTA_BY_KIND = {
    "task_assigned": "/tasks",
    "deadline_reminder": "/tasks",
    "deadline_risk": "/tasks",
    "task_overdue": "/tasks",
    "task_completed": "/tasks",
    "revision_required": "/tasks",
    "approval_request": "/approvals",
    "approval_approved": "/approvals",
    "approval_rejected": "/approvals",
    "approval_escalated": "/approvals",
    "approval_sla_breach": "/approvals",
    "join_request_new": "/join",
    "join_approved": "/dashboard",
    "join_rejected": "/join",
    "event_reminder": "/calendar",
    "goal_checkin": "/goals",
    "daily_digest": "/dashboard",
    "weekly_report": "/reports",
    "escalation": "/tasks",
    "system_alert": "/settings",
    "ai_insight": "/ai",
}


def _bullet_lines(lines: List[str]) -> str:
    return "\n".join(f"  • {ln}" for ln in lines if ln)


def _html(settings: Any, *, subject: str, intro: str, facts: Dict[str, Any], severity: str, cta_url: str, footer_note: str = "") -> str:
    rows = "".join(
        f"""<tr><td style="padding:6px 12px;color:#6b7280;font:13px/1.5 Arial,sans-serif;white-space:nowrap">{k}</td>
        <td style="padding:6px 12px;color:#111827;font:13px/1.5 Arial,sans-serif"><b>{v}</b></td></tr>"""
        for k, v in facts.items()
        if v not in (None, "", [])
    )
    color = SEVERITY_COLOR.get(severity.upper(), "#0369a1")
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:24px;background:#f3f4f6;font-family:Arial,Helvetica,sans-serif">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">
<table role="presentation" width="560" cellpadding="0" cellspacing="0" style="max-width:560px;background:#fff;border-radius:14px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.08)">
  <tr><td style="background:{BRAND};padding:16px 22px">
    <span style="color:#fff;font:600 15px/1.4 Arial,sans-serif;letter-spacing:.3px">◆ HIERASYNC</span>
    <div style="color:#e0e7ff;font:12px/1.4 Arial,sans-serif">{getattr(settings, 'INSTITUTION', 'Campus Operations')}</div>
  </td></tr>
  <tr><td style="padding:22px">
    <div style="display:inline-block;background:{color};color:#fff;font:600 11px/1 Arial;padding:5px 9px;border-radius:999px;letter-spacing:.4px">{SEVERITY_ICON.get(severity.upper(), '🔔')} {severity.upper()}</div>
    <h1 style="margin:14px 0 6px;font:600 19px/1.35 Arial,sans-serif;color:#111827">{subject}</h1>
    <p style="margin:0 0 16px;font:14px/1.6 Arial,sans-serif;color:#374151">{intro}</p>
    <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="background:#f9fafb;border-radius:10px;border:1px solid #e5e7eb">{rows}</table>
    <p style="margin:20px 0 6px;text-align:center">
      <a href="{cta_url}" style="display:inline-block;background:{BRAND};color:#fff;text-decoration:none;font:600 14px/1 Arial;padding:12px 22px;border-radius:9px">Open HieraSync →</a>
    </p>
  </td></tr>
  <tr><td style="padding:14px 22px;background:#f9fafb;border-top:1px solid #e5e7eb">
    <div style="font:11px/1.6 Arial,sans-serif;color:#6b7280">{footer_note or 'Automated notification - please do not reply to this email. Channel routing, quiet hours and digests are configurable in Settings → Notifications.'}</div>
  </td></tr>
</table></td></tr></table></body></html>"""


def render(settings: Any, *, kind: str, severity: str, ctx: Dict[str, Any]) -> Dict[str, str]:
    """Return {subject, text, html, whatsapp} for one notification."""
    sev_up = (severity or "MEDIUM").upper()
    icon = SEVERITY_ICON.get(sev_up, "🔔")
    label = ctx.get("title") or TITLE_BY_KIND.get(kind, kind.replace("_", " ").title())
    body = ctx.get("message") or ""
    facts = dict(ctx.get("facts") or {})

    subject = ctx.get("subject") or f"{icon} {TITLE_BY_KIND.get(kind, label)}"
    if kind != "daily_digest" and label and label not in subject:
        subject = f"{subject}: {label}" if len(label) < 90 else subject

    lines: List[str] = [body or TITLE_BY_KIND.get(kind, ""), ""]
    for key, val in facts.items():
        lines.append(f"{key}: {val}")
    cta_path = CTA_BY_KIND.get(kind, "/dashboard")
    cta_url = f"{str(getattr(settings, 'APP_PUBLIC_URL', '')).rstrip('/')}{cta_path}"
    lines += ["", f"Action required → {cta_url}"]
    text = "\n".join([ln for ln in lines if ln is not None]).strip()

    html = _html(
        settings,
        subject=label if kind != "daily_digest" else "Daily briefing",
        intro=body or TITLE_BY_KIND.get(kind, ""),
        facts=facts,
        severity=sev_up,
        cta_url=cta_url,
        footer_note=ctx.get("footer"),
    )

    # WhatsApp/SMS need to be scannable on a lock screen: label + 3 facts + link.
    short = [f"*{TITLE_BY_KIND.get(kind, label)}*", body]
    for key, val in list(facts.items())[:4]:
        short.append(f"{key}: {val}")
    short.append(cta_url)
    whatsapp = "\n".join([s for s in short if s])

    return {"subject": subject, "text": text, "html": html, "whatsapp": whatsapp}


def digest_body(items: List[Dict[str, Any]], settings: Any) -> Dict[str, str]:
    """Aggregate several pending alerts into one digest message."""
    buckets: Dict[str, List[str]] = {"Overdue": [], "Due today": [], "Upcoming": [], "Approvals": [], "Other": []}
    for it in items:
        kind = it.get("kind", "other")
        line = f"- {it.get('title', 'Item')}: {str(it.get('message', '')).splitlines()[0][:110]}"
        if kind in ("task_overdue", "escalation"):
            buckets["Overdue"].append(line)
        elif kind == "deadline_reminder" and it.get("facts", {}).get("Days left") in (0, "0"):
            buckets["Due today"].append(line)
        elif kind in ("deadline_reminder", "deadline_risk", "task_assigned"):
            buckets["Upcoming"].append(line)
        elif "approval" in kind or kind in ("join_request_new",):
            buckets["Approvals"].append(line)
        else:
            buckets["Other"].append(line)

    blocks = [f"Good morning. Here is your HieraSync briefing for {len(items)} item(s)."]
    for name, lines in buckets.items():
        if lines:
            blocks.append(f"\n{name} ({len(lines)})\n" + "\n".join(lines))
    if len(blocks) == 1:
        blocks.append("Nothing needs your attention right now. Enjoy the day.")
    text = "\n".join(blocks)
    url = f"{str(getattr(settings, 'APP_PUBLIC_URL', '')).rstrip('/')}/dashboard"
    facts = {k: len(v) for k, v in buckets.items() if v}
    return render(
        settings,
        kind="daily_digest",
        severity="LOW",
        ctx={"title": "Daily briefing", "message": text, "facts": facts, "subject": f"📋 HieraSync daily briefing ({len(items)})"},
    )
