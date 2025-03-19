from __future__ import annotations

import enum
import json
from datetime import datetime
from dataclasses import dataclass
import typing as t

from dataclasses_json import DataClassJsonMixin
from geopy.distance import distance

from fastapi.routing import APIRoute

from pphoto.data_model.config import DBFilesConfig, Config
from pphoto.db.connection import PhotosConnection, GalleryConnection, JobsConnection
from pphoto.db.types_location import LocPoint
from pphoto.gallery.db import ImageSqlDB, Image as ImageRow
from pphoto.gallery.url import SearchQuery
from pphoto.utils import Lazy
from pphoto.remote_jobs.types import (
    ManualLocation,
    TextAnnotation,
)

DB = Lazy(
    lambda: ImageSqlDB(
        PhotosConnection(DBFilesConfig().photos_db, check_same_thread=False),
        GalleryConnection(DBFilesConfig().gallery_db, check_same_thread=False),
        JobsConnection(DBFilesConfig().jobs_db, check_same_thread=False),
    )
)

CONFIG = Lazy(lambda: Config.load("config.yaml"))


def custom_generate_unique_id(route: APIRoute) -> str:
    method = "_".join(sorted(route.methods))
    if route.tags:
        return f"{route.tags[0]}-{route.name}-{method}"
    return f"{route.name}-{method}"


T = t.TypeVar("T")
R = t.TypeVar("R")


def forward_backward(
    seq: t.Sequence[T], fun: t.Callable[[T], t.Optional[R]]
) -> t.List[t.Tuple[t.Optional[R], t.Optional[R]]]:
    last = None
    backward: t.List[t.Optional[R]] = []
    for omg in reversed(seq):
        backward.append(last)
        last = fun(omg) or last
    last = None
    forward: t.List[t.Tuple[t.Optional[R], t.Optional[R]]] = []
    for index, omg in enumerate(seq):
        forward.append((last, backward[-(index + 1)]))
        last = fun(omg) or last
    return forward


def distance_m(p1: LocPoint, p2: LocPoint) -> float:
    return t.cast(float, distance((p1.latitude, p1.longitude), (p2.latitude, p2.longitude)).m)


@dataclass
class DateWithLoc:
    loc: LocPoint
    date: datetime

    @staticmethod
    def from_image(omg: ImageRow) -> t.Optional[DateWithLoc]:
        if omg.latitude is not None and omg.longitude is not None and omg.date is not None:
            return DateWithLoc(LocPoint(omg.latitude, omg.longitude), omg.date)
        return None

    def distance(self, other: DateWithLoc) -> float:
        return t.cast(
            float,
            distance((self.loc.latitude, self.loc.longitude), (other.loc.latitude, other.loc.longitude)).m,
        )

    def timedist(self, other: datetime) -> float:
        return abs((self.date - other).total_seconds())


@dataclass
class ReferenceStats:
    distance_m: float
    seconds: float  # noqa: F841


@dataclass
class PredictedLocation:
    loc: LocPoint
    earlier: t.Optional[ReferenceStats]
    later: t.Optional[ReferenceStats]  # noqa: F841


def predict_location(
    omg: ImageRow,
    prev_loc: t.Optional[DateWithLoc] = None,
    next_loc: t.Optional[DateWithLoc] = None,
) -> t.Optional[PredictedLocation]:
    if omg.date is None:
        return None
    if omg.latitude is not None and omg.longitude is not None:
        return None
    if prev_loc is not None and next_loc is not None:
        prev_d = prev_loc.timedist(omg.date)
        next_d = next_loc.timedist(omg.date)
        t_d = prev_d + next_d
        if t_d == 0:
            loc_point = prev_loc.loc + (next_loc.loc - prev_loc.loc).scale(0.5)
        else:
            loc_point = prev_loc.loc + (next_loc.loc - prev_loc.loc).scale(prev_d / t_d)
        return PredictedLocation(
            loc_point,
            ReferenceStats(distance_m(prev_loc.loc, loc_point), prev_d),
            ReferenceStats(distance_m(loc_point, next_loc.loc), next_d),
        )
    if prev_loc is not None:
        return PredictedLocation(
            prev_loc.loc,
            ReferenceStats(0.0, prev_loc.timedist(omg.date)),
            None,
        )
    if next_loc is not None:
        return PredictedLocation(
            next_loc.loc,
            None,
            ReferenceStats(0.0, next_loc.timedist(omg.date)),
        )
    return None


class ManualLocationOverride(enum.Enum):
    NO_LOCATION_NO_MANUAL = "NoLocNoMan"
    NO_LOCATION_YES_MANUAL = "NoLocYeMan"
    YES_LOCATION_NO_MANUAL = "YeLocNoMan"
    YES_LOCATION_YES_MANUAL = "YeLocYeMan"


class TextAnnotationOverride(enum.Enum):
    EXTEND_MANUAL = "ExMan"
    NO_MANUAL = "NoMan"
    YES_MANUAL = "YeMan"


@dataclass
class LocationQueryFixedLocation(DataClassJsonMixin):
    t: t.Literal["FixedLocation"]
    location: ManualLocation
    override: ManualLocationOverride


@dataclass
class MassManualAnnotationDeprecated(DataClassJsonMixin):
    query: SearchQuery
    location: ManualLocation
    location_override: ManualLocationOverride
    text: TextAnnotation
    text_override: TextAnnotationOverride


@dataclass
class TextQueryFixedText(DataClassJsonMixin):
    t: t.Literal["FixedText"]
    text: TextAnnotation
    override: TextAnnotationOverride
    loc_only: bool


@dataclass
class AnnotationOverlayInterpolateLocation(DataClassJsonMixin):
    t: t.Literal["InterpolatedLocation"]
    location: ManualLocation  # Actually not manual location, it's just sample. But structurally same type


@dataclass
class AnnotationOverlayNoLocation(DataClassJsonMixin):
    t: t.Literal["NoLocation"]


@dataclass
class TransDate(DataClassJsonMixin):
    t: t.Literal["TransDate"]
    adjust_dates: bool


LocationTypes = (
    LocationQueryFixedLocation | AnnotationOverlayInterpolateLocation | AnnotationOverlayNoLocation
)
TextTypes = TextQueryFixedText
DateTypes = TransDate


@dataclass
class MassLocationAndTextAnnotation(DataClassJsonMixin):
    t: t.Literal["MassLocAndTxt"]
    query: SearchQuery
    location: LocationTypes
    text: TextTypes
    date: DateTypes


def mass_manual_annotation_migrate(params: MassManualAnnotationDeprecated) -> MassLocationAndTextAnnotation:
    return MassLocationAndTextAnnotation(
        "MassLocAndTxt",
        params.query,
        LocationQueryFixedLocation(
            "FixedLocation",
            params.location,
            params.location_override,
        ),
        TextQueryFixedText(
            "FixedText",
            params.text,
            params.text_override,
            False,
        ),
        TransDate(
            "TransDate",
            False,
        ),
    )


def mass_manual_annotation_from_json(j: bytes) -> MassLocationAndTextAnnotation:
    d = json.loads(j)
    type_ = d.get("t")
    if type_ is None:
        return mass_manual_annotation_migrate(MassManualAnnotationDeprecated.from_dict(d))
    if type_ == "MassLocAndTxt":
        return MassLocationAndTextAnnotation.from_dict(d)
    raise NotImplementedError
