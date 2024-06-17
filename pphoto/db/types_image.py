from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import itertools
import typing as t

from dataclasses_json import DataClassJsonMixin

from pphoto.data_model.exif import ImageExif
from pphoto.data_model.geo import GeoAddress
from pphoto.data_model.text import ImageClassification
from pphoto.data_model.manual import ManualText, ManualLocation

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

    @staticmethod
    def from_updates(
        address: t.Optional[GeoAddress],
        manual_location: t.Optional[ManualLocation],
    ) -> ImageAddress:
        country = None
        name = None
        full = None
        if address is not None:
            country = address.country
            name = address.name
        if manual_location is not None:
            if manual_location.address_name:
                name = manual_location.address_name
            if manual_location.address_country:
                country = manual_location.address_country
        if name is not None or country is not None:
            full = ", ".join(x for x in [name, country] if x)
        return ImageAddress(country, name, full)


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
        manual_location: t.Optional[ManualLocation],
        manual_text: t.Optional[ManualText],
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
        if manual_text is not None:
            max_tags = max(tags.values(), default=1.0)
            for tag in manual_text.tags:
                tags[tag] = max_tags

        classifications = ";".join(
            sorted(
                set(
                    itertools.chain(
                        ([] if text_classification is None else text_classification.captions),
                        ([] if manual_text is None else manual_text.description),
                    )
                )
            )
        ).lower()

        latitude = None
        longitude = None
        altitude = None
        if exif is not None and exif.gps is not None:
            latitude = exif.gps.latitude
            longitude = exif.gps.longitude
            altitude = exif.gps.altitude
        if manual_location:
            latitude = manual_location.latitude
            longitude = manual_location.longitude

        manual_features = []
        if manual_location is not None:
            manual_features.append(type(manual_location).__name__)
        if manual_text is not None:
            manual_features.append(type(manual_text).__name__)

        return Image(
            md5,
            date,
            tags,
            classifications,
            ImageAddress.from_updates(address, manual_location),
            max_last_update,
            latitude,
            longitude,
            altitude,
            manual_features,
            Image.current_version(),
        )
