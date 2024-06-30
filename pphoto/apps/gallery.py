from __future__ import annotations

import asyncio
import base64
import json
import math
import typing as t
import os
import sys
import time
import enum
import traceback
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from dataclasses_json import DataClassJsonMixin
from geopy.distance import distance
from PIL import Image, ImageFile

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pphoto.annots.geo import Geolocator
from pphoto.communication.client import get_system_status, refresh_jobs, SystemStatus
from pphoto.data_model.config import DBFilesConfig
from pphoto.data_model.base import PathWithMd5
from pphoto.db.types_location import LocationCluster, LocPoint, LocationBounds
from pphoto.db.types_date import DateCluster, DateClusterGroupBy
from pphoto.db.types_image import ImageAddress
from pphoto.db.connection import PhotosConnection, GalleryConnection, JobsConnection
from pphoto.utils import assert_never, Lazy
from pphoto.remote_jobs.types import (
    RemoteJobType,
    ManualLocation,
    TextAnnotation,
    ManualAnnotationTask,
    ManualDate,
)

from pphoto.gallery.db import ImageSqlDB, Image as ImageRow
from pphoto.gallery.image import make_image_address
from pphoto.gallery.url import SearchQuery, GalleryPaging, SortParams, SortBy, SortOrder
from pphoto.gallery.utils import (
    format_diff_date,
    format_seconds_to_duration,
    maybe_datetime_to_date,
    maybe_datetime_to_time,
    maybe_datetime_to_timestamp,
    maybe_datetime_to_day_start,
    maybe_datetime_to_next_day_start,
)
from pphoto.gallery.unicode import maybe_datetime_to_clock, append_flag, replace_with_flag, flag

ImageFile.LOAD_TRUNCATED_IMAGES = True


def custom_generate_unique_id(route: APIRoute) -> str:
    method = "_".join(sorted(route.methods))
    if route.tags:
        return f"{route.tags[0]}-{route.name}-{method}"
    return f"{route.name}-{method}"


app = FastAPI(generate_unique_id_function=custom_generate_unique_id)
app.mount("/static", StaticFiles(directory="static/"), name="static")
app.mount("/css", StaticFiles(directory="css/"), name="static")
templates = Jinja2Templates(directory="templates")


def timestamp_to_pretty_datetime(value: float) -> str:
    """
    custom max calculation logic
    """
    return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M:%S")


templates.env.filters["timestamp_to_pretty_datetime"] = timestamp_to_pretty_datetime
templates.env.filters["append_flag"] = append_flag
templates.env.filters["replace_with_flag"] = replace_with_flag
templates.env.filters["dataclass_to_json_pretty"] = lambda x: x.to_json(indent=2, ensure_ascii=False)
templates.env.filters["format_seconds_to_duration"] = lambda x: format_seconds_to_duration(float(x))

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
    jobs = DB.get().jobs.get_jobs(skip_finished=False, since=datetime.now() - timedelta(days=1))
    for job in jobs:
        if job.type_ == RemoteJobType.MASS_MANUAL_ANNOTATION:
            try:
                og_req = mass_manual_annotation_from_json(job.original_request)
                # pylint: disable-next = consider-using-in
                if og_req.location.t == "InterpolatedLocation" or og_req.location.t == "FixedLocation":
                    point = LocPoint(og_req.location.location.latitude, og_req.location.location.longitude)
                    clusters.append(
                        LocationCluster(
                            job.example_path_md5 or "missing",
                            og_req.text.text.description,
                            job.total,
                            og_req.location.location.address_name,
                            og_req.location.location.address_country,
                            og_req.query.tsfrom,
                            og_req.query.tsto,
                            point,
                            point,
                            point,
                        )
                    )
                elif og_req.location.t == "NoLocation":
                    pass
                else:
                    assert_never(og_req.location.t)
            # pylint: disable-next = broad-exception-caught
            except Exception:
                continue
        else:
            assert_never(job.type_)
    return clusters


@app.post("/api/bounds")
def location_bounds_endpoint(params: SearchQuery) -> t.Optional[LocationBounds]:
    bounds = DB.get().get_location_bounds(params)
    if bounds is None:
        return None
    return bounds


