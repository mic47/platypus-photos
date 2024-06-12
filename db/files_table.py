import typing as t

from db.connection import Connection
from db.types import FileRow, ManagedLifecycle, InternalError


class FilesTableWrongLifecycleParams(InternalError):
    def __init__(self, message: str, managed: ManagedLifecycle, tmp_path: t.Optional[str]) -> None:
        super().__init__(
            f"Files table, wrong parameters, {message}: `managed`=`{managed}`, `tmp_path`=`{tmp_path}`"
        )


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
        self._con.execute_add_column(
            """
ALTER TABLE files ADD COLUMN dirty INTEGER NOT NULL DEFAULT 1
        """
        )
        for suffix, rows in [
            ("path", "path"),
            ("md5", "md5"),
            ("managed", "managed"),
            ("dirty", "dirty"),
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
INSERT OR IGNORE INTO files VALUES (?, strftime('%s'), ?, ?, ?, ?, 1)
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
INSERT INTO files VALUES (?, strftime('%s'), ?, ?, ?, ?, 1)
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
UPDATE files SET path=?, dirty=1 WHERE path = ?
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
UPDATE files SET managed=? , tmp_path=?, dirty=1 WHERE path = ?
            """,
            (
                managed.value,
                tmp_path,
                path,
            ),
        )
        self._con.commit()

    def dirty_md5s(self, limit: int = 1000) -> t.List[str]:
        res = self._con.execute(
            f"""
SELECT DISTINCT md5 FROM files WHERE dirty=1 AND managed <> {ManagedLifecycle.BEING_MOVED_AROUND.value} AND managed <> {ManagedLifecycle.IMPORTED.value} LIMIT {limit}
            """
        ).fetchall()
        out = []
        for (md5,) in res:
            out.append(md5)
        return out

    def undirty(self, md5: str, max_last_update: float) -> None:
        self._con.execute(
            """
UPDATE files SET dirty = 0 WHERE dirty=1 AND md5 = ? AND last_update <= ?
            """,
            (md5, max_last_update),
        )

    def by_managed_lifecycle(self, managed: ManagedLifecycle) -> t.List[FileRow]:
        # TODO: test
        res = self._con.execute(
            "SELECT rowid, last_update, path, md5, og_path, tmp_path FROM files WHERE managed = ?",
            (managed.value,),
        ).fetchall()
        out = []
        for rowid, last_update, path, md5, og_path, tmp_path in res:
            out.append(
                FileRow(
                    path,
                    md5,
                    og_path,
                    tmp_path,
                    managed,
                    last_update,
                    rowid,
                )
            )
        return out

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
