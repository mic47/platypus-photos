from __future__ import annotations

import datetime as dt
import enum
import json
import typing as t

from dataclasses import dataclass

from pphoto.data_model.base import StorableData
from pphoto.data_model.face import Position

T = t.TypeVar("T")


@dataclass
class ManualLocation(StorableData):
    latitude: float
    longitude: float
    address_name: t.Optional[str]
    address_country: t.Optional[str]

    def to_json_dict(self) -> t.Any:
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "address_name": self.address_name,
            "address_country": self.address_country,
        }

    @staticmethod
    def from_json_dict(d: t.Dict[str, t.Any]) -> ManualLocation:
        return ManualLocation(
            float(d["latitude"]),
            float(d["longitude"]),
            d.get("address_name"),
            d.get("address_country"),
        )

    @staticmethod
    def from_json_bytes(x: bytes) -> ManualLocation:
        return ManualLocation.from_json_dict(json.loads(x))

    @staticmethod
    def current_version() -> int:
        return 0


@dataclass
class ManualText(StorableData):
    tags: t.List[str]
    description: t.List[str]

    @staticmethod
    def from_json_dict(d: t.Dict[str, t.Any]) -> ManualText:
        return ManualText(d["tags"], d["description"])

    @staticmethod
    def from_json_bytes(x: bytes) -> ManualText:
        return ManualText.from_json_dict(json.loads(x))

    def to_json_dict(self) -> t.Any:
        return {"tags": self.tags, "description": self.description}

    @staticmethod
    def current_version() -> int:
        return 0


class IdentitySkipReason(enum.Enum):
    NOT_FACE = "not_face"  # noqa: F841
    NOT_POI = "not_poi"  # noqa: F841


@dataclass
class ManualIdentity:
    identity: t.Optional[str]
    skip_reason: t.Optional[IdentitySkipReason]
    position: Position

    def to_json_dict(self) -> t.Any:
        return {
            "identity": self.identity,
            "skip_reason": None if self.skip_reason is None else self.skip_reason.value,
            "position": self.position.to_json_dict(),
        }

    @staticmethod
    def from_json_dict(d: t.Dict[str, t.Any]) -> ManualIdentity:
        skip_reason = d.get("skip_reason")
        return ManualIdentity(
            d.get("identity"),
            None if skip_reason is None else IdentitySkipReason(skip_reason),
            Position.from_json_dict(d["position"]),
        )


@dataclass
class ManualIdentities(StorableData):
    identities: t.List[ManualIdentity]

    def to_json_dict(self) -> t.Any:
        return {"identities": [x.to_json_dict() for x in self.identities]}

    @staticmethod
    def from_json_dict(d: t.Dict[str, t.Any]) -> ManualIdentities:
        identities = d["identities"]
        assert isinstance(identities, list)
        return ManualIdentities([ManualIdentity.from_json_dict(x) for x in identities])

    @staticmethod
    def from_json_bytes(x: bytes) -> ManualIdentities:
        return ManualIdentities.from_json_dict(json.loads(x))

    @staticmethod
    def current_version() -> int:
        return 0


@dataclass
class ManualDate(StorableData):
    date: t.Optional[dt.datetime]

    def to_json_dict(self) -> t.Any:
        return {
            "date": None if self.date is None else self.date.timestamp(),
        }

    @staticmethod
    def from_json_dict(d: t.Dict[str, t.Any]) -> ManualDate:
        date = d["date"]
        return ManualDate(None if date is None else dt.datetime.fromtimestamp(date))

    @staticmethod
    def from_json_bytes(x: bytes) -> ManualDate:
        return ManualDate.from_json_dict(json.loads(x))

    @staticmethod
    def current_version() -> int:
        return 0
