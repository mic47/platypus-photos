from __future__ import annotations

import json
import typing as t

from dataclasses import dataclass

from pphoto.data_model.base import StorableData


@dataclass
class ImageResolution:
    width: int  # noqa: F841
    height: int  # noqa: F841

    def to_json_dict(self) -> t.Any:
        return {
            "width": self.width,
            "height": self.height,
        }

    @staticmethod
    def from_json_dict(d: t.Dict[str, t.Any]) -> ImageResolution:
        return ImageResolution(
            int(d["width"]),
            int(d["height"]),
        )


@dataclass(frozen=True, eq=True)
class Position:
    left: int
    top: int
    right: int
    bottom: int

    def to_json_dict(self) -> t.Any:
        return {
            "left": self.left,
            "top": self.top,
            "right": self.right,
            "bottom": self.bottom,
        }

    @staticmethod
    def from_json_dict(d: t.Dict[str, t.Any]) -> Position:
        return Position(
            int(d["left"]),
            int(d["top"]),
            int(d["right"]),
            int(d["bottom"]),
        )

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
class Face:
    """Face is identified by the image and position."""

    position: Position
    embedding: t.List[float]  # noqa: F841

    def to_json_dict(self) -> t.Any:
        return {
            "position": self.position.to_json_dict(),
            "embedding": self.embedding,
        }

    @staticmethod
    def from_json_dict(d: t.Dict[str, t.Any]) -> Face:
        return Face(
            Position.from_json_dict(d["position"]),
            d["embedding"],
        )


@dataclass
class FaceEmbeddings(StorableData):
    resolution: ImageResolution
    faces: t.List[Face]

    def to_json_dict(self) -> t.Any:
        return {
            "resolution": self.resolution.to_json_dict(),
            "faces": [x.to_json_dict() for x in self.faces],
        }

    @staticmethod
    def from_json_dict(d: t.Dict[str, t.Any]) -> FaceEmbeddings:
        return FaceEmbeddings(
            ImageResolution.from_json_dict(d["resolution"]),
            [Face.from_json_dict(x) for x in d["faces"]],
        )

    @staticmethod
    def from_json_bytes(x: bytes) -> FaceEmbeddings:
        return FaceEmbeddings.from_json_dict(json.loads(x))

    @staticmethod
    def current_version() -> int:
        return 0
