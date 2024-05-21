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

from cache import Loader
from config import Config
from filename_to_date import PathDateExtractor
from geolocation import GeoAddress
from image_exif import ImageExif
from image_to_text import ImageClassification

from gallery.db import ImageDB, OmgDB, ImageSqlDB
from db.types import Image
from gallery.url import UrlParameters
from gallery.utils import maybe_datetime_to_date, maybe_datetime_to_timestamp


app = FastAPI()
# TODO: serve these differenty
app.mount("/static", StaticFiles(directory="static/"), name="static")
templates = Jinja2Templates(directory="templates")

config = Config.load("config.yaml")
# DB: OmgDB = ImageDB(PathDateExtractor(config.directory_matching))
DB: OmgDB = ImageSqlDB(PathDateExtractor(config.directory_matching))
del config


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
    aggr = DB.get_aggregate_stats(url)
    if url.page * url.paging >= aggr.total:
        url.page = aggr.total // url.paging

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
                "timestamp": maybe_datetime_to_timestamp(omg.date) or 0.0,
            }
        )
    top_tags = sorted(aggr.tag.items(), key=lambda x: -x[1])
    top_cls = sorted(aggr.classification.items(), key=lambda x: -x[1])
    top_addr = sorted(aggr.address.items(), key=lambda x: -x[1])

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "oi": oi,
            "images": images,
            "total": aggr.total,
            "urls": {
                "next": url.next_url(aggr.total),
                "next_overlay": url.next_url(aggr.total, overlay=True),
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


def classify_tag(value: float) -> str:
    if value >= 0.5:
        return ""
    if value >= 0.2:
        return "🤷"
    return "🗑️"
