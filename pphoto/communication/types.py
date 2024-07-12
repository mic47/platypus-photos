from __future__ import annotations

import dataclasses as dc
import enum
import json
import typing as t

import dataclasses_json as dj

from pphoto.utils.alive import State
from pphoto.utils.progress_bar import ProgressBarProgress
from pphoto.data_model.base import PathWithMd5, Error
from pphoto.data_model.face import FaceEmbeddings
from pphoto.data_model.text import (
    ImageClassification,
)

UNIX_CONNECTION_PATH = "unix-domain-socket"

_t = t


@dc.dataclass
class ImageClassificationWithMD5:
    t: _t.Literal["ImageClassificationWithMD5"]
    md5: str
    version: int
    p: _t.Optional[ImageClassification]
    e: _t.Optional[Error]
    # TODO: make test that make sure it's same as WithMD5[ImageClassification]


@dc.dataclass
class FaceEmbeddingsWithMD5:
    t: _t.Literal["FaceEmbeddingsWithMD5"]
    md5: str
    version: int
    p: _t.Optional[FaceEmbeddings]
    e: _t.Optional[Error]


@dc.dataclass
class TextAnnotationRequest(dj.DataClassJsonMixin):
    t: _t.Literal["TextAnnotationRequest"]
    path: PathWithMd5
    data_base64: str
    gap_threshold: float
    discard_threshold: float


@dc.dataclass
class FaceEmbeddingsRequest(dj.DataClassJsonMixin):
    t: _t.Literal["FaceEmbeddingsRequest"]
    path: PathWithMd5
    data_base64: str


@dc.dataclass
class RemoteAnnotatorRequest(dj.DataClassJsonMixin):
    p: TextAnnotationRequest | FaceEmbeddingsRequest


@dc.dataclass
class RemoteAnnotatorResponse(dj.DataClassJsonMixin):
    p: ImageClassificationWithMD5 | FaceEmbeddingsWithMD5


Response = t.TypeVar("Response", bound="dj.DataClassJsonMixin")


@dc.dataclass
class ActualResponse(dj.DataClassJsonMixin):
    response: t.Optional[RemoteAnnotatorResponse]
    error: t.Optional[Error]

    @staticmethod
    def from_exception(e: Exception) -> ActualResponse:
        return ActualResponse(None, Error.from_exception(e))


@dc.dataclass
class GetSystemStatus(dj.DataClassJsonMixin):
    t: t.Literal["GetSystemStatus"] = "GetSystemStatus"


@dc.dataclass
class RefreshJobs(dj.DataClassJsonMixin):
    job_id: int
    t: t.Literal["RefreshJobs"] = "RefreshJobs"


class ImportMode(enum.Enum):
    MOVE = "move"
    MOVE_OR_DELETE = "move_or_delete"
    COPY = "copy"

    def should_delete_original_if_exists(self) -> bool:
        return self == ImportMode.MOVE_OR_DELETE


@dc.dataclass
class ImportDirectory(dj.DataClassJsonMixin):
    import_path: str
    mode: ImportMode = dc.field(default=ImportMode.COPY)
    t: t.Literal["ImportDirectory"] = "ImportDirectory"


@dc.dataclass
class SystemStatus(dj.DataClassJsonMixin):
    progress_bars: _t.List[_t.Tuple[int, ProgressBarProgress]]  # noqa: F841
    current_state: _t.Dict[str, State]
    t: _t.Literal["SystemStatus"] = "SystemStatus"


@dc.dataclass
class Ok(dj.DataClassJsonMixin):
    t: t.Literal["Ok"] = "Ok"


ImageWatcherCommands = t.Union[GetSystemStatus, ImportDirectory, RefreshJobs]
ImageWatcherResponses = t.Union[SystemStatus, Ok]


def image_watcher_encode(x: ImageWatcherCommands | ImageWatcherResponses) -> str:
    return x.to_json()


def image_watcher_decode_command(x: bytes) -> ImageWatcherCommands:
    d = json.loads(x)
    type_ = d["t"]
    if type_ == "GetSystemStatus":
        return GetSystemStatus.from_dict(d)
    if type_ == "ImportDirectory":
        return ImportDirectory.from_dict(d)
    if type_ == "RefreshJobs":
        return RefreshJobs.from_dict(d)
    assert False, f"Wrong message type {type_}"


def image_watcher_decode_response(x: bytes) -> ImageWatcherResponses:
    d = json.loads(x)
    type_ = d["t"]
    if type_ == "SystemStatus":
        return SystemStatus.from_dict(d)
    if type_ == "Ok":
        return Ok.from_dict(d)
    assert False, f"Wrong message type {type_}"
