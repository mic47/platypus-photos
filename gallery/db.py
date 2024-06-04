from abc import ABC, abstractmethod
import typing as t

from dataclasses_json import DataClassJsonMixin
from tqdm import tqdm

from annots.date import PathDateExtractor
from data_model.features import ImageExif, GeoAddress, ImageClassification, MD5Annot, WithMD5
from db import FeaturesTable, GalleryIndexTable, Connection, FilesTable, SQLiteCache
from db.types import ImageAggregation, Image, LocationCluster, LocPoint, FeaturePayload, FileRow
from gallery.url import UrlParameters

Ser = t.TypeVar("Ser", bound=DataClassJsonMixin)


class OmgDB(ABC):
    @abstractmethod
    def load(self, show_progress: bool) -> int:
        ...

    @abstractmethod
    def get_matching_images(self, url: UrlParameters) -> t.Iterable[Image]:
        ...

    @abstractmethod
    def get_aggregate_stats(self, url: UrlParameters) -> ImageAggregation:
        ...

    @abstractmethod
    def get_image_clusters(
        self,
        url: UrlParameters,
        top_left: LocPoint,
        bottom_right: LocPoint,
        latitude_resolution: float,
        longitude_resolution: float,
        over_fetch: float,
    ) -> t.List[LocationCluster]:
        ...

    @abstractmethod
    def files(self, md5: str) -> t.List[FileRow]:
        ...

    @abstractmethod
    def get_path_from_hash(self, hsh: t.Union[int, str]) -> t.Optional[str]:
        ...

    @abstractmethod
    def reconnect(self) -> None:
        ...

    @abstractmethod
    def check_unused(self) -> None:
        ...


class ImageSqlDB(OmgDB):
    def __init__(self, path_to_date: PathDateExtractor, check_same_thread: bool) -> None:
        # TODO: this should be a feature with loader
        self._path_to_date = path_to_date
        self._con = Connection("data/photos.db", check_same_thread=check_same_thread)
        self._features_table = FeaturesTable(self._con)
        self._files_table = FilesTable(self._con)
        self._exif = SQLiteCache(self._features_table, ImageExif)
        self._address = SQLiteCache(self._features_table, GeoAddress)
        self._text_classification = SQLiteCache(self._features_table, ImageClassification)
        self._md5 = SQLiteCache(self._features_table, MD5Annot)
        self._gallery_index = GalleryIndexTable(self._con)
        self._hash_to_image: t.Dict[int, str] = {}
        self._md5_to_image: t.Dict[str, str] = {}

    def reconnect(self) -> None:
        self._con.reconnect()

    def check_unused(self) -> None:
        self._con.check_unused()

    def files(self, md5: str) -> t.List[FileRow]:
        return self._files_table.by_md5(md5)

    def get_path_from_hash(self, hsh: t.Union[int, str]) -> t.Optional[str]:
        if isinstance(hsh, int):
            return self._hash_to_image[hsh]
        r = self._md5_to_image.get(hsh)
        if r is not None:
            return r
        path = self._files_table.example_by_md5(hsh)
        if path is None:
            return None
        self._md5_to_image[hsh] = path.file
        return path.file

    def get_aggregate_stats(self, url: "UrlParameters") -> ImageAggregation:
        return self._gallery_index.get_aggregate_stats(url)

    def get_image_clusters(
        self,
        url: UrlParameters,
        top_left: LocPoint,
        bottom_right: LocPoint,
        latitude_resolution: float,
        longitude_resolution: float,
        over_fetch: float,
    ) -> t.List[LocationCluster]:
        return self._gallery_index.get_image_clusters(
            url, top_left, bottom_right, latitude_resolution, longitude_resolution, over_fetch
        )

    def get_matching_images(self, url: UrlParameters) -> t.Iterable[Image]:
        yield from self._gallery_index.get_matching_images(url)

    def load(self, show_progress: bool) -> int:
        reindexed = 0
        for md5, _last_update in tqdm(
            list(
                self._features_table.dirty_md5s(
                    [ImageExif.__name__, GeoAddress.__name__, ImageClassification.__name__]
                )
            ),
            desc="reindexing",
            disable=not show_progress,
        ):
            self._reindex(md5)
            reindexed += 1
        for md5 in tqdm(
            list(self._gallery_index.old_versions_md5()),
            desc="reindexing old versions",
            disable=not show_progress,
        ):
            self._reindex(md5)
            reindexed += 1
        return reindexed

    def _reindex(self, md5: str) -> None:
        max_last_update = 0.0

        def extract_data(x: t.Optional[FeaturePayload[WithMD5[Ser]]]) -> t.Optional[Ser]:
            nonlocal max_last_update
            if x is None:
                return None
            max_last_update = max(max_last_update, x.last_update)
            return x.payload.p

        exif = extract_data(self._exif.get(md5))
        addr = extract_data(self._address.get(md5))
        text_cls = extract_data(self._text_classification.get(md5))
        files = self._files_table.by_md5(md5)
        omg = Image.from_updates(
            md5,
            exif,
            addr,
            text_cls,
            [x for x in (self._path_to_date.extract_date(file.file) for file in files) if x is not None],
            max_last_update,
        )
        assert max_last_update > 0.0
        self._gallery_index.add(omg)
        self._features_table.undirty(
            md5, [ImageExif.__name__, GeoAddress.__name__, ImageClassification.__name__], max_last_update
        )
