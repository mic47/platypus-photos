from dataclasses import dataclass
from datetime import datetime
import enum
import typing as t

from dataclasses_json import DataClassJsonMixin

from data_model.features import ImageExif, GeoAddress, ImageClassification

T = t.TypeVar("T")
E = t.TypeVar("E")


@dataclass
class FeaturePayload(t.Generic[T, E]):
    payload: t.Optional[T]
    error: t.Optional[E]
    version: int
    last_update: int
    rowid: int


class ManagedLifecycle(enum.IntEnum):
    NOT_MANAGED = 0
    # File is where is should be (`file`)
    SYNCED = 1
    # File metadata changed, file is being moved.
    BEING_MOVED_AROUND = 2
    # File just has been imported, moving from `og_file` to `file` location
    IMPORTED = 3


@dataclass
class FileRow:
    file: str
    md5: t.Optional[str]
    og_file: t.Optional[str]
    tmp_file: t.Optional[str]
    managed: ManagedLifecycle  # File location is managed by application
    last_update: int
    rowid: int


LocRange = t.Tuple[float, float]


@dataclass
class LocPoint:
    latitude: float
    longitude: float


@dataclass
class LocationCluster:
    example_path_md5: str
    example_classification: t.Optional[str]
    size: int
    address_name: t.Optional[str]
    address_country: t.Optional[str]
    top_left: LocPoint
    bottom_right: LocPoint
    position: LocPoint


@dataclass
class DateCluster:
    example_path_md5: str
    bucket_min: float
    bucket_max: float
    overfetched: bool
    min_timestamp: float
    max_timestamp: float
    avg_timestamp: float
    total: int


@dataclass
class ImageAggregation:
    total: int
    address: t.Dict[str, int]
    tag: t.Dict[str, int]
    classification: t.Dict[str, int]
    latitude: t.Optional[LocRange]
    longitude: t.Optional[LocRange]
    altitude: t.Optional[LocRange]


@dataclass
class DirectoryStats:
    directory: str
    total_images: int
    has_location: int
    has_timestamp: int


@dataclass
class Image(DataClassJsonMixin):
    md5: str
    date: t.Optional[datetime]
    tags: t.Optional[t.Dict[str, float]]
    classifications: t.Optional[str]
    address_country: t.Optional[str]
    address_name: t.Optional[str]
    address_full: t.Optional[str]
    dependent_features_last_update: float
    latitude: t.Optional[float]
    longitude: t.Optional[float]
    altitude: t.Optional[float]
    version: int

    @staticmethod
    def current_version() -> int:
        return 2

    @staticmethod
    def from_updates(
        md5: str,
        exif: t.Optional[ImageExif],
        address: t.Optional[GeoAddress],
        text_classification: t.Optional[ImageClassification],
        date_from_path: t.List[datetime],
        max_last_update: float,
    ) -> "Image":
        date = None
        if exif is not None and exif.date is not None:
            date = exif.date.datetime
        date = date or (date_from_path[0] if date_from_path else None)

        tags: t.Dict[str, float] = {}
        if text_classification is not None:
            for boxes in text_classification.boxes:
                confidence = boxes.box.confidence
                for classification in boxes.classifications:
                    name = classification.name.replace("_", " ").lower()
                    if name not in tags:
                        tags[name] = 0.0
                    tags[name] += confidence * classification.confidence

        classifications = ";".join(
            [] if text_classification is None else text_classification.captions
        ).lower()

        latitude = None
        longitude = None
        altitude = None
        if exif is not None and exif.gps is not None:
            latitude = exif.gps.latitude
            longitude = exif.gps.longitude
            altitude = exif.gps.altitude

        address_country = None
        address_name = None
        address_full = None
        if address is not None:
            address_country = address.country
            address_name = address.name
            address_full = ", ".join(x for x in [address_name, address_country] if x)

        return Image(
            md5,
            date,
            tags,
            classifications,
            address_country,
            address_name,
            address_full,
            max_last_update,
            latitude,
            longitude,
            altitude,
            Image.current_version(),
        )


class InternalError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(f"Internal error, this si bug: {message}")
