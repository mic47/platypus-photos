import typing as t
from pphoto.db.connection import PhotosConnection
from pphoto.db.types import FeaturePayload


class FeaturesFableWrongParams(Exception):
    def __init__(self, message: str, payload: t.Optional[bytes], error: t.Optional[bytes]) -> None:
        super().__init__(
            f"Bug: FeaturesTable wrong parameters, {message}: `payload is None`=`{payload is None}`, `error is None`=`{error is None}`"
        )


class FeaturesTable:
    def __init__(
        self,
        connection: PhotosConnection,
    ) -> None:
        self._con = connection
        self._init_db()

    def _init_db(
        self,
    ) -> None:
        self._con.execute(
            """
CREATE TABLE IF NOT EXISTS features (
  type TEXT NOT NULL,
  md5 TEXT NOT NULL,
  version INT NOT NULL,
  last_update INTEGER NOT NULL,
  dirty INTEGER NOT NULL,
  payload BLOB NOT NULL,
  PRIMARY KEY (type, md5)
) STRICT;
        """
        )
        self._con.execute(
            """
CREATE INDEX IF NOT EXISTS features_idx_type_md5 ON features (type, md5);
        """
        )
        self._con.execute(
            """
CREATE INDEX IF NOT EXISTS features_idx_md5 ON features (md5);
        """
        )
        self._con.execute(
            """
CREATE INDEX IF NOT EXISTS features_idx_last_update ON features (last_update);
        """
        )
        self._con.execute_add_column(
            """
ALTER TABLE features ADD column is_error INT NOT NULL DEFAULT 0;"""
        )
        self._con.execute(
            """
CREATE INDEX IF NOT EXISTS features_idx_is_error ON features (is_error);
        """
        )

    def undirty(
        self,
        md5: str,
        types: t.List[str],
        max_last_update: float,
    ) -> None:
        q = ", ".join(f"'{qt}'" for qt in types)
        (
            query,
            param,
        ) = (
            f"UPDATE features SET dirty = 0 WHERE dirty > 0 AND md5 = ? AND type in ({q}) AND last_update <= ?",
            (
                md5,
                max_last_update,
            ),
        )
        self._con.execute(
            query,
            param,
        )
        self._con.commit()

    def dirty_md5s(
        self,
        types: t.List[str],
        limit: int = 1000,
    ) -> t.Iterable[
        t.Tuple[
            str,
            int,
        ]
    ]:
        if types:
            q = ", ".join(f"'{qt}'" for qt in types)
            res = self._con.execute(
                f"SELECT md5, MAX(last_update) FROM features WHERE dirty > 0 AND type in ({q}) GROUP BY md5 LIMIT {limit}"
            )
        else:
            res = self._con.execute(
                f"SELECT md5, MAX(last_update) FROM features WHERE dirty > 0 GROUP BY md5 LIMIT {limit}"
            )
        while True:
            items = res.fetchmany()
            if not items:
                return
            yield from items

    def get_payload(
        self,
        type_: str,
        key: str,
    ) -> t.Optional[FeaturePayload[bytes, bytes]]:
        res = self._con.execute(
            "SELECT rowid, payload, is_error, last_update, version FROM features WHERE type = ? AND md5 = ?",
            (
                type_,
                key,
            ),
        ).fetchone()
        if res is None:
            return None
        (
            rowid,
            payload,
            is_error,
            last_update,
            version,
        ) = res
        # Payload column cannot be null, so we need handle empty strings
        payload = None if not payload else payload
        return FeaturePayload(
            payload if is_error == 0 else None,
            None if is_error == 0 else payload,
            version,
            last_update,
            rowid,
        )

    def add(
        self,
        payload: t.Optional[bytes],
        error: t.Optional[bytes],
        type_: str,
        md5: str,
        version: int,
    ) -> None:
        if (payload is None) == (error is None):
            raise FeaturesFableWrongParams("You have to provide payload XOR error", payload, error)
        self._con.execute(
            """
INSERT INTO features VALUES (?, ?, ?, strftime('%s'), 1, ?, ?)
ON CONFLICT(type, md5) DO UPDATE SET
  version=excluded.version,
  last_update=excluded.last_update,
  dirty=excluded.dirty,
  payload=excluded.payload,
  is_error=excluded.is_error
WHERE
  excluded.version > features.version
  OR (
    excluded.version == features.version
    AND excluded.payload != features.payload
  )""",
            (type_, md5, version, payload or error, 1 if payload is None else 0),
        )
        self._con.commit()
