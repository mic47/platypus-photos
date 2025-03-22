from dataclasses import dataclass
from datetime import datetime
import typing as t


@dataclass
class ImageAggregation:
    total: int
    address: t.Dict[str, int]
    tag: t.Dict[str, int]
    classification: t.Dict[str, int]
    cameras: t.Dict[t.Optional[str], int]  # noqa: F841
    identities: t.Dict[t.Optional[str], int]


@dataclass
class ImageAddress:
    country: t.Optional[str]
    name: t.Optional[str]
    full: t.Optional[str]


@dataclass
class ImageDims:
    width: int
    height: int


@dataclass
class Image:
    md5: str
    extension: str
    date: t.Optional[datetime]
    date_transformed: bool
    tags: t.Optional[t.Dict[str, float]]
    classifications: t.Optional[str]
    address: ImageAddress
    dependent_features_last_update: float
    latitude: t.Optional[float]
    longitude: t.Optional[float]
    altitude: t.Optional[float]
    manual_features: t.List[str]
    being_annotated: bool
    camera: t.Optional[str]
    software: t.Optional[str]
    identities: t.List[str]
    dimension: t.Optional[ImageDims]
    file_size: t.Optional[int]
    version: int

    @staticmethod
    def current_version() -> int:
        return 8