@dataclass
class DateClusterParams:
    url: SearchQuery
    group_by: t.List[DateClusterGroupBy]
    buckets: int


@app.post("/api/date_clusters")
def date_clusters_endpoint(params: DateClusterParams) -> t.List[DateCluster]:
    clusters = DB.get().get_date_clusters(
        params.url,
        params.group_by,
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
class LocationQueryFixedLocation(DataClassJsonMixin):
    t: t.Literal["FixedLocation"]
    location: ManualLocation
    override: ManualLocationOverride


@dataclass
class MassManualAnnotationDeprecated(DataClassJsonMixin):
    query: SearchQuery
    location: ManualLocation
    location_override: ManualLocationOverride
    text: TextAnnotation
    text_override: TextAnnotationOverride


@dataclass
class TextQueryFixedText(DataClassJsonMixin):
    t: t.Literal["FixedText"]
    text: TextAnnotation
    override: TextAnnotationOverride
    loc_only: bool


@dataclass
class AnnotationOverlayInterpolateLocation(DataClassJsonMixin):
    t: t.Literal["InterpolatedLocation"]
    location: ManualLocation  # Actually not manual location, it's just sample. But structurally same type


@dataclass
class AnnotationOverlayNoLocation(DataClassJsonMixin):
    t: t.Literal["NoLocation"]


@dataclass
class TransDate(DataClassJsonMixin):
    t: t.Literal["TransDate"]
    adjust_dates: bool


LocationTypes = (
    LocationQueryFixedLocation | AnnotationOverlayInterpolateLocation | AnnotationOverlayNoLocation
)
TextTypes = TextQueryFixedText
DateTypes = TransDate


@dataclass
class MassLocationAndTextAnnotation(DataClassJsonMixin):
    t: t.Literal["MassLocAndTxt"]
    query: SearchQuery
    location: LocationTypes
    text: TextTypes
    date: DateTypes


MassManualAnnotation = MassLocationAndTextAnnotation


def mass_manual_annotation_from_json(j: bytes) -> MassLocationAndTextAnnotation:
    d = json.loads(j)
    type_ = d.get("t")
    if type_ is None:
        return mass_manual_annotation_migrate(MassManualAnnotationDeprecated.from_dict(d))
    if type_ == "MassLocAndTxt":
        return MassLocationAndTextAnnotation.from_dict(d)
    raise NotImplementedError


def mass_manual_annotation_migrate(params: MassManualAnnotationDeprecated) -> MassLocationAndTextAnnotation:
    return MassLocationAndTextAnnotation(
        "MassLocAndTxt",
        params.query,
        LocationQueryFixedLocation(
            "FixedLocation",
            params.location,
            params.location_override,
        ),
        TextQueryFixedText(
            "FixedText",
            params.text,
            params.text_override,
            False,
        ),
        TransDate(
            "TransDate",
            False,
        ),
    )


def location_tasks_recipes(
    location: LocationTypes,
    query: SearchQuery,
    db: ImageSqlDB,
    all_images: Lazy[t.Tuple[t.List[ImageRow], bool]],
) -> t.Dict[str, ManualLocation]:
    location_tasks_recipe = {}
    if location.t == "FixedLocation":
        has_location = None
        has_manual_location = None
        if location.override == ManualLocationOverride.NO_LOCATION_NO_MANUAL:
            has_location = False
            has_manual_location = False
        elif location.override == ManualLocationOverride.NO_LOCATION_YES_MANUAL:
            has_location = False
            has_manual_location = None
        elif location.override == ManualLocationOverride.YES_LOCATION_NO_MANUAL:
            has_location = None
            has_manual_location = False
        elif location.override == ManualLocationOverride.YES_LOCATION_YES_MANUAL:
            has_location = None
            has_manual_location = None
        else:
            assert_never(location.override)
        location_tasks_recipe = {
            md5: location.location
            for md5 in db.get_matching_md5(
                query, has_location=has_location, has_manual_location=has_manual_location
            )
        }
    elif location.t == "InterpolatedLocation":
        location_tasks_recipe = {}
        omgs, _ = all_images.get()
        fwdbwd = forward_backward(omgs, DateWithLoc.from_image)
        for index, omg in enumerate(omgs):
            predicted_location = predict_location(omg, fwdbwd[index][0], fwdbwd[index][1])
            if predicted_location is not None and omg.latitude is None and omg.longitude is None:
                location_tasks_recipe[omg.md5] = ManualLocation(
                    predicted_location.loc.latitude,
                    predicted_location.loc.longitude,
                    # TODO: Should we allow this?
                    None,
                    None,
                )
    elif location.t == "NoLocation":
        location_tasks_recipe = {}
    else:
        assert_never(location.t)
    return location_tasks_recipe


def date_tasks_recipes(
    date: DateTypes,
    all_images: Lazy[t.Tuple[t.List[ImageRow], bool]],
) -> t.Dict[str, ManualDate]:
    transformed_date_recipe = {}
    if date.t == "TransDate":
        if date.adjust_dates:
            omgs, _ = all_images.get()
            for omg in omgs:
                if omg.date_transformed:
                    transformed_date_recipe[omg.md5] = ManualDate(omg.date)
    else:
        assert_never(date.t)
    return transformed_date_recipe


@app.post("/api/mass_manual_annotation")
async def mass_manual_annotation_endpoint(params: MassManualAnnotation) -> int:
    db = DB.get()

    all_images = Lazy(
        lambda: DB.get().get_matching_images(
            params.query, SortParams(sort_by=SortBy.TIMESTAMP, order=SortOrder.ASC), GalleryPaging(0, 1000000)
        )
    )

    transformed_date_recipe = date_tasks_recipes(params.date, all_images)

    location_tasks_recipe = location_tasks_recipes(params.location, params.query, db, all_images)

    has_manual_text = None
    extend = False
    if params.text.override == TextAnnotationOverride.EXTEND_MANUAL:
        has_manual_text = None
        extend = True
    elif params.text.override == TextAnnotationOverride.YES_MANUAL:
        has_manual_text = None
    elif params.text.override == TextAnnotationOverride.NO_MANUAL:
        has_manual_text = False
    else:
        assert_never(params.text.override)
    text_md5s = set(db.get_matching_md5(params.query, has_manual_text=has_manual_text))
    if params.text.loc_only:
        text_md5s = text_md5s.intersection(location_tasks_recipe.keys())

    tasks = []
    for md5 in text_md5s.union(location_tasks_recipe.keys()).union(transformed_date_recipe.keys()):
        tasks.append(
            (
                md5,
                ManualAnnotationTask(
                    location_tasks_recipe.get(md5),
                    params.text.text if md5 in text_md5s else None,
                    extend,
                    transformed_date_recipe.get(md5),
                )
                .to_json(ensure_ascii=False)
                .encode("utf-8"),
            )
        )
    job_id = db.jobs.submit_job(
        RemoteJobType.MASS_MANUAL_ANNOTATION, params.to_json(ensure_ascii=False).encode("utf-8"), tasks
    )
    db.mark_annotated([t for t, _ in tasks])
    await refresh_jobs(job_id)
    return job_id


GEOLOCATOR = Geolocator()


@dataclass
class MapSearchRequest:
    query: t.Optional[str] = None
    checkboxes: t.Dict[str, bool] = field(default_factory=dict)


@app.post("/internal/map_search.html", response_class=HTMLResponse)
def map_search_endpoint(request: Request, req: MapSearchRequest) -> HTMLResponse:
    error = ""
    try:
        result = GEOLOCATOR.search(req.query, limit=10) if req.query is not None else []
    # pylint: disable-next = broad-exception-caught
    except Exception as e:
        traceback.print_exc()
        error = f"{e}\n{traceback.format_exc()}"
    return templates.TemplateResponse(
        request=request,
        name="map_search.html",
        context={"req": req, "result": result, "error": error},
    )


@dataclass
class JobProgressState(DataClassJsonMixin):
    ts: float
    t_total: int
    t_finished: int
    j_total: int
    j_finished: int
    j_waiting: int

    def diff(self, earlier: JobProgressState) -> JobProgressState:
        return JobProgressState(
            self.ts - earlier.ts,
            self.t_total - earlier.t_total,
            self.t_finished - earlier.t_finished,
            self.j_total - earlier.j_total,
            self.j_finished - earlier.j_finished,
            self.j_waiting - earlier.j_waiting,
        )

    def progressed(self, earlier: JobProgressState) -> bool:
        return (
            self.t_total != earlier.t_total
            or self.t_finished != earlier.t_finished
            or self.j_total != earlier.j_total
            or self.j_finished != earlier.j_finished
            or self.j_waiting != earlier.j_waiting
        )


@dataclass
class JobProgressRequest:
    update_state_fn: str
    job_list_fn: str
    state: t.Optional[JobProgressState] = None


@app.post("/internal/job_progress.html", response_class=HTMLResponse)
def job_progress_endpoint(request: Request, req: JobProgressRequest) -> HTMLResponse:
    jobs = DB.get().jobs.get_jobs(skip_finished=False)
    state = JobProgressState(datetime.now().timestamp(), 0, 0, 0, 0, 0)
    for job in jobs:
        state.t_total += job.total
        state.t_finished += job.finished_tasks
        state.j_total += 1
        state.j_finished += int(job.total == job.finished_tasks)
        state.j_waiting += int(job.finished_tasks == 0)
    if req.state is not None and state.progressed(req.state):
        diff = state.diff(req.state)
        if state.t_total == state.t_finished or diff.ts < 1 or diff.t_finished == 0:
            eta = None
        else:
            eta = str(timedelta(seconds=int((state.t_total - state.t_finished) * diff.ts / diff.t_finished)))
    else:
        diff = None
        eta = None

    return templates.TemplateResponse(
        request=request,
        name="job_progress.html",
        context={
            "state": state,
            "state_base64": base64.b64encode(state.to_json().encode("utf-8")).decode("utf-8"),
            "diff": diff,
            "update_state_fn": req.update_state_fn,
            "job_list_fn": req.job_list_fn,
            "eta": eta,
        },
    )


@dataclass
class JobListRequest:
    pass


@app.post("/internal/job_list.html", response_class=HTMLResponse)
def job_list_endpoint(request: Request, _req: JobListRequest) -> HTMLResponse:
    jobs = []
    for job in sorted(DB.get().jobs.get_jobs(skip_finished=False), key=lambda x: x.created, reverse=True):
        total = f"{job.finished_tasks}/{job.total}"
        if job.total == job.finished_tasks:
            icon = "✅"
            total = str(job.total)
        elif job.finished_tasks == 0:
            icon = "🚏"
        else:
            icon = "🏗️"
        type_ = ["🗺️"]
        replacements = []
        query = ""
        latitude = None
        longitude = None
        if job.type_ == RemoteJobType.MASS_MANUAL_ANNOTATION:
            try:
                og_req = mass_manual_annotation_from_json(job.original_request)
                if og_req.text.text.description:
                    type_.append("📝")
                    replacements.append(f"📝{og_req.text.text.description}")
                if og_req.text.text.tags:
                    type_.append("🏷️")
                    replacements.append(f"🏷️{og_req.text.text.tags}")
                # pylint: disable-next = consider-using-in
                if og_req.location.t == "InterpolatedLocation" or og_req.location.t == "FixedLocation":
                    if og_req.location.location.address_name:
                        type_.append("📛")
                        replacements.append(f"📛{og_req.location.location.address_name}")
                    if og_req.location.location.address_country:
                        type_.append(flag(og_req.location.location.address_country) or "🎌")
                        replacements.append(
                            flag(og_req.location.location.address_country)
                            or og_req.location.location.address_country
                        )
                    latitude = og_req.location.location.latitude
                    longitude = og_req.location.location.longitude
                elif og_req.location.t == "NoLocation":
                    pass
                else:
                    assert_never(og_req.location.t)
                query = og_req.to_json(ensure_ascii=False, indent=2)

            # pylint: disable-next = broad-exception-caught
            except Exception as e:
                replacements.append(str(e))
        else:
            assert_never(job.type_)
        repls = ", ".join(replacements)
        job_dict = job.to_dict(encode_json=True)
        if "original_request" in job_dict:
            job_dict.pop("original_request")
        jobs.append(
            {
                "icon": icon,
                "total": total,
                "id_": job.id_,
                "type_": "".join(type_),
                "repls": repls,
                "time": (job.last_update or job.created).timestamp(),
                "latitude": latitude,
                "longitude": longitude,
                "query_json": query,
                "job_json": json.dumps(job_dict, ensure_ascii=False, indent=2),
                "example_path_md5": job.example_path_md5,
            }
        )
    return templates.TemplateResponse(
        request=request,
        name="job_list.html",
        context={"jobs": jobs},
    )


@app.get("/api/system_status")
async def system_status(_request: Request) -> SystemStatus:
    return await get_system_status()


@dataclass
class AnnotationOverlayFixedLocation(DataClassJsonMixin):
    t: t.Literal["FixedLocation"]
    latitude: float
    longitude: float


@dataclass
class AnnotationOverlayRequest(DataClassJsonMixin):
    request: (
        AnnotationOverlayFixedLocation | AnnotationOverlayInterpolateLocation | AnnotationOverlayNoLocation
    )
    query: SearchQuery


@app.post("/internal/submit_annotations_overlay.html", response_class=HTMLResponse)
def submit_annotation_overlay_form_endpoint(request: Request, req: AnnotationOverlayRequest) -> HTMLResponse:
    address = None
    if req.request.t == "FixedLocation":
        address = make_image_address(
            GEOLOCATOR.address(PathWithMd5("", ""), req.request.latitude, req.request.longitude).p,
            None,
        )
    elif req.request.t == "InterpolatedLocation":
        # there is nothing to do.
        address = ImageAddress(req.request.location.address_country, req.request.location.address_name, None)
    elif req.request.t == "NoLocation":
        # There is no location, so nothing to do
        pass
    else:
        assert_never(req.request.t)
    aggr = DB.get().get_aggregate_stats(req.query)
    top_tags = sorted(aggr.tag.items(), key=lambda x: -x[1])
    top_cls = sorted(aggr.classification.items(), key=lambda x: -x[1])
    top_addr = sorted(aggr.address.items(), key=lambda x: -x[1])
    top_cameras = sorted(((k or "unknown", v) for k, v in aggr.cameras.items()), key=lambda x: -x[1])

    directories = sorted(DB.get().get_matching_directories(req.query), key=lambda x: x.directory)
    omgs, _ = DB.get().get_matching_images(req.query, SortParams(sort_by=SortBy.RANDOM), GalleryPaging())
    images = [image_template_params(omg) for omg in omgs]
    return templates.TemplateResponse(
        request=request,
        name="submit_annotations_overlay.html",
        context={
            "total": aggr.total,
            "request_type": req.request.t,
            "top": {
                "tag": top_tags[:15],
                "cls": top_cls[:5],
                "addr": top_addr[:15],
                "cameras": [
                    (k, v)
                    for k, v in (
                        top_cameras[:5]
                        + [("other", sum([x for _, x in top_cameras[5:]], 0))]
                        + [("distinct", len(set(x for x, _ in top_cameras[5:])))]
                    )
                    if v
                ],
                "show_links": False,
            },
            "address": address,
            "req": req,
            "query_json": json.dumps(
                {k: v for k, v in req.query.to_dict(encode_json=True).items() if v}, indent=2
            ),
            "query_json_base64": jtob64(req.query),
            "directories": directories,
            "images": images,
        },
    )


def jtob64(data: DataClassJsonMixin) -> str:
    return base64.b64encode(data.to_json(ensure_ascii=True).encode("utf-8")).decode("utf-8")


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
            "dirs": sorted(dirs, key=lambda x: [x[1].since or 0, x[1].total_images, x[0]], reverse=True),
        },
    )


