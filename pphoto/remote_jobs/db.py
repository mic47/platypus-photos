from __future__ import annotations

import datetime
import typing as t

from pphoto.db.connection import JobsConnection
from pphoto.remote_jobs.types import JobType, TaskId, Task, Job


class JobsTable:
    def __init__(self, connection: JobsConnection) -> None:
        self._con = connection
        self._init_db()

    def _init_db(
        self,
    ) -> None:
        self._con.execute(
            """
CREATE TABLE IF NOT EXISTS tasks (
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
CREATE TABLE IF NOT EXISTS jobs (
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
  tasks_on_finish
AFTER UPDATE OF finished_at ON tasks
FOR EACH ROW WHEN OLD.finished_at IS NULL and NEW.finished_at IS NOT NULL
BEGIN
  UPDATE jobs SET finished_tasks = finished_tasks + 1, last_update = NEW.finished_at WHERE id = NEW.job_id;
END;
    """
        )
        for suffix, rows in [
            ("md5_job_id", "md5, job_id"),
            ("job_id", "job_id"),
        ]:
            self._con.execute(
                f"""
    CREATE INDEX IF NOT EXISTS tasks_idx_{suffix}_file ON tasks ({rows});
            """
            )
        for suffix, rows in [
            ("id", "id"),
            ("type", "type"),
        ]:
            self._con.execute(
                f"""
    CREATE INDEX IF NOT EXISTS jobs_idx_{suffix}_file ON jobs ({rows});
            """
            )

    def _add(self, type_: JobType, request: bytes, total: int) -> int:
        ret = self._con.execute(
            """
INSERT INTO jobs (type, total, finished_tasks, original_request_json, created)
VALUES (?, ?, 0, ?, strftime('%s'))
RETURNING id;
            """,
            (type_.value, total, request),
        ).fetchone()
        assert ret is not None, "Inserting new job should always return ID"
        return t.cast(int, ret[0])

    def _submit_jobs_no_commit(self, type_: JobType, job_id: int, tasks: t.List[t.Tuple[str, bytes]]) -> None:
        self._con.executemany(
            """
INSERT INTO tasks (md5, job_id, type, payload_json, created)
VALUES (?, ?, ?, ?, strftime('%s'))
            """,
            [(md5, job_id, type_.value, payload_json) for md5, payload_json in tasks],
        )

    def submit_job(self, type_: JobType, request: bytes, tasks: t.List[t.Tuple[str, bytes]]) -> int:
        if len(tasks) != len(set(j for j, _ in tasks)):
            raise ValidationError("Validation error: duplicit md5 for job")
        try:
            job_id = self._add(type_, request, len(tasks))
            self._submit_jobs_no_commit(type_, job_id, tasks)
            self._con.commit()
            return job_id
        except:
            self._con.rollback()
            raise

    def unfinished_tasks(self) -> t.List[Task[bytes]]:
        ret = self._con.execute(
            """
SELECT md5, job_id, type, payload_json, created FROM tasks WHERE finished_at is NULL
           """
        ).fetchall()
        return [
            Task(
                TaskId(md5, job_id),
                JobType(type_),
                payload_json,
                datetime.datetime.fromtimestamp(created),
                None,
            )
            for (md5, job_id, type_, payload_json, created) in ret
        ]

    def get_job(self, job_id: int) -> t.Optional[Job[bytes]]:
        ret = self._con.execute(
            """
SELECT
  id,
  type,
  total,
  finished_tasks,
  original_request_json,
  created,
  last_update
FROM jobs
WHERE id = ?
            """,
            (job_id,),
        ).fetchone()
        if ret is None:
            return None
        (id_, type_, total, finished_tasks, original_request_json, created, last_update) = ret
        return Job(
            id_,
            JobType(type_),
            total,
            finished_tasks,
            original_request_json,
            datetime.datetime.fromtimestamp(created),
            None if last_update is None else datetime.datetime.fromtimestamp(last_update),
        )

    def get_task(self, task_id: TaskId) -> t.Optional[Task[bytes]]:
        ret = self._con.execute(
            """
SELECT
  md5,
  job_id,
  type,
  payload_json,
  created,
  finished_at
FROM tasks
WHERE md5 = ? AND job_id = ?
            """,
            (task_id.md5, task_id.job_id),
        ).fetchone()
        if ret is None:
            return None
        (md5, job_id, type_, payload_json, created, finished_at) = ret
        return Task(
            TaskId(md5, job_id),
            JobType(type_),
            payload_json,
            datetime.datetime.fromtimestamp(created),
            None if finished_at is None else datetime.datetime.fromtimestamp(finished_at),
        )

    def finish_task(self, id_: TaskId) -> None:
        self._con.execute(
            """
UPDATE tasks SET finished_at = strftime('%s') WHERE job_id = ? AND md5 = ?
            """,
            (id_.job_id, id_.md5),
        )
        self._con.commit()


class ValidationError(Exception):
    def __init__(self, msg: str):
        super().__init__(msg)
