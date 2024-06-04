from datetime import (
    datetime,
    timedelta,
)
import sqlite3
import typing as t


class Connection:
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
        parameters: t.Optional[t.Sequence[t.Union[str, bytes, int, float, None]]] = None,
    ) -> sqlite3.Cursor:
        self._last_use = datetime.now()
        if self._connection is None:
            self._connection = self._connect()
        if parameters is None:
            return self._connection.execute(sql)
        return self._connection.execute(sql, parameters)

    def commit(self) -> None:
        self._last_use = datetime.now()
        if self._connection is None:
            self._connection = self._connect()
        return self._connection.commit()
