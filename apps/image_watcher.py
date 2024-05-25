import argparse
import asyncio
import datetime
from enum import Enum
import glob
import os
import random
import re
import sys
import traceback
import typing as t

import aiohttp
from tqdm import tqdm

from data_model.config import Config
from db.cache import SQLiteCache
from db.sql import FeaturesTable, Connection
from annots.date import PathDateExtractor
from annots.exif import Exif, ImageExif
from annots.geo import Geolocator, GeoAddress
from annots.md5 import MD5er, MD5Annot
from annots.text import Models, ImageClassification

VERSION = 0


def walk_tree(path: str, extensions: t.Optional[t.List[str]] = None) -> t.Iterable[str]:
    if extensions is None:
        extensions = ["jpg", "jpeg", "JPG", "JEPG"]
    for directory, _subdirs, files in os.walk(path):
        yield from (f"{directory}/{file}" for file in files if file.split(".")[-1] in extensions)


class JobType(Enum):
    CHEAP_FEATURES = 1
    IMAGE_TO_TEXT = 2


class GlobalContext:
    def __init__(
        self,
        config: Config,
        features: FeaturesTable,
        session: aiohttp.ClientSession,
        annotate_url: t.Optional[str],
    ) -> None:
        self.path_to_date = PathDateExtractor(config.directory_matching)

        models_cache = SQLiteCache(
            features, ImageClassification, "output-image-to-text.jsonl", enforce_version=True
        )
        self.models = Models(models_cache, annotate_url)
        exif_cache = SQLiteCache(features, ImageExif, "output-exif.jsonl", enforce_version=True)
        self.exif = Exif(exif_cache)
        geolocator_cache = SQLiteCache(features, GeoAddress, "output-geo.jsonl", enforce_version=True)
        self.geolocator = Geolocator(geolocator_cache)
        md5_cache = SQLiteCache(features, MD5Annot, "output-md5.jsonl", enforce_version=True)
        self.md5 = MD5er(md5_cache)
        self.session = session
        self.progress = {
            tp: tqdm(desc=f"Ingest {tp.name}", position=position) for position, tp in enumerate(JobType)
        }

    def cheap_features(
        self, path: str
    ) -> t.Tuple[str, MD5Annot, ImageExif, t.Optional[GeoAddress], t.Optional[datetime.datetime]]:
        exif_item = self.exif.process_image(path)
        geo = None
        if exif_item.gps is not None:
            # TODO: do recomputation based on the last_update
            geo = self.geolocator.address(
                path, exif_item.gps.latitude, exif_item.gps.longitude, recompute=False
            )
        md5hsh = self.md5.process(path)
        path_date = self.path_to_date.extract_date(path)
        return (path, md5hsh, exif_item, geo, path_date)

    async def image_to_text(self, path: str) -> t.Tuple[str, ImageClassification]:
        itt = (await self.models.process_image_batch(self.session, [path]))[0]
        return (path, itt)


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


async def worker(
    name: str, context: GlobalContext, queue: asyncio.PriorityQueue[QueueItem[t.Tuple[str, JobType]]]
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
            context.progress[type_].update(1)
            queue.task_done()
            # So that we gave up place for other workers too
            await asyncio.sleep(0)


def get_paths(config: Config) -> t.List[str]:
    paths = [
        file
        for pattern in tqdm(config.input_patterns, desc="Listing files")
        for file in tqdm(glob.glob(re.sub("^~/", os.environ["HOME"] + "/", pattern)), desc=pattern)
    ]
    for directory in tqdm(config.input_directories, desc="Listing directories"):
        paths.extend(walk_tree(re.sub("^~/", os.environ["HOME"] + "/", directory)))
    return paths


async def main() -> None:
    parser = argparse.ArgumentParser(prog="Photo annotator")
    parser.add_argument("--config", default="config.yaml", type=str)
    parser.add_argument("--db", default="output.db", type=str)
    parser.add_argument("--image-to-text-workers", default=3, type=int)
    parser.add_argument("--annotate-url", default=None, type=str)
    args = parser.parse_args()
    config = Config.load(args.config)
    features = FeaturesTable(Connection(args.db))
    async with aiohttp.ClientSession() as session:
        context = GlobalContext(config, features, session, args.annotate_url)
        cheap_queue: asyncio.PriorityQueue[QueueItem[t.Tuple[str, JobType]]] = asyncio.PriorityQueue()
        image_to_text_queue: asyncio.PriorityQueue[QueueItem[t.Tuple[str, JobType]]] = asyncio.PriorityQueue()

        paths = get_paths(config)

        tasks = []
        for i, path in enumerate(tqdm(paths, total=len(paths), desc="Creating Workers")):
            cheap_queue.put_nowait(QueueItem(47, i, (path, JobType.CHEAP_FEATURES)))
            image_to_text_queue.put_nowait(QueueItem(47, random.random(), (path, JobType.IMAGE_TO_TEXT)))
        for tp in [JobType.CHEAP_FEATURES, JobType.IMAGE_TO_TEXT]:
            context.progress[tp].reset(total=len(paths))
        for i in range(1):
            task = asyncio.create_task(worker(f"worker-cheap-{i}", context, cheap_queue))
        for i in range(args.image_to_text_workers):
            task = asyncio.create_task(worker(f"worker-image-to-text-{i}", context, image_to_text_queue))
            tasks.append(task)
        try:
            await cheap_queue.join()
            await image_to_text_queue.join()
        finally:
            for task in tasks:
                task.cancel()
            # Wait until all worker tasks are cancelled.
            await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(main())
