from __future__ import annotations

import datetime
import typing as t

from pphoto.db.connection import JobsConnection, Parameter
from pphoto.remote_jobs.types import RemoteJobType, RemoteTask, RemoteJob, TaskId


class RemoteJobsTable:
    def __init__(self, connection: JobsConnection) -> None:
        self._con = connection
        self._init_db()

    def _init_db(
        self,
    ) -> None:
        self._con.execute(
            """
CREATE TABLE IF NOT EXISTS remote_tasks (
  md5 TEXT NOT NULL,
  job_id INTEGER NOT NULL,
  type TEXT NOT NULL,
  payload_json BLOB NOT NULL,
  created INTEGER NOT NULL,
  finished_at INTEGER,
  PRIMARY KEY (md5, job_id)
) STRICT;
            """
        )
        self._con.execute(
            """
CREATE TABLE IF NOT EXISTS remote_jobs (
  id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
  type TEXT NOT NULL,
  total INTEGER NOT NULL,
  finished_tasks INTEGER NOT NULL,
  original_request_json BLOB NOT NULL,
  created INTEGER NOT NULL,
  last_update INTEGER
) STRICT;
            """
        )
        self._con.execute(
            """
CREATE TRIGGER IF NOT EXISTS
  remote_tasks_on_finish
AFTER UPDATE OF finished_at ON remote_tasks
FOR EACH ROW WHEN OLD.finished_at IS NULL and NEW.finished_at IS NOT NULL
BEGIN
  UPDATE remote_jobs SET finished_tasks = finished_tasks + 1, last_update = NEW.finished_at WHERE id = OLD.job_id;
END;
    """
        )
        self._con.execute_add_column(
            """
ALTER TABLE remote_jobs ADD COLUMN example_path_md5 TEXT;
            """
        )
        self._con.execute_add_column(
            """
ALTER TABLE remote_jobs ADD COLUMN example_path_extension TEXT;
            """
        )
        for suffix, rows in [
            ("md5_job_id", "md5, job_id"),
            ("job_id", "job_id"),
        ]:
            self._con.execute(
                f"""
    CREATE INDEX IF NOT EXISTS remote_tasks_idx_{suffix}_file ON remote_tasks ({rows});
            """
            )
        for suffix, rows in [
            ("id", "id"),
            ("type", "type"),
            ("last_update", "last_update"),
        ]:
            self._con.execute(
                f"""
    CREATE INDEX IF NOT EXISTS remote_jobs_idx_{suffix}_file ON remote_jobs ({rows});
            """
            )

    def _add(
        self,
        type_: RemoteJobType,
        request: bytes,
        total: int,
        example_path_md5: t.Optional[str],
        example_path_extension: t.Optional[str],
    ) -> int:
        ret = self._con.execute(
            """
INSERT INTO remote_jobs (type, total, finished_tasks, original_request_json, example_path_md5, example_path_extension, created)
VALUES (?, ?, 0, ?, ?, ?, strftime('%s'))
RETURNING id;
            """,
            (type_.value, total, request, example_path_md5, example_path_extension),
        ).fetchone()
        assert ret is not None, "Inserting new job should always return ID"
        return t.cast(int, ret[0])

    def _submit_jobs_no_commit(
        self, type_: RemoteJobType, job_id: int, tasks: t.List[t.Tuple[str, str, bytes]]
    ) -> None:
        self._con.executemany(
            """
INSERT INTO remote_tasks (md5, job_id, type, payload_json, created)
VALUES (?, ?, ?, ?, strftime('%s'))
            """,
            [(md5, job_id, type_.value, payload_json) for md5, _extension, payload_json in tasks],
        )

    def submit_job(
        self, type_: RemoteJobType, request: bytes, tasks: t.List[t.Tuple[str, str, bytes]]
    ) -> int:
        if len(tasks) != len(set(j for j, _, _ in tasks)):
            raise ValidationError("Validation error: duplicit md5 for job")
        try:
            job_id = self._add(
                type_,
                request,
                len(tasks),
                None if not tasks else tasks[0][0],
                None if not tasks else tasks[0][1],
            )
            self._submit_jobs_no_commit(type_, job_id, tasks)
            self._con.commit()
            return job_id
        except:
            self._con.rollback()
            raise

    def unfinished_tasks(self) -> t.List[RemoteTask[bytes]]:
        ret = self._con.execute(
            """
SELECT md5, job_id, type, payload_json, created FROM remote_tasks WHERE finished_at is NULL
           """
        ).fetchall()
        return [
            RemoteTask(
                TaskId(md5, job_id),
                RemoteJobType(type_),
                payload_json,
                datetime.datetime.fromtimestamp(created),
                None,
            )
            for (md5, job_id, type_, payload_json, created) in ret
        ]

    def get_job(self, job_id: int) -> t.Optional[RemoteJob[bytes]]:
        ret = self._con.execute(
            """
SELECT
  id,
  type,
  total,
  finished_tasks,
  original_request_json,
  created,
  last_update,
  example_path_md5,
  example_path_extension
FROM remote_jobs
WHERE id = ?
            """,
            (job_id,),
        ).fetchone()
        if ret is None:
            return None
        (
            id_,
            type_,
            total,
            finished_tasks,
            original_request_json,
            created,
            last_update,
            example_path_md5,
            example_path_extension,
        ) = ret
        return RemoteJob(
            id_,
            RemoteJobType(type_),
            total,
            finished_tasks,
            original_request_json,
            datetime.datetime.fromtimestamp(created),
            None if last_update is None else datetime.datetime.fromtimestamp(last_update),
            example_path_md5,
            example_path_extension,
        )

    def get_jobs(
        self, *, skip_finished: bool = True, since: t.Optional[datetime.datetime] = None
    ) -> t.List[RemoteJob[bytes]]:
        where = []
        params: t.List[Parameter] = []
        if skip_finished:
            where.append("finished_tasks < total")
        if since is not None:
            where.append("created > ?")
            params.append(since.timestamp())
        if where:
            where_str = "WHERE " + " AND ".join(where)
        else:
            where_str = ""
        ret = self._con.execute(
            f"""
SELECT
  id,
  type,
  total,
  finished_tasks,
  original_request_json,
  created,
  last_update,
  example_path_md5,
  example_path_extension
FROM remote_jobs
{where_str}
            """,
            params if params else None,
        ).fetchall()
        output = []
        for (
            id_,
            type_,
            total,
            finished_tasks,
            original_request_json,
            created,
            last_update,
            example_path_md5,
            example_path_extension,
        ) in ret:
            output.append(
                RemoteJob(
                    id_,
                    RemoteJobType(type_),
                    total,
                    finished_tasks,
                    original_request_json,
                    datetime.datetime.fromtimestamp(created),
                    None if last_update is None else datetime.datetime.fromtimestamp(last_update),
                    example_path_md5,
                    example_path_extension,
                )
            )
        return output

    def get_task(self, task_id: TaskId) -> t.Optional[RemoteTask[bytes]]:
        ret = self._con.execute(
            """
SELECT
  md5,
  job_id,
  type,
  payload_json,
  created,
  finished_at
FROM remote_tasks
WHERE md5 = ? AND job_id = ?
            """,
            (task_id.md5, task_id.job_id),
        ).fetchone()
        if ret is None:
            return None
        (md5, job_id, type_, payload_json, created, finished_at) = ret
        return RemoteTask(
            TaskId(md5, job_id),
            RemoteJobType(type_),
            payload_json,
            datetime.datetime.fromtimestamp(created),
            None if finished_at is None else datetime.datetime.fromtimestamp(finished_at),
        )

    def finish_task(self, id_: TaskId) -> None:
        self._con.execute(
            """
UPDATE remote_tasks SET finished_at = strftime('%s') WHERE job_id = ? AND md5 = ?
            """,
            (id_.job_id, id_.md5),
        )
        self._con.commit()


class ValidationError(Exception):
    def __init__(self, msg: str):
        super().__init__(msg)
