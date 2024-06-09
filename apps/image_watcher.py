import argparse
import asyncio
import datetime
import itertools
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
import tqdm

from data_model.config import Config, DBFilesConfig
from data_model.features import PathWithMd5
from db import FeaturesTable, Connection, FilesTable, Queries
from annots.annotator import Annotator
from file_mgmt.jobs import Jobs, JobType, IMPORT_PRIORITY, DEFAULT_PRIORITY, REALTIME_PRIORITY
from utils import assert_never, DefaultDict, CacheTTL, Lazy
from utils.files import get_paths, expand_vars_in_path
from utils.progress_bar import ProgressBar

T = t.TypeVar("T")


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

        self._prio_progress: DefaultDict[JobType, ProgressBar] = DefaultDict(
            default_factory=lambda tp: ProgressBar(desc=f"Realtime ingest {tp.name}", permanent=True)
        )
        self._import_progress: DefaultDict[JobType, ProgressBar] = DefaultDict(
            default_factory=lambda tp: ProgressBar(desc=f"Import ingest {tp.name}", permanent=True)
        )
        self._default_progress: DefaultDict[JobType, ProgressBar] = DefaultDict(
            default_factory=lambda tp: ProgressBar(desc=f"Default ingest {tp.name}", permanent=True)
        )

    def get_progress_bar(self, type_: JobType, priority: int) -> ProgressBar:
        if priority >= DEFAULT_PRIORITY:
            return self._default_progress[type_]
        if priority == IMPORT_PRIORITY:
            return self._import_progress[type_]
        return self._prio_progress[type_]

    def update_progress_bars(self) -> None:
        for p in itertools.chain(
            self._prio_progress.values(), self._import_progress.values(), self._default_progress.values()
        ):
            p.update_total()

    def enqueue_path(self, path_with_md5: PathWithMd5, priority: int, types: t.Iterable[JobType]) -> None:
        for type_ in set(types):
            self.get_progress_bar(type_, priority).add_to_total(1)
            if type_ == JobType.CHEAP_FEATURES:
                self.cheap_features.put_nowait(
                    QueueItem(priority, self._index, (path_with_md5, JobType.CHEAP_FEATURES))
                )
                self._index += 1
            elif type_ == JobType.IMAGE_TO_TEXT:
                self.image_to_text.put_nowait(
                    QueueItem(priority, random.random(), (path_with_md5, JobType.IMAGE_TO_TEXT))
                )
            else:
                assert_never(type_)

    def enqueue_path_skipped_known(self, path: PathWithMd5, priority: int) -> None:
        if not self.known_paths.mutable_should_update(path):
            return
        self.enqueue_path(path, priority, list(JobType))

    def mark_failed(self, path: PathWithMd5) -> None:
        self.known_paths.delete(path)


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
                    data = json.loads(line)
                    path = data["import_path"]
                    paths = list(get_paths([], [path]))
                    if paths:
                        progress_bar.get().add_to_total(len(paths))
                        progress_bar.get().update_total()
                    enqueued = False
                    for path in paths:
                        try:
                            action = context.jobs.import_file(path)
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
                    if enqueued and path:
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
        jobs = Jobs(config.managed_folder, files, Queries(connection), annotator)
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
