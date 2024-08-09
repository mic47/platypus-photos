import asyncio
import itertools
import os
import sys
import traceback
import typing as t

from pphoto.annots.date import PathDateExtractor
from pphoto.data_model.base import WithMD5, StorableData
from pphoto.data_model.exif import ImageExif
from pphoto.data_model.geo import GeoAddress
from pphoto.data_model.text import ImageClassification
from pphoto.data_model.manual import ManualLocation, ManualText, ManualDate, ManualIdentities
from pphoto.db.features_table import FeaturesTable
from pphoto.db.gallery_index_table import GalleryIndexTable
from pphoto.db.connection import PhotosConnection, GalleryConnection
from pphoto.db.files_table import FilesTable
from pphoto.db.cache import SQLiteCache
from pphoto.db.directories_table import DirectoriesTable
from pphoto.gallery.image import make_image
from pphoto.utils.progress_bar import ProgressBar

from pphoto.db.types import FeaturePayload


Ser = t.TypeVar("Ser", bound=StorableData)


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
        self._exif = SQLiteCache(self._features_table, ImageExif, ImageExif.from_json_bytes)
        self._address = SQLiteCache(self._features_table, GeoAddress, GeoAddress.from_json_bytes)
        self._text_classification = SQLiteCache(
            self._features_table, ImageClassification, ImageClassification.from_json_bytes
        )
        self._manual_location = SQLiteCache(
            self._features_table, ManualLocation, ManualLocation.from_json_bytes
        )
        self._manual_identity = SQLiteCache(
            self._features_table, ManualIdentities, ManualIdentities.from_json_bytes
        )
        self._manual_text = SQLiteCache(self._features_table, ManualText, ManualText.from_json_bytes)
        self._manual_date = SQLiteCache(self._features_table, ManualDate, ManualDate.from_json_bytes)
        self._gallery_index = GalleryIndexTable(self._g_con)
        self._feature_types = [
            ImageExif.__name__,
            GeoAddress.__name__,
            ImageClassification.__name__,
            ManualText.__name__,
            ManualLocation.__name__,
            ManualDate.__name__,
            ManualIdentities.__name__,
        ]
        self._queue: t.Set[str] = set()

    def reconnect(self) -> None:
        self._p_con.reconnect()
        self._g_con.reconnect()

    def check_unused(self) -> None:
        self._p_con.check_unused()
        self._g_con.check_unused()

    async def load(self, progress: t.Optional[ProgressBar]) -> int:
        reindexed = 0
        # TODO:
        # If queue does not exists
        #     Pull queue from the DB
        # If queue is empty:
        #     check newest items from source tables, save queue index
        #     put and store them into queue
        # Additionally, make the DB to automatically batch inserts in transactions.
        # Why?
        # 1. photo table will be again read only.
        # 2. Ability to have more clients reindexing / reacting to changes
        # 3. Faster reingest -- only one table is locking
        if not self._queue:
            if progress is not None:
                # TODO: this is wrong?
                todo = (
                    self._files_table.dirty_md5s_total()
                    + self._features_table.dirty_md5s_total(self._feature_types)
                    + self._gallery_index.old_versions_md5_total()
                )
                progress.update_what_is_left(todo)
            fetch_limit = 100000
            for md5, _last_update in set(
                itertools.chain(
                    self._features_table.dirty_md5s(self._feature_types, limit=fetch_limit),
                    ((x, None) for x in self._files_table.dirty_md5s(limit=fetch_limit)),
                    ((x, None) for x in self._gallery_index.old_versions_md5(limit=fetch_limit)),
                )
            ):
                self._queue.add(md5)
        to_do_this_round = list(itertools.islice(self._queue, 1000))
        for md5s in batched(to_do_this_round, 100):
            try:
                with (
                    # pylint: disable-next = protected-access
                    self._files_table._con.transaction(),
                    # pylint: disable-next = protected-access
                    self._features_table._con.transaction(),
                    # pylint: disable-next = protected-access
                    self._directories_table._con.transaction(),
                    # pylint: disable-next = protected-access
                    self._gallery_index._con.transaction(),
                ):
                    for md5 in md5s:
                        self._reindex(md5)
                for md5 in md5s:
                    self._queue.remove(md5)
                if progress is not None:
                    progress.update(len(md5s))
                reindexed += len(md5s)
            # pylint: disable-next = broad-exception-caught
            except Exception as e:
                traceback.print_exc()
                print(
                    "Error while batch reindexing. Going to reindex this batch individually",
                    e,
                    file=sys.stderr,
                )
                for md5 in md5s:
                    self._reindex(md5)
                    self._queue.remove(md5)
                    if progress is not None:
                        progress.update(1)
                    reindexed += 1
            await asyncio.sleep(0.001)

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
        manual_identity = extract_data(self._manual_identity.get(md5))
        files = self._files_table.by_md5(md5)
        directories = set()
        max_dir_last_update = 0.0
        extensions: t.Dict[str, int] = {}
        for file in files:
            max_dir_last_update = max(max_dir_last_update, file.last_update)
            ext: str = os.path.splitext(file.file)[1].lstrip(".")
            extensions[ext] = extensions.get(ext, 0) + 1
            for path in [file.file, file.og_file]:
                if path is not None:
                    directories.add(os.path.dirname(path))
        if not extensions:
            top_extension = "jpg"
        else:
            top_extension = sorted(extensions.items(), key=lambda x: x[1])[-1][0]

        effective_max_last_update = max(max_last_update, max_dir_last_update)
        omg = make_image(
            md5,
            top_extension,
            exif,
            addr,
            text_cls,
            manual_location,
            manual_text,
            manual_date,
            manual_identity,
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


T = t.TypeVar("T")


def batched(iterable: t.Iterable[T], n: int) -> t.Iterable[t.Tuple[T, ...]]:
    # batched('ABCDEFG', 3) → ABC DEF G
    if n < 1:
        raise ValueError("n must be at least one")
    iterator = iter(iterable)
    while batch := tuple(itertools.islice(iterator, n)):
        yield batch
