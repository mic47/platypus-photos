import typing as t

from dataclasses import dataclass, field
from dataclasses_json import DataClassJsonMixin

from pphoto.data_model.base import HasCurrentVersion

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
class ImageClassification(HasCurrentVersion):
    captions: t.List[str]
    boxes: t.List[BoxClassification]
    exception: t.Optional[str] = field(default=None)  # noqa: F841

    @staticmethod
    def current_version() -> int:
        return 0
