from __future__ import annotations

import dataclasses as dc
import enum
import json
import typing as t

import dataclasses_json as dj

from pphoto.utils.alive import State
from pphoto.utils.progress_bar import ProgressBarProgress

UNIX_CONNECTION_PATH = "unix-domain-socket"


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


_t = t


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
