import argparse
import asyncio
import enum
import os
import random
import re
import sys
import traceback
import typing as t

import aiohttp
import asyncinotify

from data_model.config import Config, DBFilesConfig
from data_model.features import PathWithMd5
from db import FeaturesTable, Connection, FilesTable
from annots.annotator import Annotator
from file_mgmt.jobs import Jobs, JobAction, EnqueuePathAction
from utils import assert_never
from utils.files import get_paths
from utils.progress_bar import ProgressBar

T = t.TypeVar("T")

IMPORT_PRIORITY = 46
DEFAULT_PRIORITY = 47
REALTIME_PRIORITY = 23


class JobType(enum.Enum):
    CHEAP_FEATURES = 1
    IMAGE_TO_TEXT = 2
    IMPORT = 3


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
        self._index = 0

    def enqueue_path(self, context: "GlobalContext", path: str, priority: int, can_add: bool) -> None:
        # TODO: this caching is wrong?
        if path in context.known_paths:
            return
        context.known_paths.add(path)
        path_with_md5 = context.jobs.get_path_with_md5_to_enqueue(path, can_add)
        if path_with_md5 is None:
            return
        self.cheap_features.put_nowait(
            QueueItem(priority, self._index, (path_with_md5, JobType.CHEAP_FEATURES))
        )
        self.image_to_text.put_nowait(
            QueueItem(priority, random.random(), (path_with_md5, JobType.IMAGE_TO_TEXT))
        )
        self._index += 1


K = t.TypeVar("K")
V = t.TypeVar("V")


class DefaultDict(dict[K, V]):
    def __init__(self, default_factory: t.Callable[[K], V]):
        super().__init__()
        self.default_factory = default_factory

    def __missing__(self, key: K) -> V:
        ret = self[key] = self.default_factory(key)
        return ret


class GlobalContext:
    def __init__(
        self,
        annotator: Annotator,
        jobs: Jobs,
        queues: Queues,
    ) -> None:
        self.queues = queues
        self.jobs = jobs
        self.annotator = annotator

        self.prio_progress: DefaultDict[JobType, ProgressBar] = DefaultDict(
            default_factory=lambda tp: ProgressBar(desc=f"Realtime ingest {tp.name}", permanent=True)
        )
        self.import_progress: DefaultDict[JobType, ProgressBar] = DefaultDict(
            default_factory=lambda tp: ProgressBar(desc=f"Import ingest {tp.name}", permanent=True)
        )
        self.default_progress: DefaultDict[JobType, ProgressBar] = DefaultDict(
            default_factory=lambda tp: ProgressBar(desc=f"Default ingest {tp.name}", permanent=True)
        )
        self.known_paths: t.Set[str] = set()


async def worker(
    name: str,
    context: GlobalContext,
    queue: asyncio.PriorityQueue[QueueItem[t.Tuple[PathWithMd5, JobType]]],
) -> None:
    while True:
        # Get a "work item" out of the queue.
        item = await queue.get()
        path, type_ = item.payload
        actions: t.List[JobAction] = []
        try:
            if type_ == JobType.CHEAP_FEATURES:
                context.annotator.cheap_features(path)
            elif type_ == JobType.IMAGE_TO_TEXT:
                await context.annotator.image_to_text(path)
            elif type_ == JobType.IMPORT:
                enqueue = context.jobs.import_file(path)
                actions.append(enqueue)
            else:
                assert_never(type_)
            for action in actions:
                if isinstance(action, EnqueuePathAction):
                    context.queues.enqueue_path(context, action.path, action.priority, action.can_add)
                else:
                    assert_never(action)
        # pylint: disable = broad-exception-caught
        except Exception as e:
            traceback.print_exc()
            print("Error while processing path in ", name, path, e, file=sys.stderr)
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
                re.sub("^~/", os.environ["HOME"] + "/", dir_),
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
            context.queues.enqueue_path(context, path, REALTIME_PRIORITY, can_add=True)


async def reingest_directories_worker(context: GlobalContext, config: Config) -> None:
    total_for_reingest = 0
    while True:
        await context.queues.cheap_features.join()
        found_something = False
        for path in get_paths(config.input_patterns, config.input_directories):
            context.queues.enqueue_path(context, path, DEFAULT_PRIORITY, can_add=True)
            total_for_reingest += 1
            if total_for_reingest % 1000 == 0:
                await asyncio.sleep(0)
            found_something = True
        if found_something:
            for p in context.default_progress.values():
                p.update_total(total_for_reingest)

        # Check for new features once every 8 hours
        await asyncio.sleep(3600 * 8)


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
        jobs = Jobs(files, annotator)
        queues = Queues()
        context = GlobalContext(annotator, jobs, queues)

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
