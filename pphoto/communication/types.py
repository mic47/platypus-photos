from __future__ import annotations

import dataclasses as dc
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
class SystemStatus(dj.DataClassJsonMixin):
    progress_bars: t.List[t.Tuple[int, ProgressBarProgress]]  # noqa: F841
    current_state: t.Dict[str, State]
    t: t.Literal["SystemStatus"] = "SystemStatus"


ImageWatcherCommands = t.Union[GetSystemStatus]
ImageWatcherResponses = t.Union[SystemStatus]


def image_watcher_encode(x: ImageWatcherCommands | ImageWatcherResponses) -> str:
    return x.to_json()


def image_watcher_decode_command(x: bytes) -> ImageWatcherCommands:
    d = json.loads(x)
    type_ = d["t"]
    if type_ == "GetSystemStatus":
        return GetSystemStatus.from_dict(d)
    assert False, f"Wrong message type {type_}"


def image_watcher_decode_response(x: bytes) -> ImageWatcherResponses:
    d = json.loads(x)
    type_ = d["t"]
    if type_ == "SystemStatus":
        return SystemStatus.from_dict(d)
    assert False, f"Wrong message type {type_}"
