from __future__ import annotations

import json
import traceback
import typing as t

from dataclasses import dataclass
from dataclasses_json import DataClassJsonMixin


class StorableData(t.Protocol):
    def to_json_dict(self) -> t.Any: ...
    @staticmethod
    def current_version() -> int: ...


@dataclass(frozen=True, eq=True)
class PathWithMd5:
    path: str
    md5: str


Ser = t.TypeVar("Ser", bound="StorableData")
T = t.TypeVar("T")


@dataclass
class Error(BaseException, DataClassJsonMixin):
    name: str
    message: t.Optional[str]
    traceback: t.Optional[str]

    def to_json_dict(self) -> object:
        return self.to_dict(encode_json=True)

    @staticmethod
    def from_exception(e: Exception) -> "Error":
        return Error(
            type(e).__name__,
            str(e),
            traceback.format_exc(),
        )


class WithMD5(t.Generic[Ser]):
    def __init__(self, md5: str, version: int, payload: t.Optional[Ser], e: t.Optional[Error]):
        self.md5 = md5
        self.version = version
        self.p = payload
        self.e = e

    def to_json(self) -> str:
        return json.dumps(
            {
                "p": None if self.p is None else self.p.to_json_dict(),
                "e": None if self.e is None else self.e.to_json_dict(),
                "md5": self.md5,
                "version": self.version,
            },
            ensure_ascii=False,
        )
