import typing as t
from dataclasses import dataclass
from datetime import datetime

from gallery.utils import maybe_datetime_to_date


@dataclass
class SearchQuery:
    tag: str = ""
    cls: str = ""
    addr: str = ""
    datefrom: t.Optional[datetime] = None
    dateto: t.Optional[datetime] = None
    page: int = 0
    paging: int = 100
    directory: str = ""
    tsfrom: t.Optional[float] = None
    tsto: t.Optional[float] = None

    def to_url(
        self,
        tag: t.Optional[str] = None,
        add_tag: t.Optional[str] = None,
        cls: t.Optional[str] = None,
        addr: t.Optional[str] = None,
        datefrom: t.Optional[datetime] = None,
        dateto: t.Optional[datetime] = None,
        page: t.Optional[int] = None,
        paging: t.Optional[int] = None,
        oi: t.Optional[int] = None,
        directory: t.Optional[str] = None,
        tsfrom: t.Optional[float] = None,
        tsto: t.Optional[float] = None,
    ) -> str:
        tag = tag or self.tag
        if add_tag:
            if tag:
                tag = f"{tag},{add_tag}"
            else:
                tag = add_tag or ""
        cls = cls or self.cls
        addr = addr or self.addr
        page = page if page is not None else self.page
        paging = paging or self.paging
        datefrom_ = maybe_datetime_to_date(datefrom or self.datefrom) or ""
        dateto_ = maybe_datetime_to_date(dateto or self.dateto) or ""
        directory = directory or self.directory
        tsfrom = tsfrom or self.tsfrom
        tsto = tsto or self.tsto
        parts: t.List[t.Tuple[str, t.Union[str, int, float, None]]] = [
            ("tag", tag),
            ("cls", cls),
            ("addr", addr),
            ("datefrom", datefrom_),
            ("dateto", dateto_),
            ("page", page),
            ("paging", paging),
            ("dir", directory),
            ("tsfrom", tsfrom),
            ("tsto", tsto),
        ]
        if oi is not None:
            parts.append(("oi", oi))
        parts_url = "&".join(f"{k}={v}" for k, v in parts if v is not None and v != "")
        ret = f"?{parts_url}"
        return ret

    def prev_url(self, overlay: bool = False) -> t.Optional[str]:
        if self.page <= 0:
            return None
        if overlay:
            oi = self.paging - 1
        else:
            oi = None
        return self.to_url(page=self.page - 1, oi=oi)

    def next_url(self, has_next_page: bool, overlay: bool = False) -> t.Optional[str]:
        if not has_next_page:
            return None
        if overlay:
            oi = 0
        else:
            oi = None
        return self.to_url(page=self.page + 1, oi=oi)
