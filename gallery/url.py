import typing as t
from dataclasses import dataclass
from datetime import datetime, timedelta

from gallery.utils import maybe_datetime_to_date

@dataclass
class UrlParameters:
    tag: str
    cls: str
    addr: str
    datefrom: t.Optional[datetime]
    dateto: t.Optional[datetime]
    page: int
    paging: int

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
        ret = f"?tag={tag}&cls={cls}&addr={addr}&datefrom={datefrom_}&dateto={dateto_}&page={page}&paging={paging}"
        if oi is not None:
            ret = f"{ret}&oi={oi}"
        return ret

    def prev_url(self, overlay: bool = False) -> t.Optional[str]:
        if self.page <= 0:
            return None
        if overlay:
            oi = self.paging - 1
        else:
            oi = None
        return self.to_url(page=self.page - 1, oi=oi)

    def next_url(self, total_images: int, overlay: bool = False) -> t.Optional[str]:
        if (self.page + 1) * self.paging >= total_images:
            return None
        if overlay:
            oi = 0
        else:
            oi = None
        return self.to_url(page=self.page + 1, oi=oi)
