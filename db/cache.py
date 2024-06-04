import sys
import typing as t
import json
import os
import traceback

from tqdm import tqdm

from data_model.features import WithImage, HasCurrentVersion, WithMD5
from db import FeaturesTable, Connection, FilesTable
from db.types import FileRow, FeaturePayload


Ser = t.TypeVar("Ser", bound="HasCurrentVersion")

DEFAULT_VERSION = 0


class Cache(t.Generic[Ser]):
    def get(self, key: str) -> t.Optional[FeaturePayload[WithMD5[Ser]]]:
        raise NotImplementedError

    def add(self, data: WithMD5[Ser]) -> WithMD5[Ser]:
        raise NotImplementedError


class NoCache(t.Generic[Ser], Cache[Ser]):
    def get(self, key: str) -> t.Optional[FeaturePayload[WithMD5[Ser]]]:
        pass

    def add(self, data: WithMD5[Ser]) -> WithMD5[Ser]:
        return data


class WithImageLoader(t.Generic[Ser]):
    def __init__(self, path: str, type_: t.Type[Ser], loader: t.Callable[[WithImage[Ser]], None]):
        self._position = 0
        # pylint: disable=consider-using-with
        self._file = open(path, encoding="utf-8")
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
                    self._loader(WithImage.load(j, data))
                # pylint: disable = broad-exception-caught
                except Exception as e:
                    # Revert position in the file
                    self._position = position
                    self._file.seek(self._position, 0)
                    print("Error while loading input", e, file=sys.stderr)
                    traceback.print_exc()
                    break
                finally:
                    # Advance position in the file
                    self._position = self._file.tell()
                    pbar.update(self._position - last_position)
                    last_position = self._position

    def __del__(self) -> None:
        self._file.close()


class JsonlWriter:
    def __init__(self, path: t.Optional[str]):
        if path is None:
            self._file = None
        else:
            # pylint: disable=consider-using-with
            self._file = open(path, "a", encoding="utf-8")

    def append(self, data: str) -> None:
        if self._file is None:
            return
        self._file.write(data)
        self._file.write("\n")
        self._file.flush()


class SQLiteCache(t.Generic[Ser], Cache[Ser]):
    def __init__(
        self,
        features_table: FeaturesTable,
        loader: t.Type[Ser],
        jsonl_path: t.Optional[str] = None,
        enforce_version: bool = False,
    ) -> None:
        self._features_table = features_table
        self._loader = loader
        self._type = loader.__name__
        self._data: t.Dict[str, FeaturePayload[WithMD5[Ser]]] = {}
        self._current_version = loader.current_version()
        self._enforce_version = enforce_version
        self._jsonl = JsonlWriter(jsonl_path)

    def get(self, key: str) -> t.Optional[FeaturePayload[WithMD5[Ser]]]:
        cached = self._data.get(key)
        res = self._features_table.get_payload(self._type, key)
        if res is None:
            return None
        if cached is not None and cached.rowid == res.rowid:
            return cached
        parsed = WithMD5(key, res.version, self._loader.from_json(res.payload))
        ret = t.cast(FeaturePayload[WithMD5[Ser]], res)
        ret.payload = parsed
        self._data[key] = ret
        return ret

    def add(self, data: WithMD5[Ser]) -> WithMD5[Ser]:
        if data.version != self._current_version:
            print(
                "Trying to add wrong version of feature",
                data.version,
                self._current_version,
                data,
                file=sys.stderr,
            )
            return data
        d = data.p.to_json()
        self._features_table.add(
            d.encode("utf-8"),
            self._type,
            data.md5,
            data.version,
        )

        self._jsonl.append(data.to_json())
        # NOTE: local cache is just for fetching
        return data


class FilesCache:
    def __init__(
        self,
        files_table: FilesTable,
        jsonl_path: t.Optional[str] = None,
    ) -> None:
        self._files_table = files_table
        self._by_path: t.Dict[str, FileRow] = {}
        self._jsonl = JsonlWriter(jsonl_path)

    def get(self, path: str) -> t.Optional[FileRow]:
        ret = self._by_path.get(path)
        if ret is not None:
            return None
        ret = self._files_table.by_path(path)
        if ret is not None:
            self._by_path[path] = ret
            return ret
        return None

    def add(self, path: str, md5: str) -> None:
        self._files_table.add(path, md5)
        self._jsonl.append(json.dumps({"path": path, "md5": md5}, ensure_ascii=False))


def main() -> None:
    # pylint: disable=import-outside-toplevel
    from annots.md5 import compute_md5

    # pylint: disable=import-outside-toplevel
    from data_model.features import ImageClassification

    # pylint: disable=import-outside-toplevel
    from data_model.features import ImageExif

    # pylint: disable=import-outside-toplevel
    from data_model.features import GeoAddress

    # pylint: disable=import-outside-toplevel
    from data_model.features import MD5Annot

    conn = Connection("data/photos.db")
    conn.execute("PRAGMA synchronous=OFF;")
    cache = FilesCache(FilesTable(conn), "data/output-files.jsonl")

    def ldmd5(x: WithImage[MD5Annot]) -> None:
        cache.add(x.image, x.p.md5)

    loader_md5 = WithImageLoader("output-md5.jsonl", MD5Annot, ldmd5)
    loader_md5.load(show_progress=True)
    conn.reconnect()

    to_iter: t.List[t.Tuple[str, t.Type[HasCurrentVersion]]] = [
        ("output-exif.jsonl", ImageExif),
        ("output-geo.jsonl", GeoAddress),
        ("output-image-to-text.jsonl", ImageClassification),
    ]
    for path, type_ in to_iter:
        sql = SQLiteCache(FeaturesTable(conn), type_, f"data/{path}")

        def load(x: WithImage[HasCurrentVersion]) -> None:
            row = cache.get(x.image)
            if row is not None:
                md5 = row.md5
            else:
                if not os.path.exists(x.image):
                    return
                md5 = compute_md5(x.image).md5
                cache.add(x.image, md5)
            # pylint: disable = cell-var-from-loop
            sql.add(WithMD5(md5, x.version, x.p))

        loader = WithImageLoader(path, type_, load)
        loader.load(show_progress=True)
        conn.reconnect()


if __name__ == "__main__":
    main()
