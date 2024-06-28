from __future__ import annotations

import dataclasses
import datetime
import enum
import typing as t

from dataclasses_json import DataClassJsonMixin

from pphoto.data_model.manual import ManualLocation, ManualDate


class RemoteJobType(enum.Enum):
    MASS_MANUAL_ANNOTATION = "mass_manual_annotation"


@dataclasses.dataclass(frozen=True)
class TaskId:
    md5: str
    job_id: int


T = t.TypeVar("T")
R = t.TypeVar("R")


@dataclasses.dataclass
class RemoteJob(t.Generic[T], DataClassJsonMixin):
    id_: int
    type_: RemoteJobType
    total: int
    finished_tasks: int
    original_request: T  # noqa: F841
    created: datetime.datetime
    last_update: t.Optional[datetime.datetime]
    example_path_md5: t.Optional[str]

    def test_sanitize(self) -> RemoteJob[T]:
        self.created = datetime.datetime(1, 1, 1)
        if self.last_update is not None:
            self.last_update = datetime.datetime(1, 1, 1)
        return self


@dataclasses.dataclass
class RemoteTask(t.Generic[T]):
    id_: TaskId
    type_: RemoteJobType
    payload: T
    created: datetime.datetime
    finished_at: t.Optional[datetime.datetime]

    def test_sanitize(self) -> RemoteTask[T]:
        self.created = datetime.datetime(1, 1, 1)
        if self.finished_at is not None:
            self.finished_at = datetime.datetime(1, 1, 1)
        return self

    def map(self, f: t.Callable[[T], R]) -> RemoteTask[R]:
        return RemoteTask(self.id_, self.type_, f(self.payload), self.created, self.finished_at)


@dataclasses.dataclass
class TextAnnotation(DataClassJsonMixin):
    description: t.Optional[str]
    tags: t.Optional[str]


@dataclasses.dataclass
class ManualAnnotationTask(DataClassJsonMixin):
    location: t.Optional[ManualLocation]
    text: t.Optional[TextAnnotation]
    text_extend: bool
    date: t.Optional[ManualDate]  # TODO: set default to None
