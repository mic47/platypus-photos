from abc import ABC, abstractmethod
import typing as t

from dataclasses_json import DataClassJsonMixin
from tqdm import tqdm

from annots.date import PathDateExtractor
from data_model.features import ImageExif, GeoAddress, ImageClassification, MD5Annot, HasImage
from db.cache import SQLiteCache
from db.sql import FeaturesTable, GalleryIndexTable, Connection, FeaturePayload
from db.types import ImageAggregation, Image, LocationCluster, LocPoint
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
        self._con = Connection("output.db", check_same_thread=check_same_thread)
        self._features_table = FeaturesTable(self._con)
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

    def get_path_from_hash(self, hsh: t.Union[int, str]) -> t.Optional[str]:
        if isinstance(hsh, int):
            return self._hash_to_image[hsh]
        r = self._md5_to_image.get(hsh)
        if r is not None:
            return r
        path = self._gallery_index.path_by_hash(hsh)
        if path is not None:
            self._md5_to_image[hsh] = path
        return path

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
        for omg in self._gallery_index.get_matching_images(url):
            self._hash_to_image[hash(omg.path)] = omg.path
            if omg.md5:
                self._md5_to_image[omg.md5] = omg.path
            yield omg

    def load(self, show_progress: bool) -> int:
        reindexed = 0
        for file, _last_update in tqdm(
            list(
                self._features_table.dirty_files(
                    [ImageExif.__name__, GeoAddress.__name__, ImageClassification.__name__]
                )
            ),
            desc="reindexing",
            disable=not show_progress,
        ):
            self._reindex(file)
            reindexed += 1
        for file in tqdm(
            list(self._gallery_index.old_version_files()),
            desc="reindexing old versions",
            disable=not show_progress,
        ):
            self._reindex(file)
            reindexed += 1
        return reindexed

    def _reindex(self, path: str) -> None:
        max_last_update = 0.0

        def extract_data(x: t.Optional[FeaturePayload[HasImage[Ser]]]) -> t.Optional[Ser]:
            nonlocal max_last_update
            if x is None:
                return None
            max_last_update = max(max_last_update, x.last_update)
            return x.payload.p

        exif = extract_data(self._exif.get(path))
        addr = extract_data(self._address.get(path))
        text_cls = extract_data(self._text_classification.get(path))
        md5 = extract_data(self._md5.get(path))
        omg = Image.from_updates(
            path,
            exif,
            addr,
            text_cls,
            self._path_to_date.extract_date(path),
            md5,
            max_last_update,
        )
        assert max_last_update > 0.0
        self._gallery_index.add(omg)
        self._features_table.undirty(
            path, [ImageExif.__name__, GeoAddress.__name__, ImageClassification.__name__], max_last_update
        )
