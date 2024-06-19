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
    tsfrom: t.Optional[float] = None
    tsto: t.Optional[float] = None
    skip_with_location: bool = False
    skip_being_annotated: bool = False
