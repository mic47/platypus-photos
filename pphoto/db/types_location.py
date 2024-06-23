from __future__ import annotations

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

    def update(self, point: LocPoint) -> LocationBounds:
        self.nw.latitude = max(self.nw.latitude, point.latitude)
        self.nw.longitude = min(self.nw.longitude, point.longitude)
        self.se.latitude = min(self.se.latitude, point.latitude)
        self.se.longitude = max(self.se.longitude, point.longitude)
        return self


@dataclass
class LocationCluster:
    example_path_md5: str
    example_classification: t.Optional[str]
    size: int
    address_name: t.Optional[str]
    address_country: t.Optional[str]
    tsfrom: t.Optional[float]
    tsto: t.Optional[float]
    top_left: LocPoint
    bottom_right: LocPoint
    position: LocPoint
