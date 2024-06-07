import typing as t

from db.connection import Connection
from db.types import FileRow, ManagedLifecycle


class InternalError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(f"Internal error, this si bug: {message}")


class FilesTableWrongLifecycleParams(InternalError):
    def __init__(self, message: str, managed: ManagedLifecycle, tmp_path: t.Optional[str]) -> None:
        super().__init__(f"Wrong parameters, {message}: `managed`=`{managed}`, `tmp_path`=`{tmp_path}`")


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
        self._con.execute_add_column(
            """
ALTER TABLE files ADD COLUMN og_path TEXT
        """
        )
        self._con.execute_add_column(
            """
ALTER TABLE files ADD COLUMN tmp_path TEXT
        """
        )
        self._con.execute_add_column(
            """
ALTER TABLE files ADD COLUMN managed INTEGER NOT NULL DEFAULT 0
        """
        )
        for suffix, rows in [
            ("path", "path"),
            ("md5", "md5"),
            ("managed", "managed"),
            # Explicitly skipping indices for these
            # `og_path` -- it is just payload, no intention to search for it
            # `tmp_path` -- again, this is payload
        ]:
            self._con.execute(
                f"""
    CREATE INDEX IF NOT EXISTS files_idx_{suffix}_file ON files ({rows});
            """
            )

    def add_if_not_exists(
        self,
        path: str,
        md5: t.Optional[str],
        og_path: t.Optional[str],
        managed: ManagedLifecycle,
        tmp_path: t.Optional[str],
    ) -> None:
        self._validate_lifecycle(managed, tmp_path)
        self._con.execute(
            """
INSERT OR IGNORE INTO files VALUES (?, strftime('%s'), ?, ?, ?, ?)
            """,
            (
                path,
                md5,
                og_path,
                tmp_path,
                managed.value,
            ),
        )
        self._con.commit()

    def add_or_update(
        self,
        path: str,
        md5: t.Optional[str],
        og_path: t.Optional[str],
        managed: ManagedLifecycle,
        tmp_path: t.Optional[str],
    ) -> None:
        self._validate_lifecycle(managed, tmp_path)
        self._con.execute(
            """
INSERT INTO files VALUES (?, strftime('%s'), ?, ?, ?, ?)
ON CONFLICT(path) DO UPDATE SET
  last_update=excluded.last_update,
  md5=excluded.md5,
  tmp_path=excluded.tmp_path,
  managed=excluded.managed
            """,
            (
                path,
                md5,
                og_path,
                tmp_path,
                managed.value,
            ),
        )
        self._con.commit()

    def _validate_lifecycle(
        self,
        managed: ManagedLifecycle,
        tmp_path: t.Optional[str],
    ) -> None:
        if managed == ManagedLifecycle.BEING_MOVED_AROUND:
            if tmp_path is None:
                raise FilesTableWrongLifecycleParams(
                    "`tmp_path` must not be None when moving file around", managed, tmp_path
                )
        else:
            if tmp_path is not None:
                raise FilesTableWrongLifecycleParams(
                    "`tmp_path` must be None when not movinf file around", managed, tmp_path
                )

    def change_path(
        self,
        old_path: str,
        new_path: str,
    ) -> None:
        self._con.execute(
            """
UPDATE files SET path=? WHERE path = ?
            """,
            (new_path, old_path),
        )
        self._con.commit()

    def set_lifecycle(
        self,
        path: str,
        managed: ManagedLifecycle,
        tmp_path: t.Optional[str],
    ) -> None:
        self._validate_lifecycle(managed, tmp_path)
        self._con.execute(
            """
UPDATE files SET managed=? , tmp_path=? WHERE path = ?
            """,
            (
                managed.value,
                tmp_path,
                path,
            ),
        )
        self._con.commit()

    def by_path(
        self,
        path: str,
    ) -> t.Optional[FileRow]:
        res = self._con.execute(
            "SELECT rowid, last_update, md5, og_path, tmp_path, managed  FROM files WHERE path = ?",
            (path,),
        ).fetchone()
        if res is None:
            return None
        (
            rowid,
            last_update,
            md5,
            og_path,
            tmp_path,
            managed,
        ) = res
        return FileRow(
            path,
            md5,
            og_path,
            tmp_path,
            ManagedLifecycle(managed),
            last_update,
            rowid,
        )

    def example_by_md5(
        self,
        md5: str,
    ) -> t.Optional[FileRow]:
        res = self._con.execute(
            "SELECT rowid, last_update, path, og_path, tmp_path, managed FROM files WHERE md5 = ?",
            (md5,),
        ).fetchone()
        if res is None:
            return None
        (
            rowid,
            last_update,
            path,
            og_path,
            tmp_path,
            managed,
        ) = res
        return FileRow(
            path,
            md5,
            og_path,
            tmp_path,
            ManagedLifecycle(managed),
            last_update,
            rowid,
        )

    def by_md5(
        self,
        md5: str,
    ) -> t.List[FileRow]:
        res = self._con.execute(
            "SELECT rowid, last_update, path, og_path, tmp_path, managed FROM files WHERE md5 = ?",
            (md5,),
        ).fetchall()
        out = []
        for rowid, last_update, path, og_path, tmp_path, managed in res:
            out.append(
                FileRow(
                    path,
                    md5,
                    og_path,
                    tmp_path,
                    ManagedLifecycle(managed),
                    last_update,
                    rowid,
                )
            )
        return out
