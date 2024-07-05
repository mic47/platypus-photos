import typing as t
from datetime import datetime


def maybe_datetime_to_timestamp(value: t.Optional[datetime]) -> t.Optional[float]:
    if value is None:
        return None
    return value.timestamp()
