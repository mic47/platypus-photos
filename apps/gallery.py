import asyncio
import json
import typing as t
import os
import sys
import time
import enum
from datetime import datetime
from dataclasses import dataclass
import traceback

from PIL import Image, ImageFile

from fastapi import FastAPI, Request, Response, Query
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from data_model.config import Config, DBFilesConfig
from db.types import LocationCluster, LocPoint
from db import Connection
from annots.date import PathDateExtractor
from utils import assert_never

from gallery.db import OmgDB, ImageSqlDB
from gallery.url import UrlParameters
from gallery.utils import maybe_datetime_to_date, maybe_datetime_to_timestamp

ImageFile.LOAD_TRUNCATED_IMAGES = True


app = FastAPI()
# TODO: serve these differenty
app.mount("/static", StaticFiles(directory="static/"), name="static")
templates = Jinja2Templates(directory="templates")

config = Config.load("config.yaml")

DB: OmgDB = ImageSqlDB(
    PathDateExtractor(config.directory_matching),
    Connection(DBFilesConfig().photos_db, check_same_thread=False),
)
del config


@app.on_event("startup")
async def on_startup() -> None:
    asyncio.create_task(auto_load())
    asyncio.create_task(check_db_connection())


async def check_db_connection() -> None:
    while True:
        DB.check_unused()
        await asyncio.sleep(10)


async def auto_load() -> None:
    # Allow other tasks to start
    await asyncio.sleep(0)
    sleep_time = 1
    max_sleep_time = 64
    while True:
        try:
            done = DB.load(show_progress=False)
            if done <= 100:
                sleep_time = min(sleep_time * 2, max_sleep_time)
                if done > 0:
                    print(f"Reindexed {done} images.", file=sys.stderr)
            else:
                print(f"Reindexed {done} images.", file=sys.stderr)
                sleep_time = 1
        # pylint: disable = broad-exception-caught
        except Exception as e:
            traceback.print_exc()
            print("Error while trying to refresh data in db:", e)
            sleep_time = 1
            print("Reconnecting")
            DB.reconnect()
        await asyncio.sleep(sleep_time)


@app.middleware("http")
async def log_metadata(request: Request, func: t.Callable[[Request], t.Awaitable[Response]]) -> Response:
    start_time = time.time()
    response = await func(request)
    took = time.time() - start_time
    print("Request took ", request.url, took, file=sys.stderr)
    return response


class ImageSize(enum.Enum):
    ORIGINAL = "original"
    MEDIUM = "medium"
    PREVIEW = "preview"


def sz_to_resolution(size: ImageSize) -> t.Optional[int]:
    if size == ImageSize.ORIGINAL:
        return None
    if size == ImageSize.MEDIUM:
        return 1600
    if size == ImageSize.PREVIEW:
        return 640
    assert_never(size)


def get_cache_file(size: int, hsh: str) -> str:
    return f".cache/{size}/{hsh[0]}/{hsh[1]}/{hsh[2]}/{hsh[3:]}.jpg"


@app.get(
    "/img",
    responses={
        200: {"description": "photo", "content": {"image/jpeg": {"example": "No example available."}}}
    },
)
def image_endpoint(hsh: t.Union[int, str], size: ImageSize = ImageSize.ORIGINAL) -> t.Any:
    sz = sz_to_resolution(size)
    if sz is not None and isinstance(hsh, str):
        cache_file = get_cache_file(sz, hsh)
        if not os.path.exists(cache_file):
            file_path = DB.get_path_from_hash(hsh)
            if file_path is None:
                return {"error": "File not found!"}
            img = Image.open(file_path)
            img.thumbnail((sz, sz))
            dirname = os.path.dirname(cache_file)
            if not os.path.exists(dirname):
                os.makedirs(dirname, exist_ok=True)
            if "exif" in img.info:
                exif = img.info["exif"]
                img.save(cache_file, exif=exif)
            else:
                img.save(cache_file)
        return FileResponse(cache_file, media_type="image/jpeg", filename=cache_file.split("/")[-1])
    file_path = DB.get_path_from_hash(hsh)
    if file_path is not None and os.path.exists(file_path):
        # TODO: fix media type
        return FileResponse(file_path, media_type="image/jpeg", filename=file_path.split("/")[-1])
    return {"error": "File not found!"}


@dataclass
class LocClusterParams:
    tl: LocPoint
    br: LocPoint
    url: UrlParameters
    res: LocPoint
    of: float = 0.5


@app.post("/api/location_clusters")
def location_clusters_endpoint(params: LocClusterParams) -> t.List[LocationCluster]:
    clusters = DB.get_image_clusters(
        params.url,
        params.tl,
        params.br,
        params.res.latitude,
        params.res.longitude,
        params.of,
    )
    return clusters


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
    dir_: str = Query("", alias="dir"),
    oi: t.Optional[int] = None,
) -> HTMLResponse:
    url = UrlParameters(
        tag,
        cls,
        addr,
        datetime.strptime(datefrom, "%Y-%m-%d") if datefrom else None,
        datetime.strptime(dateto, "%Y-%m-%d") if dateto else None,
        page,
        paging,
        dir_,
    )
    del tag
    del cls
    del addr
    del page
    del paging
    del datefrom
    del dateto
    del dir_
    images = []
    aggr = DB.get_aggregate_stats(url)
    if url.page * url.paging >= aggr.total:
        url.page = aggr.total // url.paging
    bounds = None
    if aggr.latitude is not None and aggr.longitude is not None:
        bounds = {
            "lat": aggr.latitude,
            "lon": aggr.longitude,
        }

    for omg in DB.get_matching_images(url):

        max_tag = min(1, max((omg.tags or {}).values(), default=1.0))
        loc = None
        if omg.latitude is not None and omg.longitude is not None:
            loc = {"lat": omg.latitude, "lon": omg.longitude}

        paths = [
            {
                "filename": os.path.basename(file.file),
                "dir": os.path.dirname(file.file),
                "dir_url": url.to_url(directory=os.path.dirname(file.file)),
            }
            for file in DB.files(omg.md5)
        ]

        images.append(
            {
                "hsh": omg.md5,
                "paths": paths,
                "loc": loc,
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
            "bounds": bounds,
            "images": images,
            "total": aggr.total,
            "location_url_json": json.dumps(url.to_filtered_dict(["addr", "page", "paging"])),
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
                "dir": url.directory,
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
