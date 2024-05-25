import typing as t
from datetime import datetime
from dataclasses import dataclass, field
from dataclasses_json import DataClassJsonMixin


@dataclass
class HasImage(DataClassJsonMixin):
    image: str
    version: int

    @staticmethod
    def current_version() -> int:
        raise NotImplementedError

    def _set_from_cache(self) -> None:
        # pylint: disable= attribute-defined-outside-init
        self._from_cache = True

    def is_from_cache(self) -> bool:
        if hasattr(self, "_from_cache"):
            return self._from_cache
        return False

    def changed(self) -> bool:
        return not self.is_from_cache()


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
class ImageExif(HasImage):
    image: str
    version: int
    gps: t.Optional[GPSCoord]
    camera: Camera
    date: t.Optional[Date]

    @staticmethod
    def current_version() -> int:
        return 0


@dataclass
class GeoAddress(HasImage):
    image: str
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
class NearestPOI(HasImage):
    image: str
    poi: POI
    distance: float

    @staticmethod
    def current_version() -> int:
        return 0


@dataclass
class MD5Annot(HasImage):
    image: str
    version: int
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
class ImageClassification(HasImage):
    image: str
    version: int
    captions: t.List[str]
    boxes: t.List[BoxClassification]
    exception: t.Optional[str] = field(default=None)

    def print(self) -> None:
        print(self.image)
        for caption in self.captions:
            print(" ", caption)
        for box in self.boxes:
            print(" ", box.box.classification, box.box.confidence)
            for c in box.classifications:
                print("   ", c.name, c.confidence)

    @staticmethod
    def current_version() -> int:
        return 0
