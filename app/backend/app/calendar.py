from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")


def market_now() -> datetime:
    return datetime.now(tz=EASTERN)


def nearest_friday_on_or_after(d: date) -> date:
    offset = (4 - d.weekday()) % 7
    return d + timedelta(days=offset)


def current_expiry() -> date:
    now = market_now()
    today = now.date()
    friday = nearest_friday_on_or_after(today)
    if today == friday and now.hour >= 16:
        friday = friday + timedelta(days=7)
    return friday


def most_recent_completed_session(now: datetime | None = None) -> date:
    if now is None:
        now = market_now()
    d = now.date()
    if now.hour < 16:
        d = d - timedelta(days=1)
    while d.weekday() >= 5:
        d = d - timedelta(days=1)
    return d
