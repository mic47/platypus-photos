import typing as t
from datetime import datetime
from dataclasses import dataclass

from image_to_text import ImageClassification
from image_exif import ImageExif
from md5_annot import MD5Annot
from geolocation import GeoAddress
from cache import HasImage, Cache

VERSION = 0


@dataclass
class ImageAnnotations(HasImage):
    image: str
    version: int
    md5: str
    exif: ImageExif
    address: t.Optional[GeoAddress]
    text_classification: t.Optional[ImageClassification]
    date_from_path: t.Optional[datetime]

    @staticmethod
    def current_version() -> int:
        return VERSION


class ImageAnnotator:
    def __init__(self, cache: Cache[ImageAnnotations]):
        self._cache = cache

    def process(
        self,
        image: str,
        md5: MD5Annot,
        exif: ImageExif,
        address: t.Optional[GeoAddress],
        text_classification: t.Optional[ImageClassification],
        date: t.Optional[datetime],
    ) -> ImageAnnotations:
        # TODO: datetime is not chaced
        # Also, if dependency changed, nothing is changed
        changed = (
            md5.changed()
            or exif.changed()
            or (address is not None and address.changed())
            or (text_classification is not None and text_classification.changed())
        )
        cached = self._cache.get(image)
        if (
            changed
            or cached is None
            or (
                cached is not None
                and (
                    md5.md5 != cached.md5
                    or exif != cached.exif
                    or (address is not None and address != cached.address)
                    or (text_classification is not None and text_classification != cached.text_classification)
                )
            )
        ):
            return self._cache.add(
                self.process_impl(image, md5.md5, exif, address, text_classification, date)
            )
        else:
            return cached

    def process_impl(
        self,
        image: str,
        md5: str,
        exif: ImageExif,
        address: t.Optional[GeoAddress],
        text_classification: t.Optional[ImageClassification],
        date: t.Optional[datetime],
    ) -> ImageAnnotations:
        return ImageAnnotations(image, VERSION, md5, exif, address, text_classification, date)
