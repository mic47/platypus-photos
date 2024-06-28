import typing as t
from datetime import datetime, time, timedelta


def maybe_datetime_to_date(value: t.Optional[datetime]) -> t.Optional[str]:
    if value is None:
        return None
    return f"{value.year}-{value.month:02d}-{value.day:02d}"


def maybe_datetime_to_time(value: t.Optional[datetime]) -> t.Optional[str]:
    if value is None:
        return None
    return f"{value.hour}:{value.minute:02d}:{value.second:02d}"


def maybe_datetime_to_day_start(value: t.Optional[datetime]) -> t.Optional[float]:
    if value is None:
        return None
    return datetime.combine(value.date(), time.min).timestamp()


def maybe_datetime_to_next_day_start(value: t.Optional[datetime]) -> t.Optional[float]:
    if value is None:
        return None
    return datetime.combine((value + timedelta(days=1)).date(), time.min).timestamp()


def maybe_datetime_to_timestamp(value: t.Optional[datetime]) -> t.Optional[float]:
    if value is None:
        return None
    return value.timestamp()


def format_diff_date(
    d1: t.Optional[datetime], d2: t.Optional[datetime], none_threshold: int = 60
) -> t.Optional[str]:
    if d1 is None or d2 is None:
        return None
    seconds = abs(int((d1 - d2).total_seconds()))
    return format_seconds_to_duration(seconds, none_threshold)


# pylint: disable-next = too-many-return-statements
def format_seconds_to_duration(seconds: float, none_threshold: int = -1) -> t.Optional[str]:
    seconds = int(seconds)
    if seconds < none_threshold:
        return None
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 100:
        return f"{minutes}m"
    hours = seconds // 3600
    if hours < 48:
        return f"{hours}h"
    days = seconds // 86400
    if days < 14:
        return f"{days}d"
    weeks = seconds // (86400 * 7)
    if weeks < 6:
        return f"{weeks}w"
    months = seconds // (86400 * 30)
    if months < 19:
        return f"{months}mon"
    years = seconds // (86400 * 365.25)
    return f"{years}y"
