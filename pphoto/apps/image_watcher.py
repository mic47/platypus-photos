import argparse
import asyncio
import os
import stat
import sys
import traceback
import typing as t

import aiofiles
import aiohttp
import asyncinotify
import tqdm

from pphoto.data_model.base import PathWithMd5
from pphoto.data_model.config import Config, DBFilesConfig
from pphoto.db.features_table import FeaturesTable
from pphoto.db.connection import PhotosConnection, GalleryConnection, JobsConnection
from pphoto.db.files_table import FilesTable
from pphoto.db.queries import PhotosQueries
from pphoto.annots.annotator import Annotator
from pphoto.annots.date import PathDateExtractor
from pphoto.remote_jobs.types import TaskId, RemoteTask, ManualAnnotationTask
from pphoto.remote_jobs.db import RemoteJobsTable
from pphoto.file_mgmt.jobs import Jobs, JobType, IMPORT_PRIORITY, DEFAULT_PRIORITY, REALTIME_PRIORITY
from pphoto.file_mgmt.queues import Queues, Queue
from pphoto.file_mgmt.remote_control import ImportCommand, parse_rc_job, RefreshJobs
from pphoto.gallery.reindexer import Reindexer
from pphoto.utils import assert_never, Lazy
from pphoto.utils.files import get_paths, expand_vars_in_path
from pphoto.utils.progress_bar import ProgressBar


class GlobalContext:
    def __init__(
        self,
        jobs: Jobs,
        files: FilesTable,
        remote_jobs: RemoteJobsTable,
        queues: Queues,
    ) -> None:
        self.queues = queues
        self.jobs = jobs
        self.remote_jobs = remote_jobs
        self.files = files


async def worker(
    name: str,
    context: GlobalContext,
    queue: Queue,
) -> None:
    while True:
        # Get a "work item" out of the queue.
        item = await queue.get()
        path, type_ = item.payload
        try:
            if type_ == JobType.CHEAP_FEATURES:
                assert isinstance(path, PathWithMd5)
                context.jobs.cheap_features(path, recompute_location=False)
            elif type_ == JobType.IMAGE_TO_TEXT:
                assert isinstance(path, PathWithMd5)
                await context.jobs.image_to_text(path)
            elif type_ == JobType.ADD_MANUAL_ANNOTATION:
                if isinstance(path, RemoteTask) and isinstance(path.payload, ManualAnnotationTask):
                    context.jobs.add_manual_annotation(path)
                else:
                    assert False, "Wrong type for ADD_MANUAL_ANNOTATION"
            else:
                assert_never(type_)
        # pylint: disable-next = broad-exception-caught
        except Exception as e:
            traceback.print_exc()
            print("Error while processing path in ", name, path, e, file=sys.stderr)
            if isinstance(path, PathWithMd5):
                context.queues.mark_failed(path)
        finally:
            # Notify the queue that the "work item" has been processed.
            context.queues.get_progress_bar(type_, item.priority).update(1)
            queue.task_done()
            # So that we gave up place for other workers too
            await asyncio.sleep(0)


async def manual_annotation_worker(
    name: str, input_queue: asyncio.Queue[RefreshJobs], context: GlobalContext
) -> None:
    visited: t.Set[TaskId] = set()
    while True:
        refresh_job = await input_queue.get()
        try:
            unfinished_tasks = context.remote_jobs.unfinished_tasks()
            for task in unfinished_tasks:
                if task.id_ in visited:
                    continue
                try:
                    parsed_task = task.map(ManualAnnotationTask.from_json)
                # pylint: disable-next = bare-except
                except:
                    traceback.print_exc()
                    print("Error while parsing manual task", name, task)
                    continue

                context.queues.enqueue_path([(parsed_task, JobType.ADD_MANUAL_ANNOTATION)], REALTIME_PRIORITY)
                visited.add(task.id_)
        # pylint: disable-next = bare-except
        except:
            traceback.print_exc()
            print("Error in manual annotation worker", name, refresh_job)
            continue


