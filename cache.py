import os
import typing as t

from dataclasses_json import DataClassJsonMixin
from dataclasses import dataclass


@dataclass
class HasImage(DataClassJsonMixin):
    image: str


T = t.TypeVar("T", bound=HasImage)


class JsonlCache(t.Generic[T]):
    def __init__(self, path: str, loader: t.Type[T], old_paths: t.List[str] = []):
        self._data = {}

        read_path = None
        if not os.path.exists(path):
            for p in old_paths:
                if os.path.exists(p):
                    read_path = p
                    break
        else:
            read_path = path
        if read_path is not None:
            print("LOADING", read_path)
            with open(read_path, "r") as f:
                for line in f:
                    cimg = loader.from_json(line)
                    self._data[cimg.image] = cimg
        self._file = open(path, "a")
        if path != read_path:
            for d in self._data.values():
                self._do_write(d)

    def __del__(self) -> None:
        self._file.close()

    def get(self, key: str) -> t.Optional[T]:
        return self._data.get(key)

    def add(self, data: T) -> None:
        if data.image in self._data:
            return
        self._data[data.image] = data
        self._do_write(data)

    def _do_write(self, data: T) -> None:
        self._file.write(data.to_json(ensure_ascii=False))
        self._file.write("\n")
        self._file.flush()
