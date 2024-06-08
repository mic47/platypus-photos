import argparse
import asyncio
import datetime
import enum
import json
import os
import random
import stat
import sys
import traceback
import typing as t

import aiofiles
import aiohttp
import asyncinotify

from data_model.config import Config, DBFilesConfig
from data_model.features import PathWithMd5
from db import FeaturesTable, Connection, FilesTable
from annots.annotator import Annotator
from file_mgmt.jobs import Jobs
from utils import assert_never, DefaultDict, CacheTTL
from utils.files import get_paths, expand_vars_in_path
from utils.progress_bar import ProgressBar

T = t.TypeVar("T")

IMPORT_PRIORITY = 46
DEFAULT_PRIORITY = 47
REALTIME_PRIORITY = 23


class JobType(enum.Enum):
    CHEAP_FEATURES = 1
    IMAGE_TO_TEXT = 2


class QueueItem(t.Generic[T]):
    def __init__(self, priority: int, rank: float, payload: T) -> None:
        self.priority = priority
        self.rank = rank
        self.payload = payload

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, QueueItem):
            raise NotImplementedError
        return (self.priority, self.rank) < (other.priority, other.rank)


class Queues:
    def __init__(self) -> None:
        self.cheap_features: asyncio.PriorityQueue[QueueItem[t.Tuple[PathWithMd5, JobType]]] = (
            asyncio.PriorityQueue()
        )
        self.image_to_text: asyncio.PriorityQueue[QueueItem[t.Tuple[PathWithMd5, JobType]]] = (
            asyncio.PriorityQueue()
        )
        self.known_paths: CacheTTL[PathWithMd5] = CacheTTL(
            datetime.timedelta(days=7), datetime.timedelta(days=14)
        )
        self._index = 0

    def enqueue_path(self, path_with_md5: PathWithMd5, priority: int) -> None:
        self.cheap_features.put_nowait(
            QueueItem(priority, self._index, (path_with_md5, JobType.CHEAP_FEATURES))
        )
        self._index += 1
        self.enqueue_path_for_image_to_text(path_with_md5, priority)

    def enqueue_path_for_image_to_text(self, path_with_md5: PathWithMd5, priority: int) -> None:
        self.image_to_text.put_nowait(
            QueueItem(priority, random.random(), (path_with_md5, JobType.IMAGE_TO_TEXT))
        )

    def enqueue_path_skipped_known(self, path: PathWithMd5, priority: int) -> None:
        if not self.known_paths.mutable_should_update(path):
            return
        self.enqueue_path(path, priority)

    def mark_failed(self, path: PathWithMd5) -> None:
        self.known_paths.delete(path)


class GlobalContext:
    def __init__(
        self,
        jobs: Jobs,
        queues: Queues,
    ) -> None:
        self.queues = queues
        self.jobs = jobs

        self.prio_progress: DefaultDict[JobType, ProgressBar] = DefaultDict(
            default_factory=lambda tp: ProgressBar(desc=f"Realtime ingest {tp.name}", permanent=True)
        )
        self.import_progress: DefaultDict[JobType, ProgressBar] = DefaultDict(
            default_factory=lambda tp: ProgressBar(desc=f"Import ingest {tp.name}", permanent=True)
        )
        self.default_progress: DefaultDict[JobType, ProgressBar] = DefaultDict(
            default_factory=lambda tp: ProgressBar(desc=f"Default ingest {tp.name}", permanent=True)
        )


async def worker(
    name: str,
    context: GlobalContext,
    queue: asyncio.PriorityQueue[QueueItem[t.Tuple[PathWithMd5, JobType]]],
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
            if item.priority >= DEFAULT_PRIORITY:
                context.default_progress[type_].update(1)
            elif item.priority == IMPORT_PRIORITY:
                context.import_progress[type_].update(1)
            else:
                context.prio_progress[type_].update(1)
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
            path_with_md5 = context.jobs.get_path_with_md5_to_enqueue(path, can_add=True)
            if path_with_md5 is None:
                return
            context.queues.enqueue_path_skipped_known(path_with_md5, DEFAULT_PRIORITY)
            total_for_reingest += 1
            if total_for_reingest % 1000 == 0:
                await asyncio.sleep(0)
            found_something = True
        if found_something:
            for p in context.default_progress.values():
                p.update_total(total_for_reingest)

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
    total = 0
    progress_bar = context.import_progress[JobType.CHEAP_FEATURES]
    while True:
        async with aiofiles.open(config.import_fifo, "r") as import_fifo:
            async for line in import_fifo:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    path = data["import_path"]
                    paths = list(get_paths([], [path]))
                    total += len(paths)
                    progress_bar.update_total(total)
                    for path in paths:
                        try:
                            action = context.jobs.import_file(path)
                            if action is not None:
                                context.queues.enqueue_path_for_image_to_text(
                                    action.path_with_md5, action.priority
                                )
                        # pylint: disable = broad-exception-caught
                        except Exception as e:
                            traceback.print_exc()
                            print("Error while importing path", path, e, file=sys.stderr)
                            continue
                        finally:
                            progress_bar.update(1)
                            # So that we gave up place for other workers too
                            await asyncio.sleep(0)
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


async def main() -> None:
    files_config = DBFilesConfig()
    parser = argparse.ArgumentParser(prog="Photo annotator")
    parser.add_argument("--config", default="config.yaml", type=str)
    parser.add_argument("--db", default=files_config.photos_db, type=str)
    parser.add_argument("--image-to-text-workers", default=3, type=int)
    parser.add_argument("--annotate-url", default=None, type=str)
    args = parser.parse_args()
    config = Config.load(args.config)
    connection = Connection(args.db)
    features = FeaturesTable(connection)
    files = FilesTable(connection)

    async def check_db_connection() -> None:
        while True:
            connection.check_unused()
            await asyncio.sleep(10)

    tasks = []
    tasks.append(asyncio.create_task(check_db_connection()))

    async with aiohttp.ClientSession() as session:
        annotator = Annotator(config.directory_matching, files_config, features, session, args.annotate_url)
        jobs = Jobs(config.managed_folder, files, annotator)
        queues = Queues()
        context = GlobalContext(jobs, queues)

        # Fix inconsistencies in the DB before we start.
        context.jobs.fix_in_progress_moved_files_at_startup()
        context.jobs.fix_imported_files_at_startup()

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