async def inotify_worker(name: str, dirs: t.List[str], context: GlobalContext) -> None:
    with asyncinotify.Inotify() as inotify:
        for dir_ in dirs:
            inotify.add_watch(
                expand_vars_in_path(dir_),
                asyncinotify.Mask.CREATE | asyncinotify.Mask.MOVE,
            )
        async for event in inotify:
            if event.path is None:
                continue
            try:
                path = event.path.absolute().resolve().as_posix()
            # pylint: disable-next = bare-except
            except:
                traceback.print_exc()
                print("Error in inotify worker", name)
                continue
            # TODO: this shoudl be in try catch
            path_with_md5 = context.jobs.get_path_with_md5_to_enqueue(path, can_add=True)
            if path_with_md5 is None:
                return
            context.queues.enqueue_path_skipped_known(path_with_md5, REALTIME_PRIORITY)


async def reingest_directories_worker(context: GlobalContext, config: Config) -> None:
    total_for_reingest = 0
    while True:
        await context.queues.cheap_features.join()
        found_something = False
        for path in get_paths(config.input_patterns, config.input_directories):
            if context.files.by_path(path) is not None:
                continue
            path_with_md5 = context.jobs.get_path_with_md5_to_enqueue(path, can_add=True)
            if path_with_md5 is None:
                return
            context.queues.enqueue_path_skipped_known(path_with_md5, DEFAULT_PRIORITY)
            total_for_reingest += 1
            if total_for_reingest % 1000 == 0:
                await asyncio.sleep(0)
            found_something = True
        if found_something:
            context.queues.update_progress_bars()
        # Check for new features once every 8 hours
        await asyncio.sleep(3600 * 8)


async def watch_import_path(
    config: Config, import_queue: asyncio.Queue[ImportCommand], jobs_queue: asyncio.Queue[RefreshJobs]
) -> None:
    try:
        if os.path.exists(config.import_fifo):
            if not stat.S_ISFIFO(os.stat(config.import_fifo).st_mode):
                print(f"FATAL: {config.import_fifo} is not FIFo!", file=sys.stderr)
                sys.exit(1)
        else:
            os.mkfifo(config.import_fifo)
    # pylint: disable-next = broad-exception-caught
    except Exception as e:
        traceback.print_exc()
        print("Unable to create fifo file", config.import_fifo, e, file=sys.stderr)
        sys.exit(1)
    while True:
        async with aiofiles.open(config.import_fifo, "r") as import_fifo:
            async for line in import_fifo:
                line = line.strip()
                if not line:
                    continue
                try:
                    job = parse_rc_job(line)
                    if isinstance(job, ImportCommand):
                        import_queue.put_nowait(job)
                    elif isinstance(job, RefreshJobs):
                        jobs_queue.put_nowait(job)
                    else:
                        assert_never(job)
                # pylint: disable-next = broad-exception-caught
                except Exception as e:
                    traceback.print_exc()
                    print("Error while pricessing import request", line, e, file=sys.stderr)
                    continue
                finally:
                    # So that we gave up place for other workers too
                    await asyncio.sleep(0)
            # So that we gave up place for other workers too
            await asyncio.sleep(0)


async def managed_worker_and_import_worker(
    context: GlobalContext, queue: asyncio.Queue[ImportCommand]
) -> None:
    # TODO: check for new files in managed folders, and add them. Run it from time to time
    progress_bar = Lazy(lambda: context.queues.get_progress_bar(JobType.CHEAP_FEATURES, IMPORT_PRIORITY))
    while True:
        import_command = await queue.get()
        try:
            paths = list(get_paths([], [import_command.import_path]))
            if paths:
                progress_bar.get().add_to_total(len(paths))
                progress_bar.get().update_total()
            enqueued = False
            for path in paths:
                try:
                    action = context.jobs.import_file(path, import_command.mode)
                    if action is not None:
                        enqueued = True
                        context.queues.enqueue_path(
                            [(action.path_with_md5, t) for t in action.job_types], action.priority
                        )
                # pylint: disable-next = broad-exception-caught
                except Exception as e:
                    traceback.print_exc()
                    print("Error while importing path", path, e, file=sys.stderr)
                    continue
                finally:
                    progress_bar.get().update(1)
                    # So that we gave up place for other workers too
                    await asyncio.sleep(0)
            if enqueued and paths:
                context.queues.update_progress_bars()
        # pylint: disable-next = broad-exception-caught
        except Exception as e:
            traceback.print_exc()
            print("Error while pricessing import request", import_command, e, file=sys.stderr)
            continue
        finally:
            # So that we gave up place for other workers too
            await asyncio.sleep(0)


