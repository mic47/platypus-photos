import os
import sys
import typing as t
import json
from tqdm import tqdm

from dataclasses import dataclass
from dataclasses_json import DataClassJsonMixin

from data_model.features import HasImage
from db.sql import FeaturesTable



T = t.TypeVar("T", bound=HasImage)

DEFAULT_VERSION = 0


class ReadCache(t.Generic[T]):
    def get(self, key: str) -> t.Optional[T]:
        raise NotImplementedError


class WriteCache(t.Generic[T]):
    def add(self, data: T) -> T:
        raise NotImplementedError


class Cache(t.Generic[T], ReadCache[T], WriteCache[T]):
    pass


class NoCache(t.Generic[T], ReadCache[T], WriteCache[T]):
    def get(self, key: str) -> t.Optional[T]:
        pass

    def add(self, data: T) -> T:
        return data


class Loader(t.Generic[T]):
    def __init__(self, path: str, type_: t.Type[T], loader: t.Callable[[T], None]):
        self._position = 0
        self._file = open(path)
        self._loader = loader
        self._type = type_

    def load(self, show_progress: bool) -> None:
        self._file.seek(0, 2)
        end_of_file = self._file.tell()
        self._file.seek(self._position, 0)
        last_position = self._position
        if self._position == end_of_file:
            return
        with tqdm(
            desc=self._type.__name__,
            total=end_of_file - last_position,
            disable=not show_progress,
            unit="bytes",
            unit_scale=True,
        ) as pbar:
            while True:
                position = self._file.tell()
                try:
                    line = self._file.readline()
                    if not line:
                        # End of file reached
                        break
                    j = json.loads(line)
                    if "version" not in j:
                        j["version"] = DEFAULT_VERSION
                    if j.get("version", 0) != self._type.current_version():
                        continue
                    data = self._type.from_dict(j)
                    self._loader(data)
                except Exception as e:
                    # Revert position in the file
                    self._position = position
                    self._file.seek(self._position, 0)
                    print("Error while loading input", e, file=sys.stderr)
                    break
                finally:
                    # Advance position in the file
                    self._position = self._file.tell()
                    pbar.update(self._position - last_position)
                    last_position = self._position

    def __del__(self) -> None:
        self._file.close()


class SQLiteCache(t.Generic[T], Cache[T]):
    def __init__(self, features_table: FeaturesTable, loader: t.Type[T]) -> None:
        self._features_table = features_table
        self._loader = loader
        self._type = loader.__name__
        self._data: t.Dict[str, t.Tuple[int, T]] = {}
        self._current_version = loader.current_version()

    def get(self, key: str) -> t.Optional[T]:
        cached = self._data.get(key)
        res = self._features_table.get_payload(self._type, key)
        if res is None:
            return None
        if cached is not None and cached[0] == res.rowid:
            return cached[1]
        parsed = self._loader.from_json(res.payload)
        self._data[key] = (res.rowid, parsed)
        return parsed

    def get_with_last_update(self, key: str) -> t.Optional[t.Tuple[T, int]]:
        cached = self._data.get(key)
        res = self._features_table.get_payload(self._type, key)
        if res is None:
            return None
        if cached is not None and cached[0] == res.rowid:
            return (cached[1], cached[0])
        parsed = self._loader.from_json(res.payload)
        self._data[key] = (res.rowid, parsed)
        return parsed, res.last_update

    def add(self, data: T) -> T:
        if data.version != self._current_version:
            print(
                "Trying to add wrong version of feature",
                data.version,
                self._current_version,
                data,
                file=sys.stderr,
            )
            return data
        self._features_table.add(
            data.to_json(ensure_ascii=False).encode("utf-8"),
            self._type,
            data.image,
            data.version,
        )
        # NOTE: local cache is just for fetching
        return data


class JsonlCache(t.Generic[T], Cache[T]):
    def __init__(self, path: str, loader: t.Type[T], old_paths: t.List[str] = []):
        self._data = {}
        self._current_version = loader.current_version()

        read_path = None
        if not os.path.exists(path):
            for p in old_paths:
                if os.path.exists(p):
                    read_path = p
                    break
        else:
            read_path = path
        if read_path is not None:
            with open(read_path, "r") as f:
                for line in tqdm(f, desc=f"LOADING: {read_path}"):
                    j = json.loads(line)
                    # Defaulting all versions to 0
                    if "version" not in j:
                        j["version"] = DEFAULT_VERSION
                    cimg = loader.from_dict(j)
                    if cimg.version == self._current_version:
                        cimg._set_from_cache()
                        self._data[cimg.image] = cimg
        self._file = open(path, "a")
        if path != read_path:
            for d in self._data.values():
                self._do_write(d)

    def __del__(self) -> None:
        self._file.close()

    def get(self, key: str) -> t.Optional[T]:
        return self._data.get(key)

    def add(self, data: T) -> T:
        if data.version != self._current_version:
            print(
                "Trying to add wrong version of feature",
                data.version,
                self._current_version,
                data,
                file=sys.stderr,
            )
            return data
        self._data[data.image] = data
        self._do_write(data)
        return data

    def _do_write(self, data: T) -> None:
        self._file.write(data.to_json(ensure_ascii=False))
        self._file.write("\n")
        self._file.flush()


if __name__ == "__main__":
    from image_to_text import ImageClassification
    from image_exif import ImageExif
    from geolocation import GeoAddress

    to_iter: t.List[t.Tuple[str, t.Type[HasImage]]] = [
        ("output-exif.jsonl", ImageExif),
        ("output-geo.jsonl", GeoAddress),
        ("output-image-to-text.jsonl", ImageClassification),
    ]
    for path, type_ in to_iter:
        jsonl = JsonlCache(path, type_)
        sql = SQLiteCache(FeaturesTable("output.db"), type_)
        for path in tqdm(jsonl._data.keys()):
            data = jsonl.get(path)
            if data is None:
                continue
            sql.add(data)
