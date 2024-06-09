import json
import traceback
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


@dataclass(frozen=True, eq=True)
class PathWithMd5:
    path: str
    md5: str


@dataclass
class Error(DataClassJsonMixin):
    name: str
    message: t.Optional[str]
    traceback: t.Optional[str]

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
                "p": None if self.p is None else self.p.to_dict(encode_json=True),
                "e": None if self.e is None else self.e.to_dict(encode_json=True),
                "md5": self.md5,
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
