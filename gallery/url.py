import typing as t
from dataclasses import dataclass
from datetime import datetime


@dataclass
class GalleryPaging:
    page: int = 0
    paging: int = 100


@dataclass
class SearchQuery:
    tag: str = ""
    cls: str = ""
    addr: str = ""
    datefrom: t.Optional[datetime] = None
    dateto: t.Optional[datetime] = None
    directory: str = ""
    tsfrom: t.Optional[float] = None
    tsto: t.Optional[float] = None