@dataclass
class GalleryRequest:
    query: SearchQuery
    paging: GalleryPaging
    sort: SortParams
    checkboxes: t.Dict[str, bool]


def image_template_params(
    omg: ImageRow,
    prev_date: t.Optional[datetime] = None,
) -> t.Dict[str, t.Any]:

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
    diff_date = format_diff_date(omg.date, prev_date)
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
        "time": maybe_datetime_to_time(omg.date),
        "date_timestamp_start": maybe_datetime_to_day_start(omg.date),
        "date_timestamp_end": maybe_datetime_to_next_day_start(omg.date),
        "timeicon": maybe_datetime_to_clock(omg.date),
        "timestamp": maybe_datetime_to_timestamp(omg.date),
        "diff_date": diff_date,
        "being_annotated": omg.being_annotated,
        "camera": omg.camera,
        "software": omg.software,
        "raw_data": [
            {"k": k, "v": json.dumps(v, ensure_ascii=True)} for k, v in omg.to_dict(encode_json=True).items()
        ],
    }


@dataclass
class DateWithLoc:
    loc: LocPoint
    date: datetime

    @staticmethod
    def from_image(omg: ImageRow) -> t.Optional[DateWithLoc]:
        if omg.latitude is not None and omg.longitude is not None and omg.date is not None:
            return DateWithLoc(LocPoint(omg.latitude, omg.longitude), omg.date)
        return None

    def distance(self, other: DateWithLoc) -> float:
        return t.cast(
            float,
            distance((self.loc.latitude, self.loc.longitude), (other.loc.latitude, other.loc.longitude)).m,
        )

    def timedist(self, other: datetime) -> float:
        return abs((self.date - other).total_seconds())


