from abc import ABC, abstractmethod
from collections import Counter
import copy
import typing as t

from tqdm import tqdm

from image_to_text import ImageClassification
from image_exif import ImageExif
from geolocation import GeoAddress
from filename_to_date import PathDateExtractor
from cache import Loader, SQLiteCache

from db.sql import FeaturesTable, GalleryIndexTable, connect
from db.types import ImageAggregation, Image
from gallery.url import UrlParameters
from gallery.utils import maybe_datetime_to_timestamp

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


class ImageDB(OmgDB):
    def __init__(self, path_to_date: PathDateExtractor) -> None:
        # TODO: this should be a feature with loader
        self._path_to_date = path_to_date

        self._exif: t.Dict[str, ImageExif] = {}
        self._address: t.Dict[str, GeoAddress] = {}
        self._text_classification: t.Dict[str, ImageClassification] = {}
        self._loaders: t.List[Loader[t.Any]] = [
            Loader("output-exif.jsonl", ImageExif, self._load_exif),
            Loader("output-geo.jsonl", GeoAddress, self._load_address),
            Loader("output-image-to-text.jsonl", ImageClassification, self._load_text_classification),
        ]

        self._images: t.List[Image] = []
        self._image_to_index: t.Dict[str, int] = {}
        self._hash_to_image: t.Dict[int, str] = {}
        self._dirty_paths: t.Set[str] = set()

    def load(self, show_progress: bool) -> None:
        for loader in self._loaders:
            loader.load(show_progress=show_progress)
        for path in tqdm(self._dirty_paths, desc="Re-index", disable=not show_progress):
            self._reindex(path)
        self._dirty_paths.clear()

    def get_matching_images(self, url: "UrlParameters") -> t.Iterable[Image]:
        out = []
        for image in self._images:
            if image.match_url(url):
                out.append(image)
        out.sort(key=lambda x: maybe_datetime_to_timestamp(x.date) or 0.0, reverse=True)
        if url.paging:
            yield from out[url.page * url.paging : (url.page + 1) * url.paging]
        else:
            yield from out

    def get_aggregate_stats(self, url: "UrlParameters") -> ImageAggregation:
        url = copy.copy(url)
        url.paging = 0
        tag_cnt: t.Counter[str] = Counter()
        classifications_cnt: t.Counter[str] = Counter()
        address_cnt: t.Counter[str] = Counter()
        total = 0
        for omg in self.get_matching_images(url):
            total += 1
            classifications_cnt.update([] if omg.classifications is None else omg.classifications.split(";"))
            tag_cnt.update((omg.tags or {}).keys())
            address_cnt.update(a for a in [omg.address_name, omg.address_country] if a)
        return ImageAggregation(total, address=address_cnt, tag=tag_cnt, classification=classifications_cnt)

    def get_path_from_hash(self, hsh: int) -> str:
        return self._hash_to_image[hsh]

    def _reindex(self, path: str) -> None:
        omg = Image.from_updates(
            path,
            self._exif.get(path),
            self._address.get(path),
            self._text_classification.get(path),
            self._path_to_date.extract_date(path),
            -1,
        )
        _index = self._image_to_index.get(omg.path)
        if _index is None:
            self._image_to_index[omg.path] = len(self._images)
            self._images.append(omg)
        else:
            self._images[_index] = omg
        self._hash_to_image[hash(omg.path)] = omg.path

    def _load_exif(self, exif: ImageExif) -> None:
        self._exif[exif.image] = exif
        self._dirty_paths.add(exif.image)

    def _load_address(self, addr: GeoAddress) -> None:
        self._address[addr.image] = addr
        self._dirty_paths.add(addr.image)

    def _load_text_classification(self, annot: ImageClassification) -> None:
        self._text_classification[annot.image] = annot
        self._dirty_paths.add(annot.image)
