from dataclasses import dataclass
from datetime import datetime
import typing as t

from dataclasses_json import DataClassJsonMixin

LocRange = t.Tuple[float, float]


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
class ImageAddress(DataClassJsonMixin):
    country: t.Optional[str]
    name: t.Optional[str]
    full: t.Optional[str]


@dataclass
class Image(DataClassJsonMixin):
    md5: str
    date: t.Optional[datetime]
    tags: t.Optional[t.Dict[str, float]]
    classifications: t.Optional[str]
    address: ImageAddress
    dependent_features_last_update: float
    latitude: t.Optional[float]
    longitude: t.Optional[float]
    altitude: t.Optional[float]
    manual_features: t.List[str]
    being_annotated: bool
    version: int

    @staticmethod
    def current_version() -> int:
        return 2
