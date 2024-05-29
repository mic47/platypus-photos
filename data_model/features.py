import json
import typing as t
from datetime import datetime
from dataclasses import dataclass, field
from dataclasses_json import DataClassJsonMixin


class HasCurrentVersion(DataClassJsonMixin):
    @staticmethod
    def current_version() -> int:
        raise NotImplementedError


Ser = t.TypeVar("Ser", bound="DataClassJsonMixin")
T = t.TypeVar("T")


class HasImage(t.Generic[Ser]):
    def __init__(self, image: str, version: int, payload: Ser):
        self.image = image
        self.version = version
        self.p = payload

    @staticmethod
    def load(d: t.Dict[str, t.Any], payload: Ser) -> "HasImage[Ser]":
        return HasImage(cast(d["image"], str), cast(d["version"], int), payload)

    def to_json(self) -> str:
        return json.dumps(
            {
                **self.p.to_dict(),
                "image": self.image,
                "version": self.version,
            },
            ensure_ascii=False,
        )


def cast(x: t.Any, type_: t.Type[T]) -> T:
    if not isinstance(x, type_):
        # pylint: disable = broad-exception-raised
        raise Exception(f"Expected value of type '{type_}', got value '{x}'")
    return x


@dataclass
class GPSCoord(DataClassJsonMixin):
    latitude: float
    longitude: float
    altitude: t.Optional[float]
    date: t.Optional[datetime]


@dataclass
class Camera(DataClassJsonMixin):
    make: str
    model: str
    serial_number: str
    software: str


@dataclass
class Date(DataClassJsonMixin):
    datetime: t.Optional[datetime]
    time_str: t.Optional[str]


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
class POI(DataClassJsonMixin):
    name: str
    latitude: float
    longitude: float


@dataclass
class NearestPOI(HasCurrentVersion):
    poi: POI
    distance: float

    @staticmethod
    def current_version() -> int:
        return 0


@dataclass
class MD5Annot(HasCurrentVersion):
    md5: str

    @staticmethod
    def current_version() -> int:
        return 1


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
    exception: t.Optional[str] = field(default=None)

    @staticmethod
    def current_version() -> int:
        return 0
