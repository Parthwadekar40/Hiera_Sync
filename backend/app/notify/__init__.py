"""Multi-channel notification engine: email, SMS, WhatsApp, in-app.

Layering
--------
routing.py    who must be told, over which channels, and when (policy + preferences)
templates.py  what it looks like per channel (subject/body/HTML/WhatsApp/SMS variants)
providers.py  how it physically leaves the building (SMTP, Twilio REST, Meta Graph API,
              and a file outbox so the platform is demonstrable with zero credentials)
queue.py      durability: SQLite/Firestore-backed outbox with dedupe, backoff, DLQ
engine.py     the facade every business module calls (single write path for all alerts)
"""