@app.post("/internal/gallery.html", response_class=HTMLResponse)
async def gallery_div(request: Request, params: GalleryRequest, oi: t.Optional[int] = None) -> HTMLResponse:
    images = []
    omgs, has_next_page = DB.get().get_matching_images(params.query, params.sort, params.paging)
    fwdbwd = forward_backward(omgs, DateWithLoc.from_image)

    prev_date = None
    some_location = None
    for index, omg in enumerate(omgs):
        if omg.latitude is not None and omg.longitude is not None:
            some_location = ManualLocation(
                omg.latitude,
                omg.longitude,
                omg.address.name,
                omg.address.country,
            )
        predicted_location = predict_location(omg, fwdbwd[index][0], fwdbwd[index][1])
        estimated_loc = predict_location_to_str(predicted_location)
        estimated_loc_suspicious = suspicious(predicted_location)
        images.append(
            {
                **image_template_params(omg, prev_date),
                "estimated_loc": estimated_loc,
                "estimated_loc_suspicious": estimated_loc_suspicious,
                "estimated_loc_onesided": predicted_location is not None
                and (predicted_location.earlier is None or predicted_location.later is None),
                "predicted_loc": predicted_location,
            }
        )
        prev_date = omg.date

    return templates.TemplateResponse(
        request=request,
        name="gallery.html",
        context={
            "oi": oi,
            "checkboxes": params.checkboxes,
            "location_encoded_base64": (
                base64.b64encode(some_location.to_json().encode("utf-8")).decode("utf-8")
                if some_location is not None
                else None
            ),
            "images": images,
            "has_next_page": has_next_page,
            "ascending": params.sort.order == SortOrder.ASC,
            "input": {
                "page": params.paging.page,
            },
        },
    )


