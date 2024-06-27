import datetime as dt
import typing as t

from dataclasses import dataclass

from pphoto.data_model.base import HasCurrentVersion

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
class ManualDate(HasCurrentVersion):
    date: t.Optional[dt.datetime]

    @staticmethod
    def current_version() -> int:
        return 0
