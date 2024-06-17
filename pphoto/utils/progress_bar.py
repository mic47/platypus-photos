from __future__ import annotations

import typing as t

from tqdm import tqdm

_POSITION = 0


def _get_position() -> int:
    # pylint: disable = global-statement
    global _POSITION
    ret = _POSITION
    _POSITION += 1
    return ret


class ProgressBar:
    def __init__(self, desc: t.Optional[str] = None, permanent: bool = False, smoothing: float = 0.3) -> None:
        position = None
        if permanent:
            position = _get_position()
        self._tqdm = tqdm(desc=desc, position=position, smoothing=smoothing)
        self._progress = 0
        self._total = 0

    def update(self, value: int) -> ProgressBar:
        self._progress += value
        self._tqdm.update(value)
        return self

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
        self._tqdm.reset(total=self._total)
        self._tqdm.update(self._progress)
        self._tqdm.refresh()
        return self
