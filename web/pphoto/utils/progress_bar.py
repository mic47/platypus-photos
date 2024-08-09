from __future__ import annotations

import dataclasses as dc
import typing as t

import dataclasses_json as dj
from tqdm import tqdm

_POSITION = 0


def _get_position() -> int:
    # pylint: disable-next = global-statement
    global _POSITION
    ret = _POSITION
    _POSITION += 1
    return ret


_PERMANENT_BARS: t.Dict[int, ProgressBar] = {}


@dc.dataclass
class ProgressBarProgress(dj.DataClassJsonMixin):
    desc: t.Optional[str]
    progress: int
    total: int
    rate: t.Optional[float]  # noqa: F841
    elapsed: t.Optional[float]  # noqa: F841


def get_bars() -> t.List[t.Tuple[int, ProgressBarProgress]]:
    return sorted([(k, v.get_progress()) for k, v in _PERMANENT_BARS.items()], key=lambda x: x[0])


class ProgressBar:
    def __init__(self, desc: t.Optional[str] = None, permanent: bool = False, smoothing: float = 0.3) -> None:
        position = None
        if permanent:
            position = _get_position()
            _PERMANENT_BARS[position] = self
        self._desc = desc
        self._tqdm = tqdm(desc=desc, position=position, smoothing=smoothing)
        self._progress = 0
        self._total = 0

    def update(self, value: int) -> ProgressBar:
        self._progress += value
        self._tqdm.update(value)
        return self

    def get_progress(self) -> ProgressBarProgress:
        self.update_total()
        dct = self._tqdm.format_dict
        return ProgressBarProgress(
            self._desc, self._progress, self._total, dct.get("rate"), dct.get("elapsed")
        )

    def add_to_total(self, value: int) -> ProgressBar:
        self._total += value
        return self

    def update_what_is_left(self, value: int) -> ProgressBar:
        missing = self._total - self._progress
        if missing != value:
            self._total = self._progress + value
            self.update_total()
        return self

    def refresh(self) -> ProgressBar:
        self._tqdm.refresh()
        return self

    def update_total(self) -> ProgressBar:
        self._tqdm.total = self._total
        self._tqdm.update(0)
        self._tqdm.refresh()
        return self
