import typing as t

from pphoto.db.connection import PhotosConnection
from pphoto.db.types_identity import IdentityRowPayload


class IdentityTable:
    def __init__(self, connection: PhotosConnection) -> None:
        self._con = connection
        self._init_db()

    def _init_db(
        self,
    ) -> None:
        self._con.execute(
            """
CREATE TABLE IF NOT EXISTS identities (
  identity TEXT NOT NULL PRIMARY KEY,
  example_md5 TEXT,
  example_extension TEXT,
  updates INTEGER NOT NULL,
  last_update INTEGER NOT NULL
) STRICT;
        """
        )
        for suffix, rows in [
            ("identity", "identity"),
            ("updates", "updates"),
            ("last_update", "last_update"),
        ]:
            self._con.execute(
                f"""
    CREATE INDEX IF NOT EXISTS identities_idx_{suffix}_file ON identities ({rows});
            """
            )

    def add(
        self, identity: str, example_md5: str | None, example_extension: str | None, increment: bool
    ) -> None:
        self._con.execute(
            """
INSERT INTO identities VALUES (?, ?, ?, ?, strftime('%s'))
ON CONFLICT(identity) DO UPDATE SET
  last_update=excluded.last_update,
  updates=updates + excluded.updates,
  example_md5=COALESCE(example_md5, excluded.example_md5),
  example_extension=COALESCE(example_extension, excluded.example_extension)
            """,
            (
                identity,
                example_md5,
                example_extension,
                1 if increment else 0,
            ),
        )
        self._con.commit()

    def top_identities(
        self,
        limit: None | int = 100,
    ) -> t.List[IdentityRowPayload]:
        res = self._con.execute(
            "SELECT identity, example_md5, example_extension, updates, last_update FROM identities"
            + (f" ORDER BY updates DESC LIMIT {limit}" if limit is not None else ""),
        ).fetchall()
        out = []
        for identity, example_md5, example_extension, updates, last_update in res:
            out.append(IdentityRowPayload(identity, example_md5, example_extension, updates, last_update))
        return out
