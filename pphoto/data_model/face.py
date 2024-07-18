from __future__ import annotations

import typing as t

from dataclasses import dataclass
from dataclasses_json import DataClassJsonMixin

from pphoto.data_model.base import HasCurrentVersion


@dataclass
class ImageResolution(DataClassJsonMixin):
    width: int  # noqa: F841
    height: int  # noqa: F841


@dataclass
class Position(DataClassJsonMixin):
    left: int
    top: int
    right: int
    bottom: int

    def to_query_string(self) -> str:
        return ",".join([str(self.left), str(self.top), str(self.right), str(self.bottom)])

    @staticmethod
    def from_query_string(inp: str) -> t.Optional[Position]:
        splitted = inp.split(",")
        if len(splitted) != 4:
            return None
        if any(not x.isnumeric() for x in splitted):
            return None
        return Position(
            int(splitted[0]),
            int(splitted[1]),
            int(splitted[2]),
            int(splitted[3]),
        )


@dataclass
class Face(DataClassJsonMixin):
    """Face is identified by the image and position."""

    position: Position
    embedding: t.List[float]  # noqa: F841


@dataclass
class FaceEmbeddings(HasCurrentVersion):
    resolution: ImageResolution
    faces: t.List[Face]

    @staticmethod
    def current_version() -> int:
        return 0