T = t.TypeVar("T")
R = t.TypeVar("R")


def forward_backward(
    seq: t.Sequence[T], fun: t.Callable[[T], t.Optional[R]]
) -> t.List[t.Tuple[t.Optional[R], t.Optional[R]]]:
    last = None
    backward: t.List[t.Optional[R]] = []
    for omg in reversed(seq):
        backward.append(last)
        last = fun(omg) or last
    last = None
    forward: t.List[t.Tuple[t.Optional[R], t.Optional[R]]] = []
    for index, omg in enumerate(seq):
        forward.append((last, backward[-(index + 1)]))
        last = fun(omg) or last
    return forward


@dataclass
class ReferenceStats(DataClassJsonMixin):
    distance_m: float
    seconds: float


@dataclass
class PredictedLocation(DataClassJsonMixin):
    loc: LocPoint
    earlier: t.Optional[ReferenceStats]
    later: t.Optional[ReferenceStats]


def distance_m(p1: LocPoint, p2: LocPoint) -> float:
    return t.cast(float, distance((p1.latitude, p1.longitude), (p2.latitude, p2.longitude)).m)


def suspicious(loc: t.Optional[PredictedLocation]) -> bool:
    if loc is None:
        return False
    if loc.earlier is not None:
        if loc.earlier.distance_m > 1000 or loc.earlier.seconds > 3600:
            return True
    if loc.later is not None:
        if loc.later.distance_m > 1000 or loc.later.seconds > 3600:
            return True
    return False


