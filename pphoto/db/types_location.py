from dataclasses import dataclass
import typing as t

from dataclasses_json import DataClassJsonMixin


@dataclass
class LocPoint(DataClassJsonMixin):
    latitude: float
    longitude: float


@dataclass
class LocationBounds(DataClassJsonMixin):
    nw: LocPoint  # noqa: F841
    se: LocPoint  # noqa: F841


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
