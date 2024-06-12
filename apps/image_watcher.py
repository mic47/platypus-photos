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

from data_model.config import Config, DBFilesConfig
from db import FeaturesTable, Connection, FilesTable, Queries
from annots.annotator import Annotator
from annots.date import PathDateExtractor
from file_mgmt.jobs import Jobs, JobType, IMPORT_PRIORITY, DEFAULT_PRIORITY, REALTIME_PRIORITY
from file_mgmt.queues import Queues, Queue
from file_mgmt.remote_control import ImportCommand
from gallery.db import Reindexer
from utils import assert_never, Lazy
from utils.files import get_paths, expand_vars_in_path


class GlobalContext:
    def __init__(
        self,
        jobs: Jobs,
        files: FilesTable,
        queues: Queues,
    ) -> None:
        self.queues = queues
        self.jobs = jobs
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
                context.jobs.cheap_features(path)
            elif type_ == JobType.IMAGE_TO_TEXT:
                await context.jobs.image_to_text(path)
            else:
                assert_never(type_)
        # pylint: disable = broad-exception-caught
        except Exception as e:
            traceback.print_exc()
            print("Error while processing path in ", name, path, e, file=sys.stderr)
            context.queues.mark_failed(path)
        finally:
            # Notify the queue that the "work item" has been processed.
            context.queues.get_progress_bar(type_, item.priority).update(1)
            queue.task_done()
            # So that we gave up place for other workers too
            await asyncio.sleep(0)


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
            # pylint: disable = bare-except
            except:
                traceback.print_exc()
                print("Error in inotify worker", name)
                continue
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


async def managed_worker_and_import_worker(context: GlobalContext, config: Config) -> None:
    try:
        if os.path.exists(config.import_fifo):
            if not stat.S_ISFIFO(os.stat(config.import_fifo).st_mode):
                print(f"FATAL: {config.import_fifo} is not FIFo!", file=sys.stderr)
                sys.exit(1)
        else:
            os.mkfifo(config.import_fifo)
    # pylint: disable = broad-exception-caught
    except Exception as e:
        traceback.print_exc()
        print("Unable to create fifo file", config.import_fifo, e, file=sys.stderr)
        sys.exit(1)
    # TODO: check for new files in managed folders, and add them. Run it from time to time
    progress_bar = Lazy(lambda: context.queues.get_progress_bar(JobType.CHEAP_FEATURES, IMPORT_PRIORITY))
    while True:
        async with aiofiles.open(config.import_fifo, "r") as import_fifo:
            async for line in import_fifo:
                line = line.strip()
                if not line:
                    continue
                try:
                    import_command = ImportCommand.from_json(line)
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
                                    action.path_with_md5, action.priority, action.job_types
                                )
                        # pylint: disable = broad-exception-caught
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
                # pylint: disable = broad-exception-caught
                except Exception as e:
                    traceback.print_exc()
                    print("Error while pricessing import request", line, e, file=sys.stderr)
                    continue
                finally:
                    # So that we gave up place for other workers too
                    await asyncio.sleep(0)
            # So that we gave up place for other workers too
            await asyncio.sleep(0)


async def reindex_gallery(reindexer: Reindexer) -> None:
    # Allow other tasks to start
    await asyncio.sleep(0)
    sleep_time = 1
    max_sleep_time = 64
    while True:
        try:
            done = reindexer.load(show_progress=False)
            if done <= 100:
                sleep_time = min(sleep_time * 2, max_sleep_time)
                if done > 0:
                    print(f"Reindexed {done} images.", file=sys.stderr)
            else:
                print(f"Reindexed {done} images.", file=sys.stderr)
                sleep_time = 1
        # pylint: disable = broad-exception-caught
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
    photos_connection = Connection(args.db)
    gallery_connection = Connection(files_config.gallery_db)
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
        jobs = Jobs(config.managed_folder, files, Queries(photos_connection), annotator)
        queues = Queues()
        context = GlobalContext(jobs, files, queues)

        # Fix inconsistencies in the DB before we start.
        context.jobs.fix_in_progress_moved_files_at_startup()
        context.jobs.fix_imported_files_at_startup()

        unannotated = context.jobs.find_unannotated_files()
        for action in tqdm.tqdm(unannotated, desc="Enqueuing unannotated files"):
            context.queues.enqueue_path(action.path_with_md5, action.priority, action.job_types)
        del unannotated
        context.queues.update_progress_bars()

        # Starting async tasks
        tasks.append(asyncio.create_task(managed_worker_and_import_worker(context, config)))
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
