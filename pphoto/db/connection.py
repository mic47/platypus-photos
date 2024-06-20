from datetime import (
    datetime,
    timedelta,
)
import sqlite3
import typing as t

Parameter = t.Union[str, bytes, int, float, None]
MaybeParameters = t.Optional[t.Sequence[Parameter]]


class _Connection:
    def __init__(self, path: str, timeout: int = 120, check_same_thread: bool = True) -> None:
        self._path = path
        self._timeout = timeout
        self._check_same_thread = check_same_thread
        self._last_use = datetime.now()
        self._connection: t.Optional[sqlite3.Connection] = None
        self._disconnect_timeout = timedelta(seconds=10)

    def reconnect(self) -> None:
        if self._connection is not None:
            self._connection.close()
        self._connection = self._connect()

    def check_unused(self) -> None:
        if self._connection is None:
            return
        now = datetime.now()
        if now - self._last_use > self._disconnect_timeout:
            self._connection.close()
            self._connection = None

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, timeout=self._timeout, check_same_thread=self._check_same_thread)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def execute(
        self,
        sql: str,
        parameters: MaybeParameters = None,
    ) -> sqlite3.Cursor:
        self._last_use = datetime.now()
        if self._connection is None:
            self._connection = self._connect()
        if parameters is None:
            return self._connection.execute(sql)
        return self._connection.execute(sql, parameters)

    def executemany(
        self,
        sql: str,
        parameters: t.Sequence[t.Tuple[t.Union[str, bytes, int, float, None], ...]],
    ) -> sqlite3.Cursor:
        self._last_use = datetime.now()
        if self._connection is None:
            self._connection = self._connect()
        return self._connection.executemany(sql, parameters)

    def execute_add_column(
        self,
        sql: str,
    ) -> None:
        try:
            self.execute(sql)
        except sqlite3.OperationalError as e:
            if len(e.args) == 0:
                raise
            if not isinstance(e.args[0], str):
                raise
            if not e.args[0].startswith("duplicate column name"):
                raise
            # It is ok, this is expected

    def commit(self) -> None:
        self._last_use = datetime.now()
        if self._connection is None:
            self._connection = self._connect()
        return self._connection.commit()

    def rollback(self) -> None:
        self._last_use = datetime.now()
        if self._connection is None:
            self._connection = self._connect()
        return self._connection.rollback()


class PhotosConnection(_Connection):
    pass


class GalleryConnection(_Connection):
    pass


class JobsConnection(_Connection):
    pass
