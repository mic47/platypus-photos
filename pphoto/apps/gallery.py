import asyncio
import base64
import json
import typing as t
import os
import sys
import time
import enum
import traceback
from datetime import datetime
from dataclasses import dataclass, fields

from dataclasses_json import DataClassJsonMixin
from PIL import Image, ImageFile

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pphoto.annots.geo import Geolocator
from pphoto.data_model.config import DBFilesConfig, Config
from pphoto.data_model.base import PathWithMd5
from pphoto.db.types_location import LocationCluster, LocPoint
from pphoto.db.types_date import DateCluster
from pphoto.db.connection import PhotosConnection, GalleryConnection, JobsConnection
from pphoto.file_mgmt.remote_control import RefreshJobs, write_serialized_rc_job
from pphoto.utils import assert_never, Lazy
from pphoto.remote_jobs.types import RemoteJobType, ManualLocation, TextAnnotation, ManualAnnotationTask

from pphoto.gallery.db import ImageSqlDB, Image as ImageRow
from pphoto.gallery.image import make_image_address
from pphoto.gallery.url import SearchQuery, GalleryPaging, SortParams, SortBy
from pphoto.gallery.utils import (
    maybe_datetime_to_date,
    maybe_datetime_to_timestamp,
    maybe_datetime_to_day_start,
    maybe_datetime_to_next_day_start,
)
from pphoto.gallery.unicode import maybe_datetime_to_clock

ImageFile.LOAD_TRUNCATED_IMAGES = True


app = FastAPI()
app.mount("/static", StaticFiles(directory="static/"), name="static")
app.mount("/js", StaticFiles(directory="js/"), name="static")
app.mount("/css", StaticFiles(directory="css/"), name="static")
templates = Jinja2Templates(directory="templates")

CONFIG = Config.load("config.yaml")
DB = Lazy(
    lambda: ImageSqlDB(
        PhotosConnection(DBFilesConfig().photos_db, check_same_thread=False),
        GalleryConnection(DBFilesConfig().gallery_db, check_same_thread=False),
        JobsConnection(DBFilesConfig().jobs_db, check_same_thread=False),
    )
)


@app.on_event("startup")
async def on_startup() -> None:
    asyncio.create_task(check_db_connection())


async def check_db_connection() -> None:
    await asyncio.sleep(1)
    while True:
        DB.get().check_unused()
        Lazy.check_ttl()
        await asyncio.sleep(10)


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
            file_path = DB.get().get_path_from_hash(hsh)
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
    file_path = DB.get().get_path_from_hash(hsh)
    if file_path is not None and os.path.exists(file_path):
        # TODO: fix media type
        return FileResponse(file_path, media_type="image/jpeg", filename=file_path.split("/")[-1])
    return {"error": "File not found!"}


@dataclass
class LocClusterParams:
    tl: LocPoint
    br: LocPoint
    url: SearchQuery
    res: LocPoint
    of: float = 0.5


@app.post("/api/location_clusters")
def location_clusters_endpoint(params: LocClusterParams) -> t.List[LocationCluster]:
    clusters = DB.get().get_image_clusters(
        params.url,
        params.tl,
        params.br,
        params.res.latitude,
        params.res.longitude,
        params.of,
    )
    return clusters


@dataclass
class DateClusterParams:
    url: SearchQuery
    buckets: int


@app.post("/api/date_clusters")
def date_clusters_endpoint(params: DateClusterParams) -> t.List[DateCluster]:
    clusters = DB.get().get_date_clusters(
        params.url,
        params.buckets,
    )
    return clusters


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
class MassManualAnnotation(DataClassJsonMixin):
    query: SearchQuery
    location: ManualLocation
    location_override: ManualLocationOverride
    text: TextAnnotation
    text_override: TextAnnotationOverride


@app.post("/api/mass_manual_annotation")
def mass_manual_annotation_endpoint(params: MassManualAnnotation) -> int:
    db = DB.get()
    has_location = None
    has_manual_location = None
    if params.location_override == ManualLocationOverride.NO_LOCATION_NO_MANUAL:
        has_location = False
        has_manual_location = False
    elif params.location_override == ManualLocationOverride.NO_LOCATION_YES_MANUAL:
        has_location = False
        has_manual_location = None
    elif params.location_override == ManualLocationOverride.YES_LOCATION_NO_MANUAL:
        has_location = None
        has_manual_location = False
    elif params.location_override == ManualLocationOverride.YES_LOCATION_YES_MANUAL:
        has_location = None
        has_manual_location = None
    else:
        assert_never(params.location_override)
    location_md5s = set(
        db.get_matching_md5(params.query, has_location=has_location, has_manual_location=has_manual_location)
    )
    has_manual_text = None
    extend = False
    if params.text_override == TextAnnotationOverride.EXTEND_MANUAL:
        has_manual_text = None
        extend = True
    elif params.text_override == TextAnnotationOverride.YES_MANUAL:
        has_manual_text = None
    elif params.text_override == TextAnnotationOverride.NO_MANUAL:
        has_manual_text = False
    else:
        assert_never(params.text_override)
    text_md5s = set(db.get_matching_md5(params.query, has_manual_text=has_manual_text))

    tasks = []
    for md5 in location_md5s.union(text_md5s):
        tasks.append(
            (
                md5,
                ManualAnnotationTask(
                    params.location if md5 in location_md5s else None,
                    params.text if md5 in text_md5s else None,
                    extend,
                )
                .to_json(ensure_ascii=False)
                .encode("utf-8"),
            )
        )
    job_id = db.jobs.submit_job(
        RemoteJobType.MASS_MANUAL_ANNOTATION, params.to_json(ensure_ascii=False).encode("utf-8"), tasks
    )
    db.mark_annotated([t for t, _ in tasks])
    write_serialized_rc_job(CONFIG.import_fifo, RefreshJobs(job_id))
    return job_id


