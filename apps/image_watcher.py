import argparse
import asyncio
import datetime
import enum
import os
import random
import re
import sys
import traceback
import typing as t

import aiohttp
import asyncinotify

from data_model.config import Config
from data_model.features import WithMD5, PathWithMd5
from db.cache import SQLiteCache, FilesCache
from db.sql import FeaturesTable, Connection, FilesTable
from annots.date import PathDateExtractor
from annots.exif import Exif, ImageExif
from annots.geo import Geolocator, GeoAddress
from annots.md5 import compute_md5
from annots.text import Models, ImageClassification
from utils.files import get_paths, supported_media
from utils.progress_bar import ProgressBar

T = t.TypeVar("T")

DEFAULT_PRIORITY = 47


class JobType(enum.Enum):
    CHEAP_FEATURES = 1
    IMAGE_TO_TEXT = 2


class GlobalContext:
    def __init__(
        self,
        config: Config,
        features: FeaturesTable,
        files: FilesTable,
        session: aiohttp.ClientSession,
        annotate_url: t.Optional[str],
    ) -> None:
        self.path_to_date = PathDateExtractor(config.directory_matching)

        self.files = FilesCache(files, "data/output-files.jsonl")
        models_cache = SQLiteCache(
            features, ImageClassification, "data/output-image-to-text.jsonl", enforce_version=True
        )
        self.models = Models(models_cache, annotate_url)
        exif_cache = SQLiteCache(features, ImageExif, "data/output-exif.jsonl", enforce_version=True)
        self.exif = Exif(exif_cache)
        geolocator_cache = SQLiteCache(features, GeoAddress, "data/output-geo.jsonl", enforce_version=True)
        self.geolocator = Geolocator(geolocator_cache)
        self.session = session

        self.prio_progress = {
            tp: ProgressBar(desc=f"Realtime ingest {tp.name}", permanent=True) for tp in JobType
        }
        self.default_progress = {
            tp: ProgressBar(desc=f"Backfill ingest {tp.name}", permanent=True, smoothing=0.003)
            for tp in JobType
        }
        self.known_paths: t.Set[str] = set()

    def cheap_features(
        self, path: PathWithMd5
    ) -> t.Tuple[
        PathWithMd5,
        WithMD5[ImageExif],
        t.Optional[WithMD5[GeoAddress]],
        t.Optional[datetime.datetime],
    ]:
        exif_item = self.exif.process_image(path)
        geo = None
        if exif_item.p.gps is not None:
            # TODO: do recomputation based on the last_update
            geo = self.geolocator.address(
                path, exif_item.p.gps.latitude, exif_item.p.gps.longitude, recompute=False
            )
        path_date = self.path_to_date.extract_date(path.path)
        return (path, exif_item, geo, path_date)

    async def image_to_text(self, path: PathWithMd5) -> t.Tuple[PathWithMd5, WithMD5[ImageClassification]]:
        itt = await self.models.process_image(self.session, path)
        return (path, itt)


class QueueItem(t.Generic[T]):
    def __init__(self, priority: int, rank: float, payload: T) -> None:
        self.priority = priority
        self.rank = rank
        self.payload = payload

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, QueueItem):
            raise NotImplementedError
        return (self.priority, self.rank) < (other.priority, other.rank)


async def worker(
    name: str, context: GlobalContext, queue: asyncio.PriorityQueue[QueueItem[t.Tuple[PathWithMd5, JobType]]]
) -> None:
    while True:
        # Get a "work item" out of the queue.
        item = await queue.get()
        path, type_ = item.payload
        try:
            if type_ == JobType.CHEAP_FEATURES:
                context.cheap_features(path)
            elif type_ == JobType.IMAGE_TO_TEXT:
                await context.image_to_text(path)
        # pylint: disable = broad-exception-caught
        except Exception as e:
            traceback.print_exc()
            print("Error while processing path in ", name, path, e, file=sys.stderr)
        finally:
            # Notify the queue that the "work item" has been processed.
            if item.priority >= DEFAULT_PRIORITY:
                context.default_progress[type_].update(1)
            else:
                context.prio_progress[type_].update(1)
            queue.task_done()
            # So that we gave up place for other workers too
            await asyncio.sleep(0)


class Queues:
    def __init__(self) -> None:
        self.cheap_features: asyncio.PriorityQueue[
            QueueItem[t.Tuple[PathWithMd5, JobType]]
        ] = asyncio.PriorityQueue()
        self.image_to_text: asyncio.PriorityQueue[
            QueueItem[t.Tuple[PathWithMd5, JobType]]
        ] = asyncio.PriorityQueue()
        self._index = 0

    def enqueue_path(self, context: GlobalContext, path: str, priority: int) -> None:
        if path in context.known_paths:
            return
        context.known_paths.add(path)
        if not os.path.exists(path):
            return
        file_row = context.files.get(path)
        if file_row is None:
            path_with_md5 = compute_md5(path)
            context.files.add(path, path_with_md5.md5)
        else:
            path_with_md5 = PathWithMd5(path, file_row.md5)
        self.cheap_features.put_nowait(
            QueueItem(priority, self._index, (path_with_md5, JobType.CHEAP_FEATURES))
        )
        self.image_to_text.put_nowait(
            QueueItem(priority, random.random(), (path_with_md5, JobType.IMAGE_TO_TEXT))
        )
        self._index += 1


async def inotify_worker(name: str, dirs: t.List[str], context: GlobalContext, queues: Queues) -> None:
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
            if supported_media(path) is None:
                continue
            if not os.path.exists(path):
                continue
            if not os.path.isfile(path):
                continue
            queues.enqueue_path(context, path, 23)


async def reingest_directories_worker(context: GlobalContext, config: Config, queues: Queues) -> None:
    total_for_reingest = 0
    while True:
        await queues.cheap_features.join()
        found_something = False
        for path in get_paths(config.input_patterns, config.input_directories):
            queues.enqueue_path(context, path, DEFAULT_PRIORITY)
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
    parser = argparse.ArgumentParser(prog="Photo annotator")
    parser.add_argument("--config", default="config.yaml", type=str)
    parser.add_argument("--db", default="data/photos.db", type=str)
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
        context = GlobalContext(config, features, files, session, args.annotate_url)
        queues = Queues()

        tasks.append(asyncio.create_task(reingest_directories_worker(context, config, queues)))
        for i in range(1):
            task = asyncio.create_task(worker(f"worker-cheap-{i}", context, queues.cheap_features))
        for i in range(args.image_to_text_workers):
            task = asyncio.create_task(worker(f"worker-image-to-text-{i}", context, queues.image_to_text))
            tasks.append(task)
        tasks.append(
            asyncio.create_task(inotify_worker("watch-files", config.watched_directories, context, queues))
        )
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
