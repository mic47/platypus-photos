from __future__ import annotations

import dataclasses
import datetime
import enum
import typing as t

from dataclasses_json import DataClassJsonMixin


class JobType(enum.Enum):
    MASS_MANUAL_ANNOTATION = "mass_manual_annotation"


@dataclasses.dataclass
class TaskId:
    md5: str
    job_id: int


@dataclasses.dataclass
class Job:
    id_: int
    type_: JobType
    total: int
    finished_tasks: int
    original_request_json: bytes
    created: datetime.datetime
    last_update: t.Optional[datetime.datetime]

    def test_sanitize(self) -> Job:
        self.created = datetime.datetime(1, 1, 1)
        if self.last_update is not None:
            self.last_update = datetime.datetime(1, 1, 1)
        return self


@dataclasses.dataclass
class Task:
    id_: TaskId
    type_: JobType
    payload_json: bytes
    created: datetime.datetime
    finished_at: t.Optional[datetime.datetime]

    def test_sanitize(self) -> Task:
        self.created = datetime.datetime(1, 1, 1)
        if self.finished_at is not None:
            self.finished_at = datetime.datetime(1, 1, 1)
        return self


@dataclasses.dataclass
class LocationAnnotation(DataClassJsonMixin):
    latitude: float
    longitude: float
    address_name: t.Optional[str]
    address_country: t.Optional[str]


@dataclasses.dataclass
class TextAnnotation(DataClassJsonMixin):
    description: t.Optional[str]
    tags: t.Optional[str]


@dataclasses.dataclass
class MassManualAnnotationTask(DataClassJsonMixin):
    location: t.Optional[LocationAnnotation]
    text: t.Optional[TextAnnotation]
    text_extend: bool
