import datetime as dt
import typing as t

# LEFT="⬅️"
# RIGHT="➡️"

_OCLOCK = ["🕛", "🕐", "🕑", "🕒", "🕓", "🕔", "🕕", "🕖", "🕗", "🕘", "🕙", "🕚"]
_THIRTY = ["🕧", "🕜", "🕝", "🕞", "🕟", "🕠", "🕡", "🕢", "🕣", "🕤", "🕥", "🕦"]


def maybe_datetime_to_clock(value: t.Optional[dt.datetime]) -> t.Optional[str]:
    if value is None:
        return None
    if value.minute < 30:
        mapping = _OCLOCK
    else:
        mapping = _THIRTY
    return mapping[value.hour % 12]
