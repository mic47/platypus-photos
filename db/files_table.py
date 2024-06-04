import typing as t

from db.connection import Connection
from db.types import FileRow


class FilesTable:
    def __init__(self, connection: Connection) -> None:
        self._con = connection
        self._init_db()

    def _init_db(
        self,
    ) -> None:
        self._con.execute(
            """
CREATE TABLE IF NOT EXISTS files (
  path TEXT NOT NULL PRIMARY KEY,
  last_update INTEGER NOT NULL,
  md5 TEXT
) STRICT;
        """
        )
        for (suffix, rows) in [("path", "path"), ("md5", "md5")]:
            self._con.execute(
                f"""
    CREATE INDEX IF NOT EXISTS files_idx_{suffix}_file ON files ({rows});
            """
            )

    def add(
        self,
        path: str,
        md5: t.Optional[str],
    ) -> None:
        self._con.execute(
            """
INSERT INTO files VALUES (?, strftime('%s'), ?)
ON CONFLICT(path) DO UPDATE SET
  last_update=excluded.last_update,
  md5=excluded.md5
            """,
            (
                path,
                md5,
            ),
        )
        self._con.commit()

    def by_path(
        self,
        path: str,
    ) -> t.Optional[FileRow]:
        res = self._con.execute(
            "SELECT rowid, last_update, md5 FROM files WHERE path = ?",
            (path,),
        ).fetchone()
        if res is None:
            return None
        (
            rowid,
            last_update,
            md5,
        ) = res
        return FileRow(
            path,
            md5,
            last_update,
            rowid,
        )

    def example_by_md5(
        self,
        md5: str,
    ) -> t.Optional[FileRow]:
        res = self._con.execute(
            "SELECT rowid, last_update, path FROM files WHERE md5 = ?",
            (md5,),
        ).fetchone()
        if res is None:
            return None
        (
            rowid,
            last_update,
            path,
        ) = res
        return FileRow(
            path,
            md5,
            last_update,
            rowid,
        )

    def by_md5(
        self,
        md5: str,
    ) -> t.List[FileRow]:
        res = self._con.execute(
            "SELECT rowid, last_update, path FROM files WHERE md5 = ?",
            (md5,),
        ).fetchall()
        out = []
        for (
            rowid,
            last_update,
            path,
        ) in res:
            out.append(
                FileRow(
                    path,
                    md5,
                    last_update,
                    rowid,
                )
            )
        return out
