from __future__ import annotations

import json
import typing as t

from dataclasses import dataclass, field
from dataclasses_json import DataClassJsonMixin

from pphoto.data_model.base import StorableData

T = t.TypeVar("T")


@dataclass
class Box(DataClassJsonMixin):
    classification: str
    confidence: float
    xyxy: t.List[float]


@dataclass
class Classification(DataClassJsonMixin):
    name: str
    confidence: float


@dataclass
class BoxClassification(DataClassJsonMixin):
    box: Box
    classifications: t.List[Classification]


@dataclass
class ImageClassification(StorableData):
    captions: t.List[str]
    boxes: t.List[BoxClassification]
    exception: t.Optional[str] = field(default=None)  # noqa: F841

    def to_json_dict(self) -> t.Any:
        return {
            "captions": self.captions,
            "boxes": [x.to_dict(encode_json=True) for x in self.boxes],
            "exception": self.exception,
        }

    @staticmethod
    def from_json_dict(d: t.Dict[str, t.Any]) -> ImageClassification:
        return ImageClassification(
            d["captions"],
            [BoxClassification.from_dict(x) for x in d["boxes"]],
            d.get("exception"),
        )

    @staticmethod
    def from_json_bytes(x: bytes) -> ImageClassification:
        return ImageClassification.from_json_dict(json.loads(x))

    @staticmethod
    def current_version() -> int:
        return 0
