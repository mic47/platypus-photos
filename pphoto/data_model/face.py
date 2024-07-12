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
