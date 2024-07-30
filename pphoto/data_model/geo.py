from __future__ import annotations

import json
import typing as t

from dataclasses import dataclass

from pphoto.data_model.base import StorableData

T = t.TypeVar("T")


@dataclass
class GeoAddress(StorableData):
    address: str
    country: t.Optional[str]
    name: t.Optional[str]
    raw: str
    query: str
    # TODO: add points of interestis -- i.e. home, work, ...

    def to_json_dict(self) -> t.Any:
        return {
            "address": self.address,
            "country": self.country,
            "name": self.name,
            "raw": self.raw,
            "query": self.query,
        }

    @staticmethod
    def current_version() -> int:
        return 0

    @staticmethod
    def from_json_dict(d: t.Dict[str, t.Any]) -> GeoAddress:
        return GeoAddress(
            d["address"],
            d.get("country"),
            d.get("name"),
            d["raw"],
            d["query"],
        )

    @staticmethod
    def from_json_bytes(x: bytes) -> GeoAddress:
        return GeoAddress.from_json_dict(json.loads(x))
