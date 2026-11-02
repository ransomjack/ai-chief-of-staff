"""Time helpers. Everything is stored in UTC; everything shown to the owner is in
his own time zone (IST by default)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# WhatsApp lets a business reply freely for 24 hours after the user's last message.
# We keep a small safety margin.
WINDOW = timedelta(hours=23, minutes=50)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_when(value: str, tz_name: str) -> datetime:
    """Parse an ISO 8601 date or date-time. A value without an offset is read in the
    owner's time zone; a bare date means 9 AM local. Returns an aware UTC datetime."""
    value = value.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(value)
    if len(value) == 10:  # YYYY-MM-DD
        dt = dt.replace(hour=9)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(tz_name))
    return dt.astimezone(timezone.utc)


def to_iso(dt: datetime) -> str:
    """Fixed-format UTC string, so string comparison equals time comparison."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def from_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def fmt_local(dt: datetime, tz_name: str) -> str:
    local = dt.astimezone(ZoneInfo(tz_name))
    return local.strftime("%a %d %b, %I:%M %p").replace(" 0", " ")


def local_now_text(now: datetime, tz_name: str) -> str:
    local = now.astimezone(ZoneInfo(tz_name))
    return local.strftime("%A %d %B %Y, %I:%M %p ") + tz_name


def window_open(last_inbound_iso: str | None, now: datetime) -> bool:
    if not last_inbound_iso:
        return False
    return now - from_iso(last_inbound_iso) < WINDOW
