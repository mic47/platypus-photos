import typing as t
import sqlite3

from dataclasses import dataclass
from dataclasses_json import DataClassJsonMixin

T = t.TypeVar("T")


@dataclass
class FeaturePayload(t.Generic[T]):
    payload: T
    version: int
    last_update: int
    rowid: int


class FeaturesTable:
    def __init__(self, path: t.Union[str, sqlite3.Connection]) -> None:
        if isinstance(path, str):
            self._con = sqlite3.connect(path)
        else:
            self._con = path
        self._init_db()

    def _init_db(self) -> None:
        self._con.execute(
            """
CREATE TABLE IF NOT EXISTS features (
  type TEXT NOT NULL,
  file TEXT NOT NULL,
  version INT NOT NULL,
  last_update INTEGER NOT NULL,
  dirty INTEGER NOT NULL,
  payload BLOB NOT NULL,
  PRIMARY KEY (type, file)
) STRICT;
        """
        )
        self._con.execute(
            """
CREATE INDEX IF NOT EXISTS features_idx_type_file ON features (type, file);
        """
        )
        self._con.execute(
            """
CREATE INDEX IF NOT EXISTS features_idx_file ON features (file);
        """
        )
        self._con.execute(
            """
CREATE INDEX IF NOT EXISTS features_idx_last_update ON features (last_update);
        """
        )

    def get_payload(self, type_: str, key: str) -> t.Optional[FeaturePayload[bytes]]:
        res = self._con.execute(
            "SELECT rowid, payload, last_update, version FROM features WHERE type = ? AND file = ?",
            (type_, key),
        ).fetchone()
        if res is None:
            return None
        (rowid, payload, last_update, version) = res
        return FeaturePayload(payload, version, last_update, rowid)

    def add(self, payload: bytes, type_: str, path: str, version: int) -> None:
        self._con.execute(
            """
INSERT INTO features VALUES (?, ?, ?, strftime('%s'), 1, ?)
ON CONFLICT(type, file) DO UPDATE SET
  version=excluded.version,
  last_update=excluded.last_update,
  dirty=excluded.dirty,
  payload=excluded.payload
WHERE excluded.version > features.version""",
            (type_, path, version, payload),
        )
        self._con.commit()


class Table:
    def __init__(self, path: t.Union[str, sqlite3.Connection]) -> None:
        if isinstance(path, str):
            self._con = sqlite3.connect(path)
        else:
            self._con = path
        self.features = FeaturesTable(self._con)
        self._init_db()

    def _init_db(self) -> None:
        pass
