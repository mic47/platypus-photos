from __future__ import annotations

from datetime import datetime
import itertools
import typing as t

from pphoto.data_model.exif import ImageExif
from pphoto.data_model.geo import GeoAddress
from pphoto.data_model.text import ImageClassification
from pphoto.data_model.manual import ManualText, ManualLocation, ManualDate
from pphoto.db.types_image import Image, ImageAddress


def make_image_address(
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


def make_image(
    md5: str,
    extension: str,
    exif: t.Optional[ImageExif],
    address: t.Optional[GeoAddress],
    text_classification: t.Optional[ImageClassification],
    manual_location: t.Optional[ManualLocation],
    manual_text: t.Optional[ManualText],
    transformed_date: t.Optional[ManualDate],
    date_from_path: t.List[datetime],
    max_last_update: float,
) -> Image:
    date = None
    if exif is not None and exif.date is not None:
        date = exif.date.datetime
    date = (
        (transformed_date.date if transformed_date is not None else None)
        or date
        or (date_from_path[0] if date_from_path else None)
    )
    camera = None
    software = None
    if exif is not None:
        make = exif.camera.make.lower().strip()
        for x in ["olympus", "nikon"]:
            if make.startswith(x):
                make = x
        model = " ".join(x for x in exif.camera.model.lower().split() if x not in make).strip()
        camera = f"{make} {model}".strip() or None
        software = exif.camera.software.lower().strip() or None

    tags: t.Dict[str, float] = {}
    if text_classification is not None:
        for boxes in text_classification.boxes:
            confidence = boxes.box.confidence
            base_name = boxes.box.classification.replace("_", " ").lower()
            if base_name not in tags:
                tags[base_name] = confidence
            else:
                tags[base_name] = max(tags[base_name], confidence)
            for classification in boxes.classifications:
                name = base_name + " - " + classification.name.replace("_", " ").lower()
                if name not in tags:
                    tags[name] = 0.0
                tags[name] = max(tags[name], confidence * classification.confidence)

    max_tag = max(0.0001, max(tags.values(), default=1.0))
    if manual_text is not None:
        for tag in manual_text.tags:
            tags[tag] = max_tag
    # Throw away rubish tags
    tags = {k: v for k, v in tags.items() if (v / max_tag) >= 0.5}

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
    if transformed_date is not None:
        manual_features.append(type(transformed_date).__name__)

    return Image(
        md5,
        extension,
        date,
        False,  # This is not real column, just derived from query
        tags,
        classifications,
        make_image_address(address, manual_location),
        max_last_update,
        latitude,
        longitude,
        altitude,
        manual_features,
        False,
        camera,
        software,
        Image.current_version(),
    )
