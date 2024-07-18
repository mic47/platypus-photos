import datetime as dt
import typing as t

from dataclasses import dataclass

from dataclasses_json import DataClassJsonMixin

from pphoto.data_model.base import HasCurrentVersion
from pphoto.data_model.face import Position

T = t.TypeVar("T")


@dataclass
class ManualLocation(HasCurrentVersion):
    latitude: float
    longitude: float
    address_name: t.Optional[str]
    address_country: t.Optional[str]

    @staticmethod
    def current_version() -> int:
        return 0


@dataclass
class ManualText(HasCurrentVersion):
    tags: t.List[str]
    description: t.List[str]

    @staticmethod
    def current_version() -> int:
        return 0


@dataclass
class ManualIdentity(DataClassJsonMixin):
    identity: t.Optional[str]
    skip_reason: t.Optional[str]
    position: Position


@dataclass
class ManualIdentities(HasCurrentVersion):
    identities: t.List[ManualIdentity]

    @staticmethod
    def current_version() -> int:
        return 0


@dataclass
class ManualDate(HasCurrentVersion):
    date: t.Optional[dt.datetime]

    @staticmethod
    def current_version() -> int:
        return 0
