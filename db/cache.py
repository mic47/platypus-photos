import sys
import typing as t

from data_model.features import HasCurrentVersion, WithMD5, Error
from db.features_table import FeaturesTable
from db.types import FeaturePayload


Ser = t.TypeVar("Ser", bound=HasCurrentVersion)

DEFAULT_VERSION = 0


class Cache(t.Generic[Ser]):
    def get(self, key: str) -> t.Optional[FeaturePayload[WithMD5[Ser], None]]:
        raise NotImplementedError

    def add(self, data: WithMD5[Ser]) -> WithMD5[Ser]:
        raise NotImplementedError


class NoCache(t.Generic[Ser], Cache[Ser]):
    def get(self, key: str) -> t.Optional[FeaturePayload[WithMD5[Ser], None]]:
        pass

    def add(self, data: WithMD5[Ser]) -> WithMD5[Ser]:
        return data


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
        self._data: t.Dict[str, FeaturePayload[WithMD5[Ser], None]] = {}
        self._current_version = loader.current_version()
        self._enforce_version = enforce_version
        self._jsonl = JsonlWriter(jsonl_path)

    def get(self, key: str) -> t.Optional[FeaturePayload[WithMD5[Ser], None]]:
        cached = self._data.get(key)
        res = self._features_table.get_payload(self._type, key)
        if res is None:
            return None
        if cached is not None and cached.rowid == res.rowid and cached.last_update == res.last_update:
            return cached
        if res.payload is not None:
            parsed = WithMD5(key, res.version, self._loader.from_json(res.payload), None)
        elif res.error is not None:
            parsed = WithMD5(key, res.version, None, Error.from_json(res.error))
        else:
            assert False, "FeaturePayload is missing payload and error"
        ret = t.cast(FeaturePayload[WithMD5[Ser], None], res)
        ret.payload = parsed
        ret.error = None
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
        if data.p is None:
            d = None
        else:
            d = data.p.to_json().encode("utf-8")
        if data.e is None:
            e = None
        else:
            e = data.e.to_json().encode("utf-8")
        self._features_table.add(
            d,
            e,
            self._type,
            data.md5,
            data.version,
        )

        self._jsonl.append(data.to_json())
        # NOTE: local cache is just for fetching
        return data
