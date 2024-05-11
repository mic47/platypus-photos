import os
import sys
import typing as t
import json
from tqdm import tqdm

from dataclasses_json import DataClassJsonMixin
from dataclasses import dataclass


@dataclass
class HasImage(DataClassJsonMixin):
    image: str
    version: int

    @staticmethod
    def current_version() -> int:
        raise NotImplementedError

    def _set_from_cache(self) -> None:
        self._from_cache = True

    def is_from_cache(self) -> bool:
        if hasattr(self, '_from_cache'):
            return self._from_cache
        return False

    def changed(self) -> bool:
        return not self.is_from_cache()


T = t.TypeVar("T", bound=HasImage)

DEFAULT_VERSION = 0

class Cache(t.Generic[T]):
    def get(self, key: str) -> t.Optional[T]:
        raise NotImplementedError

    def add(self, data: T) -> T:
        raise NotImplementedError

class NoCache(t.Generic[T], Cache[T]):
    def get(self, key: str) -> t.Optional[T]:
        pass

    def add(self, data: T) -> T:
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
        if data.image in self._data:
            return data
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
