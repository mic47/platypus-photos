import typing as t
from datetime import datetime


def maybe_datetime_to_timestamp(value: t.Optional[datetime]) -> t.Optional[float]:
    if value is None:
        return None
    return value.timestamp()


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
