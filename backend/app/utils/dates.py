"""Date helpers shared by the calendar (events) endpoints.

The collection has been written with two different date shapes over time:
ISO ("2026-09-05") and human ("05 August 2026"). Anything that is not ISO
breaks FullCalendar on the client and makes range filters useless, so every
event date is normalised here before it is stored or compared.
"""

from datetime import date, datetime, timedelta
from typing import Optional

MONTHS = {
    month.lower(): index
    for index, month in enumerate(
        [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ],
        start=1,
    )
}
for _name, _index in list(MONTHS.items()):
    MONTHS[_name[:3]] = _index


def to_iso_date(value: Optional[str], fallback: Optional[date] = None) -> str:
    """Best-effort conversion of any stored/formatted date into YYYY-MM-DD."""
    if not value:
        return (fallback or date.today()).isoformat()

    text = str(value).strip()
    if not text:
        return (fallback or date.today()).isoformat()

    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        pass

    parts = text.replace(",", " ").split()
    if len(parts) >= 3 and parts[0].isdigit():
        day = int(parts[0])
        month = MONTHS.get(parts[1].lower().rstrip("."))
        year = parts[2][:4]
        if month and year.isdigit():
            try:
                return date(int(year), month, day).isoformat()
            except ValueError:
                pass

    for pattern in ("%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(text, pattern).date().isoformat()
        except ValueError:
            continue

    return (fallback or date.today()).isoformat()


def shift_days(days: int, start: Optional[date] = None) -> str:
    return (start or date.today()).__add__(timedelta(days=days)).isoformat()


def is_valid_time(value: Optional[str]) -> bool:
    if not value:
        return True
    try:
        datetime.strptime(str(value)[:5], "%H:%M")
        return True
    except ValueError:
        return False


def clean_time(value: Optional[str]) -> Optional[str]:
    """Trim to HH:MM, or None when it is not a usable clock time."""
    if not value:
        return None
    text = str(value).strip()[:5]
    return text if is_valid_time(text) else None
