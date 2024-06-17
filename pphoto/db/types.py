from __future__ import annotations

from dataclasses import dataclass
import typing as t

from pphoto.data_model.base import HasCurrentVersion, WithMD5

T = t.TypeVar("T")
E = t.TypeVar("E")


@dataclass
class FeaturePayload(t.Generic[T, E]):
    payload: t.Optional[T]
    error: t.Optional[E]
    version: int
    last_update: int
    rowid: int


Ser = t.TypeVar("Ser", bound=HasCurrentVersion)


class Cache(t.Generic[Ser]):
    def get(self, key: str) -> t.Optional[FeaturePayload[WithMD5[Ser], None]]:
        raise NotImplementedError

    def add(self, data: WithMD5[Ser]) -> WithMD5[Ser]:
        raise NotImplementedError


class NoCache(t.Generic[Ser], Cache[Ser]):
    def get(self, key: str) -> t.Optional[FeaturePayload[WithMD5[Ser], None]]:
        pass

    def add(self, data: WithMD5[Ser]) -> WithMD5[Ser]:
        return data
