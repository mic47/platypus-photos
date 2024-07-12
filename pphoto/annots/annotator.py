import datetime
import typing as t

from pphoto.annots.date import PathDateExtractor
from pphoto.annots.exif import Exif, ImageExif
from pphoto.annots.face import FaceEmbeddingsAnnotator
from pphoto.annots.geo import Geolocator, GeoAddress
from pphoto.annots.text import Models, ImageClassification
from pphoto.data_model.config import DirectoryMatchingConfig, DBFilesConfig
from pphoto.data_model.base import WithMD5, PathWithMd5, Error, HasCurrentVersion
from pphoto.data_model.manual import ManualLocation, ManualText, ManualDate
from pphoto.data_model.face import FaceEmbeddings
from pphoto.remote_jobs.types import RemoteTask, ManualAnnotationTask
from pphoto.db.cache import SQLiteCache
from pphoto.db.features_table import FeaturesTable
from pphoto.communication.server import RemoteExecutorQueue


class Annotator:
    def __init__(
        self,
        directory_matching: DirectoryMatchingConfig,
        files_config: DBFilesConfig,
        features: FeaturesTable,
        remote_annotator_queue: t.Optional[RemoteExecutorQueue],
    ):
        self.path_to_date = PathDateExtractor(directory_matching)
        models_cache = SQLiteCache(features, ImageClassification, files_config.image_to_text_jsonl)
        self.models = Models(models_cache, remote_annotator_queue)
        face_embeddings_cache = SQLiteCache(features, FaceEmbeddings, files_config.face_embeddings_jsonl)
        self.face = FaceEmbeddingsAnnotator(face_embeddings_cache, remote_annotator_queue)
        exif_cache = SQLiteCache(features, ImageExif, files_config.exif_jsonl)
        self.exif = Exif(exif_cache)
        self.manual_location = SQLiteCache(features, ManualLocation, files_config.manual_location_jsonl)
        self.manual_date = SQLiteCache(features, ManualDate, files_config.manual_date_jsonl)
        self.manual_text = SQLiteCache(features, ManualText, files_config.manual_text_jsonl)
        geolocator_cache = SQLiteCache(features, GeoAddress, files_config.geo_address_jsonl)
        self.geolocator = Geolocator(geolocator_cache)
        self.cheap_features_types: t.List[t.Type[HasCurrentVersion]] = [ImageExif, GeoAddress]
        self.image_to_text_types: t.List[t.Type[HasCurrentVersion]] = [ImageClassification, FaceEmbeddings]

    def manual_features(
        self, task: RemoteTask[ManualAnnotationTask]
    ) -> t.Tuple[
        t.Optional[WithMD5[ManualLocation]], t.Optional[WithMD5[ManualDate]], t.Optional[WithMD5[ManualText]]
    ]:
        ml = None
        md = None
        mt = None
        if task.payload.location is not None:
            ml = self.manual_location.add(
                WithMD5(task.id_.md5, ManualLocation.current_version(), task.payload.location, None)
            )
        if task.payload.date is not None:
            md = self.manual_date.add(
                WithMD5(task.id_.md5, ManualDate.current_version(), task.payload.date, None)
            )
        if task.payload.text is not None:
            txt = task.payload.text
            t_pay = ManualText(
                [] if txt.tags is None else txt.tags.split(","),
                [] if txt.description is None else txt.description.split(";"),
            )
            if task.payload.text_extend:
                old_pay = self.manual_text.get(task.id_.md5)
                if old_pay is not None and old_pay.payload is not None and old_pay.payload.p is not None:
                    old_tags = set(t_pay.tags)
                    t_pay.tags.extend(x for x in old_pay.payload.p.tags if x not in old_tags)
                    old_desc = set(t_pay.description)
                    t_pay.description.extend(x for x in old_pay.payload.p.description if x not in old_desc)
            mt = self.manual_text.add(WithMD5(task.id_.md5, ManualText.current_version(), t_pay, None))
        return (ml, md, mt)

    def cheap_features(self, path: PathWithMd5, recompute_location: bool) -> t.Tuple[
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
                path,
                manual_location.payload.p.latitude,
                manual_location.payload.p.longitude,
                recompute=recompute_location,
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

    async def image_to_text(
        self, path: PathWithMd5
    ) -> t.Tuple[PathWithMd5, WithMD5[ImageClassification], WithMD5[FaceEmbeddings]]:
        itt = await self.models.process_image(path)
        fe = await self.face.process_image(path)
        return (path, itt, fe)
