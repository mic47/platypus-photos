import datetime
import typing as t

import aiohttp

from pphoto.annots.date import PathDateExtractor
from pphoto.annots.exif import Exif, ImageExif
from pphoto.annots.geo import Geolocator, GeoAddress
from pphoto.annots.text import Models, ImageClassification
from pphoto.data_model.config import DirectoryMatchingConfig, DBFilesConfig
from pphoto.data_model.base import WithMD5, PathWithMd5, Error, HasCurrentVersion
from pphoto.data_model.manual import ManualLocation
from pphoto.db.cache import SQLiteCache
from pphoto.db.features_table import FeaturesTable


class Annotator:
    def __init__(
        self,
        directory_matching: DirectoryMatchingConfig,
        files_config: DBFilesConfig,
        features: FeaturesTable,
        session: aiohttp.ClientSession,
        annotate_url: t.Optional[str],
    ):
        self._session = session
        self.path_to_date = PathDateExtractor(directory_matching)
        models_cache = SQLiteCache(features, ImageClassification, files_config.image_to_text_jsonl)
        self.models = Models(models_cache, annotate_url)
        exif_cache = SQLiteCache(features, ImageExif, files_config.exif_jsonl)
        self.exif = Exif(exif_cache)
        self.manual_location = SQLiteCache(features, ManualLocation, files_config.manual_location_jsonl)
        geolocator_cache = SQLiteCache(features, GeoAddress, files_config.geo_address_jsonl)
        self.geolocator = Geolocator(geolocator_cache)
        self.cheap_features_types: t.List[t.Type[HasCurrentVersion]] = [ImageExif, GeoAddress]
        self.image_to_text_types: t.List[t.Type[HasCurrentVersion]] = [ImageClassification]

    def cheap_features(self, path: PathWithMd5) -> t.Tuple[
        PathWithMd5,
        WithMD5[ImageExif],
        WithMD5[GeoAddress],
        t.Optional[datetime.datetime],
    ]:
        exif_item = self.exif.process_image(path)
        manual_location = self.manual_location.get(path.md5)
        if (
            manual_location is not None
            and manual_location.payload is not None
            and manual_location.payload.p is not None
        ):
            geo = self.geolocator.address(
                path, manual_location.payload.p.latitude, manual_location.payload.p.longitude, recompute=False
            )
        elif exif_item.p is not None and exif_item.p.gps is not None:
            geo = self.geolocator.address(
                path, exif_item.p.gps.latitude, exif_item.p.gps.longitude, recompute=False
            )
        else:
            geo = self.geolocator.cache.add(
                WithMD5(path.md5, GeoAddress.current_version(), None, Error("DependencyMissing", None, None))
            )
        path_date = self.path_to_date.extract_date(path.path)
        return (path, exif_item, geo, path_date)

    async def image_to_text(self, path: PathWithMd5) -> t.Tuple[PathWithMd5, WithMD5[ImageClassification]]:
        itt = await self.models.process_image(self._session, path)
        return (path, itt)
