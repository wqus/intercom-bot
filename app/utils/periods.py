from datetime import datetime, timedelta, timezone

TZ = timezone.utc


def get_today_range() -> tuple[datetime, datetime]:
    now = datetime.now(TZ)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, now


def get_yesterday_range() -> tuple[datetime, datetime]:
    now = datetime.now(TZ)
    end = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=1)
    return start, end


def get_week_range() -> tuple[datetime, datetime]:
    now = datetime.now(TZ)
    start = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return start, now


def get_month_range() -> tuple[datetime, datetime]:
    now = datetime.now(TZ)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return start, now