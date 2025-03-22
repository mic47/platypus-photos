import datetime
import typing as t

from pphoto.annots.date import PathDateExtractor
from pphoto.annots.dimensions import Dimensions
from pphoto.annots.exif import Exif, ImageExif
from pphoto.annots.face import FaceEmbeddingsAnnotator
from pphoto.annots.geo import Geolocator, GeoAddress
from pphoto.annots.text import Models, ImageClassification
from pphoto.data_model.config import DirectoryMatchingConfig, DBFilesConfig
from pphoto.data_model.base import WithMD5, PathWithMd5, Error, StorableData
from pphoto.data_model.dimensions import ImageDimensions
from pphoto.data_model.manual import (
    ManualLocation,
    ManualText,
    ManualDate,
    ManualIdentity,
    ManualIdentities,
    Position,
)
from pphoto.data_model.face import FaceEmbeddings
from pphoto.remote_jobs.types import RemoteTask, ManualAnnotationTask
from pphoto.db.cache import SQLiteCache
from pphoto.db.features_table import FeaturesTable
from pphoto.db.identity_table import IdentityTable
from pphoto.communication.server import RemoteExecutorQueue


class Annotator:
    def __init__(
        self,
        directory_matching: DirectoryMatchingConfig,
        files_config: DBFilesConfig,
        features: FeaturesTable,
        identities_table: IdentityTable,
        remote_annotator_queue: t.Optional[RemoteExecutorQueue],
    ):
        self.path_to_date = PathDateExtractor(directory_matching)
        models_cache = SQLiteCache(
            features,
            ImageClassification,
            ImageClassification.from_json_bytes,
            files_config.image_to_text_jsonl,
        )
        self.models = Models(models_cache, remote_annotator_queue)
        face_embeddings_cache = SQLiteCache(
            features, FaceEmbeddings, FaceEmbeddings.from_json_bytes, files_config.face_embeddings_jsonl
        )
        self.face = FaceEmbeddingsAnnotator(face_embeddings_cache, remote_annotator_queue)
        exif_cache = SQLiteCache(features, ImageExif, ImageExif.from_json_bytes, files_config.exif_jsonl)
        self.exif = Exif(exif_cache)
        dimm_cache = SQLiteCache(
            features, ImageDimensions, ImageDimensions.from_json_bytes, files_config.dimm_jsonl
        )
        self.dimensions = Dimensions(dimm_cache)
        self.manual_location = SQLiteCache(
            features, ManualLocation, ManualLocation.from_json_bytes, files_config.manual_location_jsonl
        )
        self.manual_identities = SQLiteCache(
            features, ManualIdentities, ManualIdentities.from_json_bytes, files_config.manual_identity_jsonl
        )
        self._identities = identities_table
        self.manual_date = SQLiteCache(
            features, ManualDate, ManualDate.from_json_bytes, files_config.manual_date_jsonl
        )
        self.manual_text = SQLiteCache(
            features, ManualText, ManualText.from_json_bytes, files_config.manual_text_jsonl
        )
        geolocator_cache = SQLiteCache(
            features, GeoAddress, GeoAddress.from_json_bytes, files_config.geo_address_jsonl
        )
        self.geolocator = Geolocator(geolocator_cache)
        self.cheap_features_types: t.List[t.Type[StorableData]] = [ImageExif, ImageDimensions, GeoAddress]
        self.image_to_text_types: t.List[t.Type[StorableData]] = [ImageClassification, FaceEmbeddings]

    def update_manual_identity(
        self, task: RemoteTask[t.List[ManualIdentity]]
    ) -> t.Tuple[t.Optional[WithMD5[ManualIdentities]], t.Tuple[str, t.List[ManualIdentity]]]:
        existing_identity = self.manual_identities.get(task.id_.md5)
        if (
            existing_identity is None
            or existing_identity.payload is None
            or existing_identity.payload.p is None
        ):
            identities: t.Dict[Position, ManualIdentity] = {}
        else:
            identities = {identity.position: identity for identity in existing_identity.payload.p.identities}
        new_identities = []
        for identity in task.payload:
            if identity.position not in identities:
                new_identities.append(identity)
            identities[identity.position] = identity
        for identity in task.payload:
            if identity.identity is not None:
                self._identities.add(identity.identity, None, None, True)
        return (
            self.manual_identities.add(
                WithMD5(
                    task.id_.md5,
                    ManualIdentities.current_version(),
                    ManualIdentities(list(identities.values())),
                    None,
                )
            ),
            (task.id_.md5, new_identities),
        )

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
        WithMD5[ImageDimensions],
        WithMD5[GeoAddress],
        t.Optional[datetime.datetime],
    ]:
        exif_item = self.exif.process_file(path)
        dimensions_item = self.dimensions.process_file(path)
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
        return (path, exif_item, dimensions_item, geo, path_date)

    async def image_to_text(
        self, path: PathWithMd5
    ) -> t.Tuple[PathWithMd5, WithMD5[ImageClassification], WithMD5[FaceEmbeddings]]:
        itt = await self.models.process_file(path)
        fe = await self.face.process_file(path)
        # There might be manual annotations which needs to be processed too
        identities = self.manual_identities.get(path.md5)
        if identities is None or identities.payload is None or identities.payload.p is None:
            return (path, itt, fe)
        if fe.p is not None:
            existing_positions = set(fc.position for fc in fe.p.faces)
        else:
            existing_positions = set()
        to_annotate = [
            identity
            for identity in identities.payload.p.identities
            if identity.position not in existing_positions
        ]
        if not to_annotate:
            return (path, itt, fe)
        (fe,) = await self.add_faces(path, to_annotate)
        return (path, itt, fe)

    async def add_faces(
        self,
        path: PathWithMd5,
        identities: t.List[ManualIdentity],
    ) -> t.Tuple[WithMD5[FaceEmbeddings]]:
        return (await self.face.add_faces(path, identities),)
