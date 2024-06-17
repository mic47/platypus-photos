import typing as t

from datetime import datetime
from dataclasses import dataclass, field
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


@dataclass
class GeoAddress(HasCurrentVersion):
    address: str
    country: t.Optional[str]
    name: t.Optional[str]
    raw: str
    query: str
    # TODO: add points of interestis -- i.e. home, work, ...

    @staticmethod
    def current_version() -> int:
        return 0


@dataclass
class Box(DataClassJsonMixin):
    classification: str
    confidence: float
    xyxy: t.List[float]


@dataclass
class Classification(DataClassJsonMixin):
    name: str
    confidence: float


@dataclass
class BoxClassification(DataClassJsonMixin):
    box: Box
    classifications: t.List[Classification]


@dataclass
class ImageClassification(HasCurrentVersion):
    captions: t.List[str]
    boxes: t.List[BoxClassification]
    exception: t.Optional[str] = field(default=None)  # noqa: F841

    @staticmethod
    def current_version() -> int:
        return 0


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
