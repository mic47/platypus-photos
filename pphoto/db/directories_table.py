import typing as t

from pphoto.db.connection import GalleryConnection


class DirectoriesTable:
    def __init__(self, connection: GalleryConnection) -> None:
        self._con = connection
        self._init_db()

    def _init_db(
        self,
    ) -> None:
        self._con.execute(
            """
CREATE TABLE IF NOT EXISTS directories (
  directory TEXT NOT NULL,
  md5 TEXT NOT NULL,
  PRIMARY KEY (directory, md5)
) STRICT;
        """
        )
        for suffix, rows in [
            ("directory", "directory"),
            ("md5", "md5"),
        ]:
            self._con.execute(
                f"""
    CREATE INDEX IF NOT EXISTS directories_idx_{suffix}_file ON directories ({rows});
            """
            )

    def add(
        self,
        directory: str,
        md5: str,
    ) -> None:
        self._con.execute(
            """
INSERT OR IGNORE INTO directories VALUES (?, ?)
            """,
            (
                directory,
                md5,
            ),
        )
        self._con.commit()

    def multi_add(
        self,
        items: t.List[t.Tuple[str, str]],
    ) -> None:
        self._con.executemany(
            """
INSERT OR IGNORE INTO directories VALUES (?, ?)
            """,
            items,
        )
        self._con.commit()

    def by_md5(
        self,
        md5: str,
    ) -> t.List[str]:
        res = self._con.execute(
            "SELECT directory FROM directories WHERE md5 = ?",
            (md5,),
        ).fetchall()
        out = []
        for (directory,) in res:
            out.append(directory)
        return out
