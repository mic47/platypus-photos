import json
import typing as t
import os
from collections import Counter, defaultdict
import sys
import re
import copy
import asyncio
from datetime import datetime, timedelta
from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from tqdm import tqdm

from image_to_text import ImageClassification
from image_exif import ImageExif
from geolocation import GeoAddress
from image_annotation import ImageAnnotations
from cache import Loader


# This is using
# exif
# date_from_path
# text_classification
# address
@dataclass
class Image:
    path: str
    date: t.Optional[datetime]
    tags: t.Optional[t.Dict[str, float]]
    classifications: t.Optional[str]
    address_country: t.Optional[str]
    address_name: t.Optional[str]
    address_full: t.Optional[str]

    @staticmethod
    def from_path(path: str) -> "Image":
        return Image(path, None, None, None, None, None, None)

    @staticmethod
    def from_updates(
        path: str,
        exif: t.Optional[ImageExif],
        address: t.Optional[GeoAddress],
        text_classification: t.Optional[ImageClassification],
        date_from_path: t.Optional[datetime],
    ) -> "Image":
        date = None
        if exif is not None and exif.date is not None:
            date = exif.date.datetime
        date = date or date_from_path

        tags: t.Dict[str, float] = {}
        if text_classification is not None:
            for boxes in text_classification.boxes:
                confidence = boxes.box.confidence
                for classification in boxes.classifications:
                    name = classification.name.replace("_", " ").lower()
                    if name not in tags:
                        tags[name] = 0.0
                    tags[name] += confidence * classification.confidence

        classifications = ";".join(
            [] if text_classification is None else text_classification.captions
        ).lower()

        address_country = None
        address_name = None
        address_full = None
        if address is not None:
            address_country = address.country
            address_name = address.name
            address_full = ", ".join(x for x in [address_name, address_country] if x)

        return Image(path, date, tags, classifications, address_country, address_name, address_full)

    @staticmethod
    def from_annotation(image: ImageAnnotations) -> "Image":
        return Image.from_updates(
            image.image, image.exif, image.address, image.text_classification, image.date_from_path
        )

    def match_url(self, url: "UrlParameters") -> bool:
        return (
            self.match_date(url.datefrom, url.dateto)
            and self.match_tags(url.tag)
            and self.match_classifications(url.cls)
            and self.match_address(url.addr)
        )

    def match_date(self, datefrom: t.Optional[datetime], dateto: t.Optional[datetime]) -> bool:
        if self.date is not None:
            to_compare = self.date.replace(tzinfo=None)
            if datefrom is not None and to_compare < datefrom:
                return False
            if dateto is not None:
                to_compare -= timedelta(days=1)
                if to_compare > dateto:
                    return False
        else:
            if datefrom is not None or dateto is not None:
                # Datetime filter is on, so skipping stuff without date
                return False
        return True

    def match_tags(self, tag: str) -> bool:
        if not tag:
            return True
        if self.tags is None:
            return False
        return not any(not in_tags(tt, self.tags.keys()) for tt in tag.split(",") if tt)

    def match_classifications(self, classifications: str) -> bool:
        if not classifications:
            return True
        if self.classifications is None:
            return False
        return re.search(classifications, self.classifications) is not None

    def match_address(self, addr: str) -> bool:
        if not addr:
            return True
        if self.address_full is None:
            return False
        return re.search(addr.lower(), self.address_full.lower()) is not None


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


class ImageDB:
    def __init__(self, file: str):
        self._loader = Loader(file, ImageAnnotations, lambda x: self.load_image(x))
        self._images: t.List[Image] = []
        self._image_to_index: t.Dict[str, int] = {}
        self._hash_to_image: t.Dict[int, str] = {}

    def load(self, show_progress: bool) -> None:
        self._loader.load(show_progress=show_progress)

    def load_image(self, image: ImageAnnotations) -> None:
        omg = Image.from_annotation(image)
        _index = self._image_to_index.get(omg.path)
        if _index is None:
            self._image_to_index[omg.path] = len(self._images)
            self._images.append(omg)
        else:
            self._images[_index] = omg
        self._hash_to_image[hash(omg.path)] = omg.path

    def get_matching_images(self, url: "UrlParameters") -> t.Iterable[Image]:
        for image in self._images:
            if image.match_url(url):
                yield image

    def get_path_from_hash(self, hsh: int) -> str:
        return self._hash_to_image[hsh]


