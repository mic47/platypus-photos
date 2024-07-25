import asyncio
import datetime
import itertools
import random
import typing as t

from pphoto.remote_jobs.types import RemoteTask, ManualAnnotationTask
from pphoto.data_model.base import PathWithMd5
from pphoto.data_model.manual import ManualIdentity
from pphoto.file_mgmt.jobs import JobType, IMPORT_PRIORITY, DEFAULT_PRIORITY
from pphoto.utils import assert_never, DefaultDict, CacheTTL
from pphoto.utils.progress_bar import ProgressBar

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


QueueValue = t.Union[
    t.Tuple[PathWithMd5, t.Literal[JobType.CHEAP_FEATURES] | t.Literal[JobType.IMAGE_TO_TEXT]],
    t.Tuple[RemoteTask[ManualAnnotationTask], t.Literal[JobType.ADD_MANUAL_ANNOTATION]],
    t.Tuple[RemoteTask[t.List[ManualIdentity]], t.Literal[JobType.FACE_CLUSTER_ANNOTATION]],
    t.Tuple[
        t.Tuple[PathWithMd5, t.List[ManualIdentity]],
        t.Literal[JobType.COMPUTE_FACE_EMBEDDING_FOR_MANUAL_ANNOTATION],
    ],
]

Queue = asyncio.PriorityQueue[QueueItem[QueueValue]]


class Queues:
    def __init__(self) -> None:
        self.cheap_features: Queue = asyncio.PriorityQueue()
        self.image_to_text: Queue = asyncio.PriorityQueue()
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

    def enqueue_path(self, values: t.Iterable[QueueValue], priority: int) -> None:
        for value in values:
            _payload, type_ = value
            self.get_progress_bar(type_, priority).add_to_total(1)
            if type_ == JobType.CHEAP_FEATURES:
                self.cheap_features.put_nowait(QueueItem(priority, self._index, value))
                self._index += 1
            elif type_ == JobType.IMAGE_TO_TEXT:
                self.image_to_text.put_nowait(QueueItem(priority, random.random(), value))
            elif type_ == JobType.ADD_MANUAL_ANNOTATION:
                self.cheap_features.put_nowait(QueueItem(priority, self._index, value))
                self._index += 1
            elif type_ == JobType.FACE_CLUSTER_ANNOTATION:
                self.cheap_features.put_nowait(QueueItem(priority, self._index, value))
                self._index += 1
            elif type_ == JobType.COMPUTE_FACE_EMBEDDING_FOR_MANUAL_ANNOTATION:
                self.image_to_text.put_nowait(QueueItem(priority, self._index, value))
                self._index += 1
            else:
                assert_never(type_)

    def enqueue_path_skipped_known(self, path: PathWithMd5, priority: int) -> None:
        if not self.known_paths.mutable_should_update(path):
            return
        self.enqueue_path([(path, JobType.CHEAP_FEATURES), (path, JobType.IMAGE_TO_TEXT)], priority)

    def mark_failed(self, path: PathWithMd5) -> None:
        self.known_paths.delete(path)