async def reindex_gallery(reindexer: Reindexer) -> None:
    # Allow other tasks to start
    await asyncio.sleep(0)
    sleep_time = 1
    max_sleep_time = 64
    progress_bar = ProgressBar("Reindexing gallery", permanent=True)
    while True:
        try:
            done = reindexer.load(progress=progress_bar)
            if done <= 100:
                sleep_time = min(sleep_time * 2, max_sleep_time)
            else:
                sleep_time = 1
        # pylint: disable-next = broad-exception-caught
        except Exception as e:
            traceback.print_exc()
            print("Error while trying to refresh data in db:", e)
            sleep_time = 1
            print("Reconnecting")
            reindexer.reconnect()
        await asyncio.sleep(sleep_time)


async def main() -> None:
    files_config = DBFilesConfig()
    parser = argparse.ArgumentParser(prog="Photo annotator")
    parser.add_argument("--config", default="config.yaml", type=str)
    parser.add_argument("--db", default=files_config.photos_db, type=str)
    parser.add_argument("--image-to-text-workers", default=3, type=int)
    parser.add_argument("--annotate-url", default=None, type=str)
    args = parser.parse_args()
    config = Config.load(args.config)
    photos_connection = PhotosConnection(args.db)
    gallery_connection = GalleryConnection(files_config.gallery_db)
    jobs_connection = JobsConnection(files_config.jobs_db)
    reindexer = Reindexer(PathDateExtractor(config.directory_matching), photos_connection, gallery_connection)
    features = FeaturesTable(photos_connection)
    files = FilesTable(photos_connection)

    async def check_db_connection() -> None:
        while True:
            photos_connection.check_unused()
            reindexer.check_unused()
            Lazy.check_ttl()
            await asyncio.sleep(10)

    tasks = []
    tasks.append(asyncio.create_task(check_db_connection()))
    tasks.append(asyncio.create_task(reindex_gallery(reindexer)))

    async with aiohttp.ClientSession() as session:
        annotator = Annotator(config.directory_matching, files_config, features, session, args.annotate_url)
        remote_jobs_table = RemoteJobsTable(jobs_connection)
        jobs = Jobs(
            config.managed_folder, files, remote_jobs_table, PhotosQueries(photos_connection), annotator
        )
        queues = Queues()
        context = GlobalContext(jobs, files, remote_jobs_table, queues)

        # Fix inconsistencies in the DB before we start.
        context.jobs.fix_in_progress_moved_files_at_startup()
        context.jobs.fix_imported_files_at_startup()

        unannotated = context.jobs.find_unannotated_files()
        for action in tqdm.tqdm(unannotated, desc="Enqueuing unannotated files"):
            context.queues.enqueue_path(
                [(action.path_with_md5, t) for t in action.job_types], action.priority
            )
        del unannotated
        context.queues.update_progress_bars()

        import_queue: asyncio.Queue[ImportCommand] = asyncio.Queue()
        refresh_queue: asyncio.Queue[RefreshJobs] = asyncio.Queue()
        # Starting async tasks
        tasks.append(asyncio.create_task(watch_import_path(config, import_queue, refresh_queue)))
        tasks.append(
            asyncio.create_task(manual_annotation_worker("manual-annotation", refresh_queue, context))
        )
        tasks.append(asyncio.create_task(managed_worker_and_import_worker(context, import_queue)))
        tasks.append(asyncio.create_task(reingest_directories_worker(context, config)))
        for i in range(1):
            task = asyncio.create_task(worker(f"worker-cheap-{i}", context, queues.cheap_features))
        for i in range(args.image_to_text_workers):
            task = asyncio.create_task(worker(f"worker-image-to-text-{i}", context, queues.image_to_text))
            tasks.append(task)
        tasks.append(asyncio.create_task(inotify_worker("watch-files", config.watched_directories, context)))
        try:
            while True:
                await asyncio.sleep(3600 * 24 * 365)
                print("Wow, it's on for 365 days!🚀", file=sys.stderr)
        finally:
            for task in tasks:
                task.cancel()
            # Wait until all worker tasks are cancelled.
            await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(main())
