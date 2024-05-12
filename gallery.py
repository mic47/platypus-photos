import json
import typing as t
import os
from collections import Counter, defaultdict
import sys
import re
import copy
from datetime import datetime, timedelta
from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from tqdm import tqdm

from image_annotation import ImageAnnotations

app = FastAPI()
# TODO: serve these differenty
app.mount("/static", StaticFiles(directory="static/"), name="static")
templates = Jinja2Templates(directory="templates")


IMAGES: t.List[ImageAnnotations] = []
HASH_TO_IMAGE: t.Dict[int, str] = {}

with open("output-all.jsonl") as f:
    for line in tqdm(f, desc="Loading images"):
        j = json.loads(line)
        if (j.get("version") or 0) != ImageAnnotations.current_version():
            continue
        _image = ImageAnnotations.from_dict(j)
        IMAGES.append(_image)
        HASH_TO_IMAGE[hash(_image.image)] = _image.image


@app.get(
    "/img",
    responses={
        200: {"description": "photo", "content": {"image/jpeg": {"example": "No example available."}}}
    },
)
def image_endpoint(hsh: int) -> t.Any:
    file_path = os.path.join(HASH_TO_IMAGE[hsh])
    if os.path.exists(file_path):
        # TODO: fix media type
        return FileResponse(file_path, media_type="image/jpeg", filename=file_path.split("/")[-1])
    return {"error": "File not found!"}


def in_tags(what: str, tags: t.Iterable[str]) -> bool:
    for tag in tags:
        if what in tag:
            return True
    return False


def classify_tag(value: float) -> str:
    if value >= 0.5:
        return ""
    if value >= 0.2:
        return "🤷"
    return "🗑️"


def maybe_datetime_to_date(value: t.Optional[datetime]) -> t.Optional[str]:
    if value is None:
        return None
    return f"{value.year}-{value.month:02d}-{value.day:02d}"


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
        page: t.Optional[int] = None,
        paging: t.Optional[int] = None,
    ) -> str:
        tag = tag or self.tag
        if add_tag:
            if tag:
                tag = f"{tag},{add_tag}"
            else:
                tag = add_tag or ""
        cls = cls or self.cls
        addr = addr or self.addr
        page = page or self.page
        paging = paging or self.paging
        datefrom = maybe_datetime_to_date(self.datefrom) or ""
        dateto = maybe_datetime_to_date(self.dateto) or ""
        return f"?tag={tag}&cls={cls}&addr={addr}&datefrom={datefrom}&dateto={dateto}&page={page}&paging={paging}"

    def prev_url(self) -> t.Optional[str]:
        if self.page <= 0:
            return None
        return self.to_url(page=self.page - 1)

    def next_url(self, total_images: int) -> t.Optional[str]:
        if (self.page + 1) * self.paging >= total_images:
            return None
        return self.to_url(page=self.page + 1)


@app.get("/index.html", response_class=HTMLResponse)
@app.get("/", response_class=HTMLResponse)
async def read_item(
    request: Request, tag: str = "", cls: str = "", addr: str = "", page: int = 0, paging: int = 100
) -> HTMLResponse:
    url = UrlParameters(tag, cls, addr, None, None, page, paging)
    del tag
    del cls
    del addr
    del page
    del paging
    images = []
    tag_cnt: t.Counter[str] = Counter()
    classifications_cnt: t.Counter[str] = Counter()
    address_cnt: t.Counter[str] = Counter()
    for image in IMAGES:
        tags: t.Dict[str, float] = defaultdict(lambda: 0.0)
        for boxes in image.text_classification.boxes:
            confidence = boxes.box.confidence
            for classification in boxes.classifications:
                name = classification.name.replace("_", " ").lower()
                tags[name] += confidence * classification.confidence

        if url.tag:
            if any(not in_tags(tt, tags.keys()) for tt in url.tag.split(",") if tt):
                continue
        classifications = ";".join(image.text_classification.captions).lower()
        if url.cls:
            if re.search(url.cls, classifications) is None:
                continue

        address_parts = []
        if image.address is not None:
            if image.address.name is not None:
                address_parts.append(image.address.name)
            if image.address.country is not None:
                address_parts.append(image.address.country)

        address = ", ".join(address_parts)
        if url.addr:
            if re.search(url.addr.lower(), address.lower()) is None:
                continue

        max_tag = min(1, max(tags.values(), default=1.0))
        date = None
        if image.exif.date is not None:
            date = image.exif.date.datetime
        date = date or image.date_from_path
        images.append(
            {
                "hsh": hash(image.image),
                "classifications": classifications,
                "tags": [
                    (tg, classify_tag(x / max_tag), url.to_url(add_tag=tg))
                    for tg, x in sorted(tags.items(), key=lambda x: -x[1])
                ],
                "addrs": [{"address": a, "url": url.to_url(addr=a or None)} for a in address_parts],
                "date": maybe_datetime_to_date(date),
            }
        )
        classifications_cnt.update(x.lower() for x in image.text_classification.captions)
        tag_cnt.update(tags.keys())
        address_cnt.update(address_parts)
    top_tags = sorted(tag_cnt.items(), key=lambda x: -x[1])
    top_cls = sorted(classifications_cnt.items(), key=lambda x: -x[1])
    top_addr = sorted(address_cnt.items(), key=lambda x: -x[1])

    if url.page * url.paging >= len(images):
        url.page = len(images) // url.paging

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "id": id,
            "images": images[url.page * url.paging : (url.page + 1) * url.paging],
            "total": len(images),
            "urls": {
                "next": url.next_url(len(images)),
                "prev": url.prev_url(),
            },
            "input": {
                "tag": url.tag,
                "cls": url.cls,
                "addr": url.addr,
            },
            "top": {
                "tag": [(tg, s, url.to_url(add_tag=tg)) for tg, s in top_tags[:15]],
                "cls": [(cl, s, url.to_url(cls=cl)) for cl, s in top_cls[:5]],
                "addr": [(ad, s, url.to_url(addr=ad)) for ad, s in top_addr[:15]],
            },
        },
    )


def add_comma(x: str) -> str:
    if x:
        return f"{x},"
    return x
