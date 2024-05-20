from abc import ABC, abstractmethod
from collections import Counter
import typing as t
from tqdm import tqdm

from image_to_text import ImageClassification
from image_exif import ImageExif
from geolocation import GeoAddress
from filename_to_date import PathDateExtractor
from cache import Loader

from gallery.url import UrlParameters
from gallery.image import Image, ImageAggregation
from gallery.utils import maybe_datetime_to_timestamp


class OmgDB(ABC):
    @abstractmethod
    def load(self, show_progress: bool) -> None:
        pass

    @abstractmethod
    def get_matching_images(self, url: "UrlParameters") -> t.Iterable[Image]:
        pass

    @abstractmethod
    def get_aggregate_stats(self, url: "UrlParameters") -> ImageAggregation:
        pass

    @abstractmethod
    def get_path_from_hash(self, hsh: int) -> str:
        pass


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
        yield from out

    def get_aggregate_stats(self, url: "UrlParameters") -> ImageAggregation:
        tag_cnt: t.Counter[str] = Counter()
        classifications_cnt: t.Counter[str] = Counter()
        address_cnt: t.Counter[str] = Counter()
        for omg in self.get_matching_images(url):
            classifications_cnt.update([] if omg.classifications is None else omg.classifications.split(";"))
            tag_cnt.update((omg.tags or {}).keys())
            address_cnt.update(a for a in [omg.address_name, omg.address_country] if a)
        return ImageAggregation(address=address_cnt, tag=tag_cnt, classification=classifications_cnt)

    def get_path_from_hash(self, hsh: int) -> str:
        return self._hash_to_image[hsh]

    def _reindex(self, path: str) -> None:
        omg = Image.from_updates(
            path,
            self._exif.get(path),
            self._address.get(path),
            self._text_classification.get(path),
            self._path_to_date.extract_date(path),
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
