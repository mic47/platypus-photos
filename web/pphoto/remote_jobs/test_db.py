import datetime
import typing as t
import unittest

from pphoto.db.connection import JobsConnection, MaybeParameters
from pphoto.remote_jobs.db import RemoteJobsTable, ValidationError
from pphoto.remote_jobs.types import RemoteJobType, RemoteTask, RemoteJob, TaskId


def connection() -> JobsConnection:
    return JobsConnection(":memory:")


class TestJobsTable(unittest.TestCase):
    def test_create_table(self) -> None:
        conn = connection()
        RemoteJobsTable(conn)
        RemoteJobsTable(conn)

    def test_submit_job(self) -> None:
        table = RemoteJobsTable(connection())
        job_a = table.submit_job(
            RemoteJobType.MASS_MANUAL_ANNOTATION, b"WAT", [("lol", "jpg", b"foo"), ("goo", "jpg", b"bar")]
        )

        with self.assertRaises(ValidationError, msg="Should fail to validate with duplicate md5s"):
            table.submit_job(
                RemoteJobType.MASS_MANUAL_ANNOTATION, b"WAT", [("lol", "jpg", b"foo"), ("lol", "jpg", b"bar")]
            )

        job_b = table.submit_job(
            RemoteJobType.MASS_MANUAL_ANNOTATION, b"WAT", [("lol", "jpg", b"foo"), ("goo", "jpg", b"bar")]
        )
        self.assertNotEqual(job_a, job_b, "Same ID for different jobs")

    def test_finish_task(self) -> None:
        table = RemoteJobsTable(connection())
        job_id = table.submit_job(
            RemoteJobType.MASS_MANUAL_ANNOTATION, b"WAT", [("lol", "jpg", b"foo"), ("goo", "jpg", b"bar")]
        )
        unfinished = table.unfinished_tasks()
        self.assertListEqual(
            [t.test_sanitize() for t in unfinished],
            [
                RemoteTask(
                    TaskId("lol", job_id),
                    RemoteJobType.MASS_MANUAL_ANNOTATION,
                    b"foo",
                    datetime.datetime(1, 1, 1),
                    None,
                ),
                RemoteTask(
                    TaskId("goo", job_id),
                    RemoteJobType.MASS_MANUAL_ANNOTATION,
                    b"bar",
                    datetime.datetime(1, 1, 1),
                    None,
                ),
            ],
            "Both tasks should be unfinished",
        )
        job = table.get_job(job_id)
        self.assertEqual(
            job.test_sanitize() if job is not None else None,
            RemoteJob(
                job_id,
                RemoteJobType.MASS_MANUAL_ANNOTATION,
                2,
                0,
                b"WAT",
                datetime.datetime(1, 1, 1),
                None,
                "lol",
                "jpg",
            ),
            "Job should have 0 finished tasks",
        )
        task = table.get_task(TaskId("goo", job_id))
        self.assertEqual(
            task.test_sanitize() if task is not None else None,
            RemoteTask(
                TaskId("goo", job_id),
                RemoteJobType.MASS_MANUAL_ANNOTATION,
                b"bar",
                datetime.datetime(1, 1, 1),
                None,
            ),
            "This task should be unfinished",
        )

        # Test you can finish something multiple times
        for _ in range(3):
            table.finish_task(TaskId("goo", job_id))
            unfinished = table.unfinished_tasks()
            self.assertListEqual(
                [t.test_sanitize() for t in unfinished],
                [
                    RemoteTask(
                        TaskId("lol", job_id),
                        RemoteJobType.MASS_MANUAL_ANNOTATION,
                        b"foo",
                        datetime.datetime(1, 1, 1),
                        None,
                    )
                ],
                "Lol task should be unfinished",
            )
            job = table.get_job(job_id)
            self.assertEqual(
                job.test_sanitize() if job is not None else None,
                RemoteJob(
                    job_id,
                    RemoteJobType.MASS_MANUAL_ANNOTATION,
                    2,
                    1,
                    b"WAT",
                    datetime.datetime(1, 1, 1),
                    datetime.datetime(1, 1, 1),
                    "lol",
                    "jpg",
                ),
                "Job should have finished 1 task",
            )
            task = table.get_task(TaskId("goo", job_id))
            self.assertEqual(
                task.test_sanitize() if task is not None else None,
                RemoteTask(
                    TaskId("goo", job_id),
                    RemoteJobType.MASS_MANUAL_ANNOTATION,
                    b"bar",
                    datetime.datetime(1, 1, 1),
                    datetime.datetime(1, 1, 1),
                ),
                "Goo should be finished",
            )
        # Other task is untouched
        task = table.get_task(TaskId("lol", job_id))
        self.assertEqual(
            task.test_sanitize() if task is not None else None,
            RemoteTask(
                TaskId("lol", job_id),
                RemoteJobType.MASS_MANUAL_ANNOTATION,
                b"foo",
                datetime.datetime(1, 1, 1),
                None,
            ),
            "Foo should still be untouched",
        )

        table.finish_task(TaskId("lol", job_id))
        unfinished = table.unfinished_tasks()
        self.assertListEqual([t.test_sanitize() for t in unfinished], [], "All tasks should be finished")
        job = table.get_job(job_id)
        self.assertEqual(
            job.test_sanitize() if job is not None else None,
            RemoteJob(
                job_id,
                RemoteJobType.MASS_MANUAL_ANNOTATION,
                2,
                2,
                b"WAT",
                datetime.datetime(1, 1, 1),
                datetime.datetime(1, 1, 1),
                "lol",
                "jpg",
            ),
            "Job should have finished 2 task",
        )
        task = table.get_task(TaskId("goo", job_id))
        self.assertEqual(
            task.test_sanitize() if task is not None else None,
            RemoteTask(
                TaskId("goo", job_id),
                RemoteJobType.MASS_MANUAL_ANNOTATION,
                b"bar",
                datetime.datetime(1, 1, 1),
                datetime.datetime(1, 1, 1),
            ),
            "Goo should still be finished",
        )

    def test_fetching_non_existent_data(self) -> None:
        table = RemoteJobsTable(connection())
        job_id = table.submit_job(
            RemoteJobType.MASS_MANUAL_ANNOTATION, b"WAT", [("lol", "jpg", b"foo"), ("goo", "jpg", b"bar")]
        )
        self.assertIsNone(table.get_job(job_id + 1))
        self.assertIsNone(table.get_task(TaskId("lol", job_id + 1)))
        self.assertIsNone(table.get_task(TaskId("lol+", job_id + 1)))
        self.assertIsNone(table.get_task(TaskId("lol+", job_id)))

    def test_error_handling(self) -> None:
        was_rollback = False
        start_failing = False

        class MockConnection(JobsConnection):
            def execute(self, sql: str, parameters: MaybeParameters = None) -> t.Any:
                nonlocal start_failing
                if start_failing:
                    raise NotImplementedError
                return super().execute(sql, parameters)

            def rollback(self) -> None:
                nonlocal was_rollback
                was_rollback = True

        table = RemoteJobsTable(MockConnection(":memory:"))
        start_failing = True
        self.assertEqual(was_rollback, False, "Rollback should not be callsed")
        with self.assertRaises(NotImplementedError, msg="Should raise exception on error"):
            table.submit_job(
                RemoteJobType.MASS_MANUAL_ANNOTATION, b"WAT", [("lol", "jpg", b"foo"), ("goo", "jpg", b"bar")]
            )
        self.assertEqual(was_rollback, True, "Rollback should be called on exception during execution")
