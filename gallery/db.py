from abc import ABC, abstractmethod
from collections import Counter
import copy
import typing as t
from tqdm import tqdm
from datetime import datetime

import sqlite3

from image_to_text import ImageClassification
from image_exif import ImageExif
from geolocation import GeoAddress
from filename_to_date import PathDateExtractor
from cache import Loader, SQLiteCache

from db.sql import FeaturesTable
from gallery.url import UrlParameters
from gallery.image import Image, ImageAggregation
from gallery.utils import maybe_datetime_to_timestamp

T = t.TypeVar("T")


class OmgDB(ABC):
    @abstractmethod
    def load(self, show_progress: bool) -> None:
        pass

    @abstractmethod
    def get_matching_images(self, url: "UrlParameters") -> t.Iterable[Image]:
        pass

    @abstractmethod
    def get_aggregate_stats(self, url: "UrlParameters") -> ImageAggregation:
        ...

    @abstractmethod
    def get_path_from_hash(self, hsh: int) -> str:
        pass


class ImageSqlDB(OmgDB):
    def __init__(self, path_to_date: PathDateExtractor) -> None:
        # TODO: this should be a feature with loader
        self._path_to_date = path_to_date
        self._con = sqlite3.connect("output.db")
        self._exif = SQLiteCache(FeaturesTable(self._con), ImageExif)
        self._address = SQLiteCache(FeaturesTable(self._con), GeoAddress)
        self._text_classification = SQLiteCache(FeaturesTable(self._con), ImageClassification)
        self._hash_to_image: t.Dict[int, str] = {}
        self._init_db()

    def _init_db(self) -> None:
        self._con.execute(
            """
CREATE TABLE IF NOT EXISTS gallery_index (
  file TEXT NOT NULL,
  feature_last_update INT NOT NULL,
  timestamp INTEGER,
  tags TEXT,
  tags_probs TEXT,
  classifications TEXT,
  address_country TEXT,
  address_name TEXT,
  address_full TEXT,
  PRIMARY KEY (file)
) STRICT;"""
        )
        for columns in [
            ["file"],
            ["feature_last_update"],
            ["timestamp"],
            ["tags"],
            ["classifications"],
            ["address_full"],
        ]:
            name = f"gallery_index_idx_{'_'.join(columns)}"
            cols_str = ", ".join(columns)
            self._con.execute(f"CREATE INDEX IF NOT EXISTS {name} ON gallery_index ({cols_str});")

    def _insert(self, omg: Image, last_update: float) -> None:
        tags = sorted(list((omg.tags or {}).items()))
        self._con.execute(
            """
INSERT INTO gallery_index VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(file) DO UPDATE SET
  feature_last_update=excluded.feature_last_update,
  timestamp=excluded.timetamp,
  tags=excluded.tags,
  tags_probs=excluded.tags_probs,
  classifications=excluded.classifications,
  address_country=excluded.address_country,
  address_name=excluded.address_name,
  address_full=excluded.address_full,
WHERE excluded.feature_last_update > gallery_index.feature_last_update""",
            (
                omg.path,
                last_update,
                maybe_datetime_to_timestamp(omg.date),
                ":".join([t for t, _ in tags]),
                ":".join([f"{p:.4f}" for p, _ in tags]),
                omg.classifications,
                omg.address_country,
                omg.address_name,
                omg.address_full,
            ),
        )
        self._con.commit()

    def get_aggregate_stats(self, url: "UrlParameters") -> ImageAggregation:
        # do aggregate query
        pass

    def get_matching_images(self, url: "UrlParameters") -> t.Iterable[Image]:
        # TODO: aggregations could be done separately
        # TODO: sorting and stuff
        clauses = []
        variables: t.List[t.Union[str, int, float, None]] = []
        if url.addr:
            clauses.append("address_full like %?%")
            variables.append(url.addr)
        if url.cls:
            clauses.append("classifications like %?%")
            variables.append(url.cls)
        if url.tag:
            clauses.append("tags like %?%")
            variables.append(url.tag)
        if url.datefrom:
            clauses.append("timestamp >= ?")
            variables.append(maybe_datetime_to_timestamp(url.datefrom))
        if url.dateto:
            clauses.append("timestamp <= ?")
            variables.append(maybe_datetime_to_timestamp(url.dateto))
        if clauses:
            where = "WHERE " + "AND".join(clauses)
        else:
            where = ""
        query = f"""
        SELECT file, timestamp, tags, tags_probs, classifications, address_country, address_name, address_full
        FROM gallery_index
        {where}
        ORDER BY timestamp DESC
        """
        res = self._con.execute(query, variables)
        while True:
            items = res.fetchmany(size=url.paging)
            if not items:
                return
            for (
                file,
                timestamp,
                tags,
                tags_probs,
                classifications,
                address_country,
                address_name,
                address_full,
            ) in items:
                yield Image(
                    file,
                    None if timestamp is None else datetime.fromtimestamp(timestamp),  # TODO convert
                    dict(zip(tags.split(":"), tags_probs.split(":"))),
                    classifications,
                    address_country,
                    address_name,
                    address_full,
                )

    def load(self, show_progress: bool) -> None:
        # Check those that have dirty flag & not newwer image
        # Maybe on start do something else
        pass

    def _reindex(self, path: str) -> None:
        max_last_update = 0.0

        def extract_data(x: t.Optional[t.Tuple[T, float]]) -> t.Optional[T]:
            nonlocal max_last_update
            if x is None:
                return None
            d, time = x
            max_last_update = max(max_last_update, time)
            return d

        omg = Image.from_updates(
            path,
            extract_data(self._exif.get_with_last_update(path)),
            extract_data(self._address.get_with_last_update(path)),
            extract_data(self._text_classification.get_with_last_update(path)),
            self._path_to_date.extract_date(path),
        )
        assert max_last_update > 0.0
        self._insert(omg, max_last_update)
        # TODO: move this elsewhere?
        self._hash_to_image[hash(omg.path)] = omg.path


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
