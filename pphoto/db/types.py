from __future__ import annotations

from dataclasses import dataclass
import typing as t


T = t.TypeVar("T")
E = t.TypeVar("E")


@dataclass
class FeaturePayload(t.Generic[T, E]):
    payload: t.Optional[T]
    error: t.Optional[E]
    version: int
    last_update: int
    rowid: int


class InternalError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(f"Internal error, this si bug: {message}")