GEOLOCATOR = Geolocator()


@dataclass
class MapSearchRequest:
    query: t.Optional[str] = None


@app.post("/internal/map_search.html", response_class=HTMLResponse)
def map_search_endpoint(request: Request, req: MapSearchRequest) -> HTMLResponse:
    print("ms", req)
    error = ""
    try:
        result = GEOLOCATOR.search(req.query, limit=10) if req.query is not None else []
    # pylint: disable = broad-exception-caught
    except Exception as e:
        traceback.print_exc()
        error = f"{e}\n{traceback.format_exc()}"
    return templates.TemplateResponse(
        request=request,
        name="map_search.html",
        context={"req": req, "result": result, "error": error},
    )


@dataclass
class AnnotationOverlayRequest(DataClassJsonMixin):
    latitude: float
    longitude: float
    query: SearchQuery


@app.post("/internal/submit_annotations_overlay.html", response_class=HTMLResponse)
def submit_annotation_overlay_form_endpoint(request: Request, req: AnnotationOverlayRequest) -> HTMLResponse:
    address = make_image_address(GEOLOCATOR.address(PathWithMd5("", ""), req.latitude, req.longitude).p, None)
    aggr = DB.get().get_aggregate_stats(req.query)
    top_tags = sorted(aggr.tag.items(), key=lambda x: -x[1])
    top_cls = sorted(aggr.classification.items(), key=lambda x: -x[1])
    top_addr = sorted(aggr.address.items(), key=lambda x: -x[1])

    directories = sorted(DB.get().get_matching_directories(req.query), key=lambda x: x.directory)
    omgs, _ = DB.get().get_matching_images(req.query, SortParams(sort_by=SortBy.RANDOM), GalleryPaging())
    images = [image_template_params(omg) for omg in omgs]
    return templates.TemplateResponse(
        request=request,
        name="submit_annotations_overlay.html",
        context={
            "total": aggr.total,
            "top": {
                "tag": top_tags[:15],
                "cls": top_cls[:5],
                "addr": top_addr[:15],
                "show_links": False,
            },
            "address": address,
            "req": req,
            "query_json": json.dumps(
                {k: v for k, v in req.query.to_dict(encode_json=True).items() if v}, indent=2
            ),
            "query_json_base64": base64.b64encode(
                req.query.to_json(ensure_ascii=True).encode("utf-8")
            ).decode("utf-8"),
            "directories": directories,
            "images": images,
        },
    )


@dataclass
class LocationInfoRequest:
    latitude: float
    longitude: float


@app.post("/internal/fetch_location_info.html", response_class=HTMLResponse)
def fetch_location_info_endpoint(request: Request, location: LocationInfoRequest) -> HTMLResponse:
    address = make_image_address(
        GEOLOCATOR.address(PathWithMd5("", ""), location.latitude, location.longitude).p, None
    )
    return templates.TemplateResponse(
        request=request,
        name="fetch_location_info.html",
        context={"address": address, "req": location},
    )


@app.post("/internal/directories.html", response_class=HTMLResponse)
def directories_endpoint(request: Request, url: SearchQuery) -> HTMLResponse:
    directories = sorted(DB.get().get_matching_directories(url), key=lambda x: x.directory)
    dirs = []
    for directory in directories:
        parts = directory.directory.split("/")
        prefixes = []
        prefix = ""
        for part in parts:
            if part:
                prefix = f"{prefix}/{part}"
                prefixes.append((part, prefix))
            else:
                prefix = ""
                prefixes.append((part, ""))
        dirs.append((prefixes, directory))
    return templates.TemplateResponse(
        request=request,
        name="directories.html",
        context={
            "dirs": sorted(dirs, key=lambda x: [x[1].total_images, x[0]], reverse=True),
        },
    )


@dataclass
class GalleryRequest:
    query: SearchQuery
    paging: GalleryPaging


