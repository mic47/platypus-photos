import datetime as dt
import typing as t
from dataclasses import dataclass
import enum

from dataclasses_json import DataClassJsonMixin


class SortBy(enum.Enum):
    TIMESTAMP = "TIMESTAMP"
    RANDOM = "RANDOM"


class SortOrder(enum.Enum):
    DESC = "DESC"
    ASC = "ASC"


@dataclass
class SortParams:
    sort_by: SortBy = SortBy.TIMESTAMP
    order: SortOrder = SortOrder.DESC


@dataclass
class GalleryPaging:
    page: int = 0
    paging: int = 100


@dataclass
class SearchQuery(DataClassJsonMixin):
    tag: str = ""
    cls: str = ""
    addr: str = ""
    directory: str = ""
    camera: str = ""
    identity: t.Optional[str] = None
    tsfrom: t.Optional[float] = None
    tsto: t.Optional[float] = None
    skip_with_location: bool = False
    skip_being_annotated: bool = False
    timestamp_trans: t.Optional[str] = None

    def to_user_string(self) -> str:
        out_parts = []
        # Intentionally skipping directory
        # Intentionally skipping skip_being_annotated
        # Intentionally skipping timestamp_trans
        if self.addr:
            out_parts.append(f"in_{self.addr}")
        if self.tsfrom:
            out_parts.append(dt.datetime.fromtimestamp(self.tsfrom).isoformat())
        if self.tsto:
            out_parts.append(dt.datetime.fromtimestamp(self.tsto).isoformat())
        if self.identity or self.tag or self.cls:
            out_parts.append("with")
        if self.identity:
            out_parts.append(self.identity)
        if self.tag:
            out_parts.append(self.tag)
        if self.cls:
            out_parts.append(self.cls)
        if self.camera:
            out_parts.append(f"by_{self.camera}")
        if self.skip_with_location:
            out_parts.append("without_location")
        return "_".join(out_parts)
