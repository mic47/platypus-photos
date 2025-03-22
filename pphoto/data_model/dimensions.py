from __future__ import annotations

import json
import typing as t

from dataclasses import dataclass

from pphoto.data_model.base import StorableData

T = t.TypeVar("T")


@dataclass
class ImageDimensions(StorableData):
    width: int
    height: int
    file_size: int

    @staticmethod
    def current_version() -> int:
        return 0

    def to_json_dict(self) -> t.Any:
        return {
            "w": self.width,
            "h": self.height,
            "s": self.file_size,
        }

    @staticmethod
    def from_json_dict(d: t.Dict[str, t.Any]) -> ImageDimensions:
        return ImageDimensions(int(d["w"]), int(d["h"]), int(d["s"]))

    @staticmethod
    def from_json_bytes(x: bytes) -> ImageDimensions:
        return ImageDimensions.from_json_dict(json.loads(x))
