import typing as t

from datetime import datetime
from dataclasses import dataclass
from dataclasses_json import DataClassJsonMixin

from pphoto.data_model.base import HasCurrentVersion

T = t.TypeVar("T")


@dataclass
class GPSCoord(DataClassJsonMixin):
    latitude: float
    longitude: float
    altitude: t.Optional[float]
    date: t.Optional[datetime]


@dataclass
class Camera(DataClassJsonMixin):
    make: str  # noqa: F841
    model: str
    serial_number: str  # noqa: F841
    software: str  # noqa: F841


@dataclass
class Date(DataClassJsonMixin):
    datetime: t.Optional[datetime]
    time_str: t.Optional[str]  # noqa: F841


@dataclass
class ImageExif(HasCurrentVersion):
    gps: t.Optional[GPSCoord]
    camera: Camera
    date: t.Optional[Date]

    @staticmethod
    def current_version() -> int:
        return 0
