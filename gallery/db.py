from abc import ABC, abstractmethod
import typing as t

from tqdm import tqdm

from image_to_text import ImageClassification
from image_exif import ImageExif
from geolocation import GeoAddress
from filename_to_date import PathDateExtractor
from cache import SQLiteCache

from db.sql import FeaturesTable, GalleryIndexTable, connect
from db.types import ImageAggregation, Image
from gallery.url import UrlParameters

T = t.TypeVar("T")


class OmgDB(ABC):
    @abstractmethod
    def load(self, show_progress: bool) -> None:
        pass

    @abstractmethod
    def get_matching_images(self, url: UrlParameters) -> t.Iterable[Image]:
        pass

    @abstractmethod
    def get_aggregate_stats(self, url: UrlParameters) -> ImageAggregation:
        ...

    @abstractmethod
    def get_path_from_hash(self, hsh: int) -> str:
        pass


class ImageSqlDB(OmgDB):
    def __init__(self, path_to_date: PathDateExtractor) -> None:
        # TODO: this should be a feature with loader
        self._path_to_date = path_to_date
        self._con = connect("output.db")
        self._features_table = FeaturesTable(self._con)
        self._exif = SQLiteCache(self._features_table, ImageExif)
        self._address = SQLiteCache(self._features_table, GeoAddress)
        self._text_classification = SQLiteCache(self._features_table, ImageClassification)
        self._gallery_index = GalleryIndexTable(self._con)
        self._hash_to_image: t.Dict[int, str] = {}

    def get_path_from_hash(self, hsh: int) -> str:
        return self._hash_to_image[hsh]

    def get_aggregate_stats(self, url: "UrlParameters") -> ImageAggregation:
        return self._gallery_index.get_aggregate_stats(url)

    def get_matching_images(self, url: UrlParameters) -> t.Iterable[Image]:
        for omg in self._gallery_index.get_matching_images(url):
            self._hash_to_image[hash(omg.path)] = omg.path
            yield omg

    def load(self, show_progress: bool) -> None:
        for file, _last_update in tqdm(
            self._features_table.dirty_files(
                [ImageExif.__name__, GeoAddress.__name__, ImageClassification.__name__]
            ),
            desc="reindexing",
            disable=not show_progress,
        ):
            self._reindex(file)
        for file in tqdm(
            self._gallery_index.old_version_files(),
            desc="reindexing old versions",
            disable=not show_progress,
        ):
            self._reindex(file)

    def _reindex(self, path: str) -> None:
        max_last_update = 0.0

        def extract_data(x: t.Optional[t.Tuple[T, float]]) -> t.Optional[T]:
            nonlocal max_last_update
            if x is None:
                return None
            d, time = x
            max_last_update = max(max_last_update, time)
            return d

        exif = extract_data(self._exif.get_with_last_update(path))
        addr = extract_data(self._address.get_with_last_update(path))
        text_cls = extract_data(self._text_classification.get_with_last_update(path))
        omg = Image.from_updates(
            path,
            exif,
            addr,
            text_cls,
            self._path_to_date.extract_date(path),
            max_last_update,
        )
        assert max_last_update > 0.0
        self._gallery_index.add(omg)
        self._features_table.undirty(
            path, [ImageExif.__name__, GeoAddress.__name__, ImageClassification.__name__], max_last_update
        )