app = FastAPI()
# TODO: serve these differenty
app.mount("/static", StaticFiles(directory="static/"), name="static")
templates = Jinja2Templates(directory="templates")
DB = ImageDB("output-all.jsonl")


@app.on_event("startup")
async def on_startup() -> None:
    global DB
    DB.load(show_progress=True)
    asyncio.create_task(auto_load())


async def auto_load() -> None:
    global DB
    while True:
        DB.load(show_progress=False)
        await asyncio.sleep(1)


@app.get(
    "/img",
    responses={
        200: {"description": "photo", "content": {"image/jpeg": {"example": "No example available."}}}
    },
)
def image_endpoint(hsh: int) -> t.Any:
    file_path = DB.get_path_from_hash(hsh)
    if os.path.exists(file_path):
        # TODO: fix media type
        return FileResponse(file_path, media_type="image/jpeg", filename=file_path.split("/")[-1])
    return {"error": "File not found!"}


@app.get("/index.html", response_class=HTMLResponse)
@app.get("/", response_class=HTMLResponse)
async def read_item(
    request: Request,
    tag: str = "",
    cls: str = "",
    addr: str = "",
    page: int = 0,
    paging: int = 100,
    datefrom: str = "",
    dateto: str = "",
    oi: t.Optional[int] = None,
) -> HTMLResponse:
    print(datefrom, dateto)
    url = UrlParameters(
        tag,
        cls,
        addr,
        datetime.strptime(datefrom, "%Y-%m-%d") if datefrom else None,
        datetime.strptime(dateto, "%Y-%m-%d") if dateto else None,
        page,
        paging,
    )
    del tag
    del cls
    del addr
    del page
    del paging
    del datefrom
    del dateto
    images = []
    tag_cnt: t.Counter[str] = Counter()
    classifications_cnt: t.Counter[str] = Counter()
    address_cnt: t.Counter[str] = Counter()
    for omg in DB.get_matching_images(url):

        max_tag = min(1, max((omg.tags or {}).values(), default=1.0))
        images.append(
            {
                "hsh": hash(omg.path),
                "classifications": omg.classifications or "",
                "tags": [
                    (tg, classify_tag(x / max_tag), url.to_url(add_tag=tg))
                    for tg, x in sorted((omg.tags or {}).items(), key=lambda x: -x[1])
                ],
                "addrs": [
                    {"address": a, "url": url.to_url(addr=a or None)}
                    for a in [omg.address_name, omg.address_country]
                    if a
                ],
                "date": {
                    "date": maybe_datetime_to_date(omg.date),
                    "url": url.to_url(datefrom=omg.date, dateto=omg.date),
                },
            }
        )
        classifications_cnt.update([] if omg.classifications is None else omg.classifications.split(";"))
        tag_cnt.update((omg.tags or {}).keys())
        address_cnt.update(a for a in [omg.address_name, omg.address_country] if a)
    top_tags = sorted(tag_cnt.items(), key=lambda x: -x[1])
    top_cls = sorted(classifications_cnt.items(), key=lambda x: -x[1])
    top_addr = sorted(address_cnt.items(), key=lambda x: -x[1])

    if url.page * url.paging >= len(images):
        url.page = len(images) // url.paging

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "oi": oi,
            "images": images[url.page * url.paging : (url.page + 1) * url.paging],
            "total": len(images),
            "urls": {
                "next": url.next_url(len(images)),
                "next_overlay": url.next_url(len(images), overlay=True),
                "prev": url.prev_url(),
                "prev_overlay": url.prev_url(overlay=True),
            },
            "input": {
                "tag": url.tag,
                "cls": url.cls,
                "addr": url.addr,
                "datefrom": maybe_datetime_to_date(url.datefrom) or "",
                "dateto": maybe_datetime_to_date(url.dateto) or "",
            },
            "top": {
                "tag": [(tg, s, url.to_url(add_tag=tg)) for tg, s in top_tags[:15]],
                "cls": [(cl, s, url.to_url(cls=cl)) for cl, s in top_cls[:5]],
                "addr": [(ad, s, url.to_url(addr=ad)) for ad, s in top_addr[:15]],
            },
        },
    )


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
