"""Daily reporting boundaries shared by first-party and YouTube reports."""
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

PACIFIC = ZoneInfo('America/Los_Angeles')


def today_window():
    day = datetime.now(PACIFIC).date()
    start = datetime.combine(day, time.min, PACIFIC).astimezone(timezone.utc)
    end = datetime.combine(day + timedelta(days=1), time.min, PACIFIC).astimezone(timezone.utc)
    return day.isoformat(), start.isoformat(), end.isoformat()
