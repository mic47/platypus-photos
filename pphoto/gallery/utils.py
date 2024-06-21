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
