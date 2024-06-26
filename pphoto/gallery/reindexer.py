import itertools
import os
import typing as t

from dataclasses_json import DataClassJsonMixin

from pphoto.annots.date import PathDateExtractor
from pphoto.data_model.base import (
    WithMD5,
)
from pphoto.data_model.exif import ImageExif
from pphoto.data_model.geo import GeoAddress
from pphoto.data_model.text import ImageClassification
from pphoto.data_model.manual import ManualLocation, ManualText, ManualDate
from pphoto.db.features_table import FeaturesTable
from pphoto.db.gallery_index_table import GalleryIndexTable
from pphoto.db.connection import PhotosConnection, GalleryConnection
from pphoto.db.files_table import FilesTable
from pphoto.db.cache import SQLiteCache
from pphoto.db.directories_table import DirectoriesTable
from pphoto.gallery.image import make_image
from pphoto.utils.progress_bar import ProgressBar

from pphoto.db.types import FeaturePayload


Ser = t.TypeVar("Ser", bound=DataClassJsonMixin)


class Reindexer:
    def __init__(
        self,
        path_to_date: PathDateExtractor,
        photos_connection: PhotosConnection,
        gallery_connection: GalleryConnection,
    ) -> None:
        # TODO: this should be a feature with loader
        self._path_to_date = path_to_date
        self._p_con = photos_connection
        self._g_con = gallery_connection
        self._features_table = FeaturesTable(self._p_con)
        self._files_table = FilesTable(self._p_con)
        self._directories_table = DirectoriesTable(self._g_con)
        self._exif = SQLiteCache(self._features_table, ImageExif)
        self._address = SQLiteCache(self._features_table, GeoAddress)
        self._text_classification = SQLiteCache(self._features_table, ImageClassification)
        self._manual_location = SQLiteCache(self._features_table, ManualLocation)
        self._manual_text = SQLiteCache(self._features_table, ManualText)
        self._manual_date = SQLiteCache(self._features_table, ManualDate)
        self._gallery_index = GalleryIndexTable(self._g_con)
        self._feature_types = [
            ImageExif.__name__,
            GeoAddress.__name__,
            ImageClassification.__name__,
            ManualText.__name__,
            ManualLocation.__name__,
            ManualDate.__name__,
        ]

    def reconnect(self) -> None:
        self._p_con.reconnect()
        self._g_con.reconnect()

    def check_unused(self) -> None:
        self._p_con.check_unused()
        self._g_con.check_unused()

    def load(self, progress: t.Optional[ProgressBar]) -> int:
        reindexed = 0
        # TODO: this is wrong?
        if progress is not None:
            todo = (
                self._files_table.dirty_md5s_total()
                + self._features_table.dirty_md5s_total(self._feature_types)
                + self._gallery_index.old_versions_md5_total()
            )
            progress.update_what_is_left(todo)
        for md5, _last_update in set(
            itertools.chain(
                self._features_table.dirty_md5s(self._feature_types),
                ((x, None) for x in self._files_table.dirty_md5s()),
            )
        ):
            self._reindex(md5)
            if progress is not None:
                progress.update(1)
            reindexed += 1
        for md5 in list(self._gallery_index.old_versions_md5()):
            self._reindex(md5)
            if progress is not None:
                progress.update(1)
            reindexed += 1

        if progress is not None:
            progress.refresh()
        return reindexed

    def _reindex(self, md5: str) -> None:
        max_last_update = 0.0

        def extract_data(x: t.Optional[FeaturePayload[WithMD5[Ser], None]]) -> t.Optional[Ser]:
            nonlocal max_last_update
            if x is None or x.payload is None:
                return None
            max_last_update = max(max_last_update, x.last_update)
            return x.payload.p

        exif = extract_data(self._exif.get(md5))
        addr = extract_data(self._address.get(md5))
        text_cls = extract_data(self._text_classification.get(md5))
        manual_location = extract_data(self._manual_location.get(md5))
        manual_text = extract_data(self._manual_text.get(md5))
        manual_date = extract_data(self._manual_date.get(md5))
        files = self._files_table.by_md5(md5)
        directories = set()
        max_dir_last_update = 0.0
        for file in files:
            max_dir_last_update = max(max_dir_last_update, file.last_update)
            for path in [file.file, file.og_file]:
                if path is not None:
                    directories.add(os.path.dirname(path))

        effective_max_last_update = max(max_last_update, max_dir_last_update)
        omg = make_image(
            md5,
            exif,
            addr,
            text_cls,
            manual_location,
            manual_text,
            manual_date,
            [
                x
                for x in itertools.chain.from_iterable(
                    [
                        self._path_to_date.extract_date(file.file),
                        None if file.og_file is None else self._path_to_date.extract_date(file.og_file),
                    ]
                    for file in files
                )
                if x is not None
            ],
            effective_max_last_update,
        )

        assert effective_max_last_update > 0.0

        self._directories_table.multi_add([(d, md5) for d in directories])
        self._files_table.undirty(md5, max_dir_last_update)
        self._gallery_index.add(omg)
        self._features_table.undirty(md5, self._feature_types, max_last_update)
