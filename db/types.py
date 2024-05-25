from dataclasses import dataclass
from datetime import datetime, timedelta
import typing as t
import re

from data_model.features import ImageExif, GeoAddress, ImageClassification, MD5Annot
from gallery.url import UrlParameters

T = t.TypeVar("T")


@dataclass
class FeaturePayload(t.Generic[T]):
    payload: T
    version: int
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
class ImageAggregation:
    total: int
    address: t.Dict[str, int]
    tag: t.Dict[str, int]
    classification: t.Dict[str, int]
    latitude: t.Optional[LocRange]
    longitude: t.Optional[LocRange]
    altitude: t.Optional[LocRange]


@dataclass
class Image:
    path: str
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
    md5: t.Optional[str]

    @staticmethod
    def current_version() -> int:
        return 2

    @staticmethod
    def from_updates(
        path: str,
        exif: t.Optional[ImageExif],
        address: t.Optional[GeoAddress],
        text_classification: t.Optional[ImageClassification],
        date_from_path: t.Optional[datetime],
        md5: t.Optional[MD5Annot],
        max_last_update: float,
    ) -> "Image":
        date = None
        if exif is not None and exif.date is not None:
            date = exif.date.datetime
        date = date or date_from_path

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

        md5_sum = None
        if md5:
            md5_sum = md5.md5

        return Image(
            path,
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
            md5_sum,
        )

    def match_url(self, url: UrlParameters) -> bool:
        return (
            self.match_date(url.datefrom, url.dateto)
            and self.match_tags(url.tag)
            and self.match_classifications(url.cls)
            and self.match_address(url.addr)
        )

    def match_date(self, datefrom: t.Optional[datetime], dateto: t.Optional[datetime]) -> bool:
        if self.date is not None:
            to_compare = self.date.replace(tzinfo=None)
            if datefrom is not None and to_compare < datefrom:
                return False
            if dateto is not None:
                to_compare -= timedelta(days=1)
                if to_compare > dateto:
                    return False
        else:
            if datefrom is not None or dateto is not None:
                # Datetime filter is on, so skipping stuff without date
                return False
        return True

    def match_tags(self, tag: str) -> bool:
        if not tag:
            return True
        if self.tags is None:
            return False
        return not any(not in_tags(tt, self.tags.keys()) for tt in tag.split(",") if tt)

    def match_classifications(self, classifications: str) -> bool:
        if not classifications:
            return True
        if self.classifications is None:
            return False
        return re.search(classifications, self.classifications) is not None

    def match_address(self, addr: str) -> bool:
        if not addr:
            return True
        if self.address_full is None:
            return False
        return re.search(addr.lower(), self.address_full.lower()) is not None


def in_tags(what: str, tags: t.Iterable[str]) -> bool:
    for tag in tags:
        if what in tag:
            return True
    return False