def image_template_params(omg: ImageRow) -> t.Dict[str, t.Any]:

    max_tag = min(1, max((omg.tags or {}).values(), default=1.0))
    loc = None
    if omg.latitude is not None and omg.longitude is not None:
        loc = {"lat": omg.latitude, "lon": omg.longitude}

    paths = [
        {
            "filename": os.path.basename(file.file),
            "dir": os.path.dirname(file.file),
        }
        for file in DB.get().files(omg.md5)
    ]
    return {
        "hsh": omg.md5,
        "paths": paths,
        "loc": loc,
        "classifications": omg.classifications or "",
        "tags": [
            (tg, classify_tag(x / max_tag)) for tg, x in sorted((omg.tags or {}).items(), key=lambda x: -x[1])
        ],
        "addrs": [a for a in [omg.address.name, omg.address.country] if a],
        "date": maybe_datetime_to_date(omg.date),
        "date_timestamp_start": maybe_datetime_to_day_start(omg.date),
        "date_timestamp_end": maybe_datetime_to_next_day_start(omg.date),
        "timeicon": maybe_datetime_to_clock(omg.date),
        "timestamp": maybe_datetime_to_timestamp(omg.date),
        "being_annotated": omg.being_annotated,
        "raw_data": [
            {"k": k, "v": json.dumps(v, ensure_ascii=True)} for k, v in omg.to_dict(encode_json=True).items()
        ],
    }


@app.post("/internal/gallery.html", response_class=HTMLResponse)
async def gallery_div(request: Request, params: GalleryRequest, oi: t.Optional[int] = None) -> HTMLResponse:
    images = []
    omgs, has_next_page = DB.get().get_matching_images(params.query, SortParams(), params.paging)
    for omg in omgs:
        images.append(image_template_params(omg))

    return templates.TemplateResponse(
        request=request,
        name="gallery.html",
        context={
            "oi": oi,
            "images": images,
            "has_next_page": has_next_page,
            "input": {
                "page": params.paging.page,
            },
        },
    )


@app.post("/internal/aggregate.html", response_class=HTMLResponse)
def aggregate_endpoint(request: Request, url: SearchQuery) -> HTMLResponse:
    aggr = DB.get().get_aggregate_stats(url)
    top_tags = sorted(aggr.tag.items(), key=lambda x: -x[1])
    top_cls = sorted(aggr.classification.items(), key=lambda x: -x[1])
    top_addr = sorted(aggr.address.items(), key=lambda x: -x[1])
    return templates.TemplateResponse(
        request=request,
        name="aggregate.html",
        context={
            "total": aggr.total,
            "top": {
                "tag": top_tags[:15],
                "cls": top_cls[:5],
                "addr": top_addr[:15],
                "show_links": True,
            },
        },
    )


@app.post("/internal/input.html", response_class=HTMLResponse)
def input_request(request: Request, url: SearchQuery) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="input.html",
        context={
            "input": {
                "tag": url.tag,
                "cls": url.cls,
                "addr": url.addr,
                "directory": url.directory,
                "tsfrom": url.tsfrom or "",
                "tsfrom_pretty": (
                    datetime.fromtimestamp(url.tsfrom).strftime("%a %Y-%m-%d %H:%M:%S")
                    if url.tsfrom is not None
                    else "_" * 23
                ),
                "tsto": url.tsto or "",
                "tsto_pretty": (
                    datetime.fromtimestamp(url.tsto).strftime("%a %Y-%m-%d %H:%M:%S")
                    if url.tsto is not None
                    else "_" * 23
                ),
            },
        },
    )


@app.get("/index.html", response_class=HTMLResponse)
@app.get("/", response_class=HTMLResponse)
async def index_page(
    request: Request,
    tag: str = "",
    cls: str = "",
    addr: str = "",
    page: int = 0,
    paging: int = 100,
    tsfrom: t.Optional[float] = None,
    tsto: t.Optional[float] = None,
    directory: str = "",
    oi: t.Optional[int] = None,
) -> HTMLResponse:
    gallery_paging = GalleryPaging(page, paging)
    url = SearchQuery(
        tag,
        cls,
        addr,
        directory,
        tsfrom,
        tsto,
    )
    del tag
    del cls
    del addr
    del page
    del paging
    del directory
    del tsfrom
    del tsto
    aggr = DB.get().get_aggregate_stats(url)
    if gallery_paging.page * gallery_paging.paging >= aggr.total:
        gallery_paging.page = aggr.total // gallery_paging.paging
    bounds = None
    if aggr.latitude is not None and aggr.longitude is not None:
        bounds = {
            "lat": aggr.latitude,
            "lon": aggr.longitude,
        }

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "oi": oi,
            "bounds": bounds,
            "url_parameters_fields": json.dumps([x.name for x in fields(SearchQuery)]),
            "paging_fields": json.dumps([x.name for x in fields(GalleryPaging)]),
        },
    )


def classify_tag(value: float) -> str:
    if value >= 0.5:
        return ""
    if value >= 0.2:
        return "🤷"
    return "🗑️"
