import datetime
import typing as t

import aiohttp

from annots.date import PathDateExtractor
from annots.exif import Exif, ImageExif
from annots.geo import Geolocator, GeoAddress
from annots.text import Models, ImageClassification
from data_model.config import DirectoryMatchingConfig, DBFilesConfig
from data_model.features import WithMD5, PathWithMd5, Error, HasCurrentVersion
from db.cache import SQLiteCache
from db import FeaturesTable


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
        if exif_item.p is not None and exif_item.p.gps is not None:
            # TODO: do recomputation based on the last_update
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
