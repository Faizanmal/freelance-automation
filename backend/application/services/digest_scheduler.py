"""Timezone, DST, and scheduling engine for user-controlled notification delivery.

Preserves the independent hunt clock while delivering digests and alerts on each
user's local schedule with IANA timezone validation, DST spring-forward / fall-back
resilience, and restart/retry idempotency.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

DAY_ALIASES: dict[str, int] = {
    "mon": 0,
    "monday": 0,
    "tue": 1,
    "tues": 1,
    "tuesday": 1,
    "wed": 2,
    "wednesday": 2,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "thursday": 3,
    "fri": 4,
    "friday": 4,
    "sat": 5,
    "saturday": 5,
    "sun": 6,
    "sunday": 6,
}

DAY_NAMES: list[str] = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


def validate_iana_timezone(tz_name: str | None) -> str:
    """Validates that a timezone string is a recognized IANA timezone identifier.

    Raises:
        ValueError: if the timezone identifier is not valid.
    """
    if not tz_name or not str(tz_name).strip():
        return "UTC"
    cleaned = str(tz_name).strip()
    try:
        zone = ZoneInfo(cleaned)
        return zone.key
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"Invalid IANA timezone identifier: '{cleaned}'") from exc


def parse_digest_days(raw: list[Any] | None) -> set[int]:
    """Parses user-specified digest days into integer weekday set (0=Monday, 6=Sunday)."""
    if not raw:
        return {0, 1, 2, 3, 4}  # default: Monday-Friday
    days: set[int] = set()
    for item in raw:
        key = str(item).strip().lower()
        if key in DAY_ALIASES:
            days.add(DAY_ALIASES[key])
    return days or {0, 1, 2, 3, 4}


def parse_local_time(value: str | None) -> tuple[int, int]:
    """Parses 'HH:MM' string safely into (hour, minute)."""
    raw = (value or "09:00").strip()
    try:
        parts = raw.split(":", 1)
        hour = max(0, min(23, int(parts[0])))
        minute = max(0, min(59, int(parts[1])))
        return hour, minute
    except (TypeError, ValueError, IndexError):
        return 9, 0


def is_in_quiet_hours(
    local_time: time,
    start: time,
    end: time,
) -> bool:
    """Checks whether local_time falls inside a quiet hours window.

    Handles both daytime (e.g. 13:00 -> 14:00) and overnight (e.g. 22:00 -> 08:00) spans.
    """
    if start == end:
        return False
    if start < end:
        # Normal daytime window
        return start <= local_time <= end
    # Overnight window spanning midnight
    return local_time >= start or local_time <= end


def get_user_zone(timezone_name: str | None) -> ZoneInfo:
    """Returns ZoneInfo object, defaulting safely to UTC on invalid names."""
    try:
        return ZoneInfo((timezone_name or "UTC").strip() or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def is_digest_due(
    prefs: Any,
    *,
    now_local: datetime | None = None,
    now_utc: datetime | None = None,
    window_minutes: int = 30,
) -> bool:
    """Evaluates whether a digest should be dispatched to the user right now.

    Protections:
    1. Paused and Unsubscribed users are strictly skipped.
    2. Cadence & days of week respected.
    3. Checked against user's local date to guarantee at most ONE digest per local day,
       completely preventing duplicate sends on worker restart, retries, and fall-back DST.
    4. Handles spring-forward DST gap (skipped minutes) by permitting a catch-up window.
    """
    # 1. Unsubscribed / paused check
    if bool(getattr(prefs, "is_unsubscribed", False)):
        return False
    if bool(getattr(prefs, "is_paused", False)):
        return False
    if not bool(getattr(prefs, "digest_mode", True)):
        return False

    # 2. Resolve user timezone & local datetime
    tz = get_user_zone(getattr(prefs, "timezone", None))
    if now_local is not None:
        local_now = now_local if now_local.tzinfo else now_local.replace(tzinfo=tz)
    elif now_utc is not None:
        utc_dt = now_utc if now_utc.tzinfo else now_utc.replace(tzinfo=UTC)
        local_now = utc_dt.astimezone(tz)
    else:
        local_now = datetime.now(UTC).astimezone(tz)

    # 3. Check allowed delivery days
    days = parse_digest_days(getattr(prefs, "digest_days", None))
    if local_now.weekday() not in days:
        return False

    # 4. Check already sent today in user's current timezone
    last = getattr(prefs, "digest_last_sent_at", None) or getattr(
        prefs, "last_digest_at", None
    )
    if last is not None:
        try:
            last_dt = last if last.tzinfo else last.replace(tzinfo=UTC)
            last_local = last_dt.astimezone(tz)
            if (
                last_local.year == local_now.year
                and last_local.month == local_now.month
                and last_local.day == local_now.day
            ):
                # Already delivered today in user's local timezone.
                return False
        except (ValueError, TypeError, OverflowError):
            pass

    # 5. Calculate target time on user's current local date
    hour, minute = parse_local_time(getattr(prefs, "digest_time_local", None))
    try:
        target = local_now.replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
    except (ValueError, OverflowError):
        target = local_now.replace(hour=9, minute=0, second=0, microsecond=0)

    # 6. Evaluation with DST spring-forward resiliency:
    # If clock jumped forward over target (e.g. 02:00 -> 03:00 jump for a 02:30 target),
    # target is considered due on this date as long as local_now has arrived and is within 90m.
    seconds_diff = (local_now - target).total_seconds()
    if seconds_diff < 0:
        # Not yet arrived; permit early window up to window_minutes (e.g. 08:50 for 09:00 target)
        if abs(seconds_diff) <= window_minutes * 60:
            return True
        return False

    # Already reached or passed target time today
    # Permit send if within window_minutes OR within DST gap allowance (up to 90 min after target)
    max_lag = max(window_minutes * 60, 5400)
    return seconds_diff <= max_lag


def calculate_next_send(
    prefs: Any,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    """Calculates the upcoming scheduled digest dispatch time in user local and UTC time."""
    tz = get_user_zone(getattr(prefs, "timezone", None))
    now = (now_utc or datetime.now(UTC)).astimezone(tz)

    is_paused = bool(getattr(prefs, "is_paused", False))
    is_unsub = bool(getattr(prefs, "is_unsubscribed", False))
    digest_mode = bool(getattr(prefs, "digest_mode", True))

    hour, minute = parse_local_time(getattr(prefs, "digest_time_local", None))
    days = parse_digest_days(getattr(prefs, "digest_days", None))

    # Determine next local date that matches schedule
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    # Check if already sent today
    last = getattr(prefs, "digest_last_sent_at", None)
    already_sent_today = False
    if last is not None:
        last_dt = (last if last.tzinfo else last.replace(tzinfo=UTC)).astimezone(tz)
        if last_dt.date() == now.date():
            already_sent_today = True

    # Look ahead up to 14 days
    next_send_local: datetime | None = None
    for day_offset in range(14):
        test_dt = candidate + timedelta(days=day_offset)
        if day_offset == 0:
            if already_sent_today or now > test_dt:
                continue
        if test_dt.weekday() in days:
            next_send_local = test_dt
            break

    if next_send_local is None:
        next_send_local = candidate + timedelta(days=1)

    next_send_utc = next_send_local.astimezone(UTC)
    utc_offset = now.strftime("%z")
    formatted_offset = (
        f"{utc_offset[:3]}:{utc_offset[3:]}" if len(utc_offset) == 5 else utc_offset
    )

    dst_active = bool(now.dst() and now.dst() != timedelta(0))

    return {
        "timezone": tz.key,
        "current_local_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "utc_offset": formatted_offset,
        "dst_active": dst_active,
        "is_paused": is_paused,
        "is_unsubscribed": is_unsub,
        "digest_mode": digest_mode,
        "scheduled_time_local": f"{hour:02d}:{minute:02d}",
        "scheduled_days": [DAY_NAMES[d] for d in sorted(days)],
        "next_send_local": next_send_local.strftime("%Y-%m-%d %H:%M:%S"),
        "next_send_utc": next_send_utc.isoformat(),
    }
