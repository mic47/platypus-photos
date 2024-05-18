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
        if hasattr(self, "_from_cache"):
            return self._from_cache
        return False

    def changed(self) -> bool:
        return not self.is_from_cache()


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
        with tqdm(total=end_of_file - last_position, disable=not show_progress) as pbar:
            while True:
                position = self._file.tell()
                try:
                    line = self._file.readline()
                    if not line:
                        # End of file reached
                        break
                    j = json.loads(line)
                    if (j.get("version") or 0) != self._type.current_version():
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
