from __future__ import annotations

import json
import typing as t

from dataclasses import dataclass, field

from pphoto.data_model.base import StorableData

T = t.TypeVar("T")


@dataclass
class Box:
    classification: str
    confidence: float
    xyxy: t.List[float]

    def to_json_dict(self) -> t.Any:
        return {
            "classification": self.classification,
            "confidence": self.confidence,
            "xyxy": self.xyxy,
        }

    @staticmethod
    def from_json_dict(d: t.Dict[str, t.Any]) -> Box:
        return Box(
            d["classification"],
            d["confidence"],
            d["xyxy"],
        )


@dataclass
class Classification:
    name: str
    confidence: float

    def to_json_dict(self) -> t.Any:
        return {
            "name": self.name,
            "confidence": self.confidence,
        }

    @staticmethod
    def from_json_dict(d: t.Dict[str, t.Any]) -> Classification:
        return Classification(
            d["name"],
            d["confidence"],
        )


@dataclass
class BoxClassification:
    box: Box
    classifications: t.List[Classification]

    def to_json_dict(self) -> t.Any:
        return {
            "box": self.box.to_json_dict(),
            "classifications": [x.to_json_dict() for x in self.classifications],
        }

    @staticmethod
    def from_json_dict(d: t.Dict[str, t.Any]) -> BoxClassification:
        c = d["classifications"]
        assert isinstance(c, list)
        return BoxClassification(
            Box.from_json_dict(d["box"]),
            [Classification.from_json_dict(x) for x in c],
        )


@dataclass
class ImageClassification(StorableData):
    captions: t.List[str]
    boxes: t.List[BoxClassification]
    exception: t.Optional[str] = field(default=None)  # noqa: F841

    def to_json_dict(self) -> t.Any:
        return {
            "captions": self.captions,
            "boxes": [x.to_json_dict() for x in self.boxes],
            "exception": self.exception,
        }

    @staticmethod
    def from_json_dict(d: t.Dict[str, t.Any]) -> ImageClassification:
        return ImageClassification(
            d["captions"],
            [BoxClassification.from_json_dict(x) for x in d["boxes"]],
            d.get("exception"),
        )

    @staticmethod
    def from_json_bytes(x: bytes) -> ImageClassification:
        return ImageClassification.from_json_dict(json.loads(x))

    @staticmethod
    def current_version() -> int:
        return 0