def predict_location(
    omg: ImageRow,
    prev_loc: t.Optional[DateWithLoc] = None,
    next_loc: t.Optional[DateWithLoc] = None,
) -> t.Optional[PredictedLocation]:
    if omg.date is None:
        return None
    if omg.latitude is not None and omg.longitude is not None:
        return None
    if prev_loc is not None and next_loc is not None:
        prev_d = prev_loc.timedist(omg.date)
        next_d = next_loc.timedist(omg.date)
        t_d = prev_d + next_d
        loc_point = prev_loc.loc + (next_loc.loc - prev_loc.loc).scale(prev_d / t_d)
        return PredictedLocation(
            loc_point,
            ReferenceStats(distance_m(prev_loc.loc, loc_point), prev_d),
            ReferenceStats(distance_m(loc_point, next_loc.loc), next_d),
        )
    if prev_loc is not None:
        return PredictedLocation(
            prev_loc.loc,
            ReferenceStats(0.0, prev_loc.timedist(omg.date)),
            None,
        )
    if next_loc is not None:
        return PredictedLocation(
            next_loc.loc,
            None,
            ReferenceStats(0.0, next_loc.timedist(omg.date)),
        )
    return None


def predict_location_to_str(
    predicted: t.Optional[PredictedLocation],
) -> t.Optional[str]:
    if predicted is None:
        return None
    parts = []
    if predicted.earlier:
        speed_str = ""
        if predicted.earlier.seconds > 0.1:
            speed = predicted.earlier.distance_m / predicted.earlier.seconds * 1000 / 3600
            speed_str = f", {speed:.1f}km/h"
        parts.append(
            f"e: {predicted.earlier.distance_m:.0f}m, {format_seconds_to_duration(predicted.earlier.seconds)}{speed_str}"
        )
    if predicted.later:
        speed_str = ""
        if predicted.later.seconds > 0.1:
            speed = predicted.later.distance_m / predicted.later.seconds * 1000 / 3600
            speed_str = f", {speed:.1f}km/h"
        parts.append(
            f"l: {predicted.later.distance_m:.0f}m, {format_seconds_to_duration(predicted.later.seconds)}{speed_str}"
        )
    return ", ".join(parts)


@dataclass
class AggregateQuery:
    query: SearchQuery
    paging: GalleryPaging


@app.post("/internal/aggregate.html", response_class=HTMLResponse)
def aggregate_endpoint(request: Request, param: AggregateQuery) -> HTMLResponse:
    paging = param.paging.paging
    aggr = DB.get().get_aggregate_stats(param.query)
    top_tags = sorted(aggr.tag.items(), key=lambda x: -x[1])
    top_cls = sorted(aggr.classification.items(), key=lambda x: -x[1])
    top_addr = sorted(aggr.address.items(), key=lambda x: -x[1])
    top_cameras = sorted(((k or "unknown", v) for k, v in aggr.cameras.items()), key=lambda x: -x[1])
    return templates.TemplateResponse(
        request=request,
        name="aggregate.html",
        context={
            "total": aggr.total,
            "num_pages": math.ceil(aggr.total / paging),
            "top": {
                "tag": top_tags[:15],
                "cls": top_cls[:5],
                "addr": top_addr[:15],
                "cameras": [
                    (k, v)
                    for k, v in (
                        top_cameras[:5]
                        + [("other", sum([x for _, x in top_cameras[5:]], 0))]
                        + [("distinct", len(set(x for x, _ in top_cameras[5:])))]
                    )
                    if v
                ],
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
                "skip_with_location": url.skip_with_location,
                "skip_being_annotated": url.skip_being_annotated,
                "directory": url.directory,
                "camera": url.camera,
                "timestamp_trans": url.timestamp_trans or "",
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


@app.get("/index.html")
@app.get("/")
async def read_index() -> FileResponse:
    return FileResponse("static/index.html")


def classify_tag(value: float) -> str:
    if value >= 0.5:
        return ""
    if value >= 0.2:
        return "🤷"
    return "🗑️"
