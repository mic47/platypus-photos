from __future__ import annotations

import asyncio
import itertools
import json
import typing as t
import os
import sys
import time
import enum
import traceback
from datetime import datetime, timedelta
from dataclasses import dataclass

from dataclasses_json import DataClassJsonMixin
from geopy.distance import distance
from PIL import Image, ImageFile

from fastapi import FastAPI, Request, Response, Query, Path as PathParam
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles

from pphoto.annots.geo import Geolocator
from pphoto.communication.client import get_system_status, refresh_jobs, SystemStatus
from pphoto.data_model.config import DBFilesConfig
from pphoto.data_model.base import PathWithMd5
from pphoto.data_model.face import Position
from pphoto.data_model.manual import ManualIdentity, IdentitySkipReason
from pphoto.db.types_location import LocationCluster, LocPoint, LocationBounds
from pphoto.db.types_date import DateCluster, DateClusterGroupBy
from pphoto.db.types_directory import DirectoryStats
from pphoto.db.types_image import ImageAddress, ImageAggregation
from pphoto.db.types_identity import IdentityRowPayload
from pphoto.db.connection import PhotosConnection, GalleryConnection, JobsConnection
from pphoto.utils import assert_never, Lazy
from pphoto.remote_jobs.types import (
    RemoteJob,
    RemoteJobType,
    ManualLocation,
    TextAnnotation,
    ManualAnnotationTask,
    ManualDate,
)

from pphoto.gallery.db import ImageSqlDB, Image as ImageRow
from pphoto.gallery.image import make_image_address
from pphoto.gallery.url import SearchQuery, GalleryPaging, SortParams, SortBy, SortOrder
from pphoto.gallery.unicode import flag
from pphoto.file_mgmt.archive import non_repeating_dirs, tar_stream
from pphoto.utils.files import pathify, supported_media_class, SupportedMediaClass
from pphoto.utils.video import get_video_frame

ImageFile.LOAD_TRUNCATED_IMAGES = True


def custom_generate_unique_id(route: APIRoute) -> str:
    method = "_".join(sorted(route.methods))
    if route.tags:
        return f"{route.tags[0]}-{route.name}-{method}"
    return f"{route.name}-{method}"


app = FastAPI(generate_unique_id_function=custom_generate_unique_id)
app.mount("/static", StaticFiles(directory="static/"), name="static")
app.mount("/css", StaticFiles(directory="css/"), name="static")


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


def get_cache_file(
    size: int | str, hsh: str, extension: str, position: t.Optional[str], frame: int | None
) -> str:
    infix = ""
    if position is not None:
        infix = f".{position}"
    if frame is not None:
        infix = f"{infix}.f{frame}"
    return f".cache/{size}/{hsh[0]}/{hsh[1]}/{hsh[2]}/{hsh[3:]}{infix}.{extension}"


@app.get(
    "/export",
    responses={
        200: {
            "description": "tar file with selected photos",
            "content": {"application/x-tar": {"example": "No example available."}},
        }
    },
)
def export_photos(query: str) -> StreamingResponse:
    db = DB.get()
    actual_query = SearchQuery.from_json(query)

    def image_iterator(
        query: SearchQuery,
    ) -> t.Iterable[t.Tuple[str, t.Optional[datetime], t.Optional[ImageAddress]]]:
        page = 0
        paging = 1000
        has_next_page = True
        while has_next_page:
            omgs, has_next_page = db.get_matching_images(
                query, SortParams(SortBy.TIMESTAMP, SortOrder.ASC), GalleryPaging(page, paging)
            )
            page += 1
            for omg in omgs:
                filename = None
                for possible_filename in db.files(omg.md5):
                    if os.path.exists(possible_filename.file):
                        filename = possible_filename.file
                        break
                if filename is None:
                    continue
                yield (filename, omg.date, omg.address)

    pretty = pathify(actual_query.to_user_string().replace("/", "_").replace(":", "_"))
    if pretty:
        filename = f"export-{pretty}"
    else:
        filename = "export"
    tar = tar_stream(non_repeating_dirs(filename, image_iterator(actual_query), use_geo=False))
    return StreamingResponse(
        content=tar,
        headers={"Content-Disposition": f'attachment; filename*="{filename}.tar"'},
        media_type="application/x-tar",
    )


def _download_file_response(hsh: str) -> t.Any:
    file_path = DB.get().get_path_from_hash(hsh)
    if file_path is not None and os.path.exists(file_path):
        # TODO: fix media type
        return FileResponse(file_path, filename=file_path.split("/")[-1])
    return {"error": "File not found!"}


def _create_cache_file(
    img: Image.Image, cache_file: str, sz: int | str, position: str | None, frame: int | None
) -> None:
    if position is not None:
        pos = Position.from_query_string(position, frame)
        if pos is not None:
            # TODO: check that this is within proper bounds or something like that
            img = img.crop((pos.left, pos.top, pos.right, pos.bottom))
    if isinstance(sz, int):
        img.thumbnail((sz, sz))
    dirname = os.path.dirname(cache_file)
    if not os.path.exists(dirname):
        os.makedirs(dirname, exist_ok=True)
    if "exif" in img.info:
        exif = img.info["exif"]
        img.save(cache_file, format=img.format, exif=exif)
    else:
        img.save(cache_file, format=img.format)


# TODO:
# store extension inside cache file, so that this endpoint does not need extension.
# Can be some encoding with <length><extension><length><metadata><length><data>
# TODO:
# Handle caching of cropped parts with care -- or maybe add some timeout (week or so),
# or have cache LRU cache or something, with some max cache size -- maybe use diskcache
@app.get(
    "/img/{size}/{hsh}.{extension}",
    responses={
        200: {"description": "photo", "content": {"image/jpeg": {"example": "No example available."}}}
    },
)
def image_endpoint(
    hsh: t.Annotated[str, PathParam(pattern="^[0-9a-zA-Z]+$", min_length=7, max_length=40)],
    size: ImageSize,
    extension: t.Annotated[str, PathParam(pattern="^[0-9a-zA-Z]+$", min_length=1, max_length=10)],
    position: t.Annotated[t.Optional[str], Query(pattern="^[0-9]+,[0-9]+,[0-9]+,[0-9]*$")] = None,
    frame: t.Optional[int] = None,
) -> t.Any:
    media_class = supported_media_class(f"file.{extension}")
    if media_class == SupportedMediaClass.VIDEO:
        return get_video_preview(hsh, size, extension, position, frame)
    if media_class == SupportedMediaClass.IMAGE:
        return get_image_preview(hsh, size, extension, position)
    if media_class is None:
        return {"error": "Unsupported media type"}
    assert_never(media_class)


def get_image_preview(hsh: str, size: ImageSize, extension: str, position: t.Optional[str]) -> t.Any:
    resolution = sz_to_resolution(size)
    if resolution is not None or position is not None:
        if position is not None:
            sz: int | str = "crop"
        else:
            sz = t.cast(int, resolution)
        if (isinstance(sz, str) and not sz.isalnum()) or not hsh.isalnum() or not extension.isalnum():
            # pylint: disable-next = broad-exception-raised
            raise Exception("Validation error, image contained disallowed characters")
        cache_file = get_cache_file(sz, hsh, extension, position, None)
        if not os.path.exists(cache_file):
            file_path = DB.get().get_path_from_hash(hsh)
            if file_path is None:
                return {"error": "File not found!"}
            img = Image.open(file_path)
            _create_cache_file(img, cache_file, sz, position, None)
        return FileResponse(cache_file, filename=cache_file.split("/")[-1])
    return _download_file_response(hsh)


def get_video_preview(
    hsh: str, size: ImageSize, extension: str, position: t.Optional[str], frame: t.Optional[int]
) -> t.Any:
    resolution = sz_to_resolution(size)
    if position is not None:
        sz: int | str = "crop"
    if resolution is None:
        sz = "frame"
    else:
        sz = resolution
    if (isinstance(sz, str) and not sz.isalnum()) or not hsh.isalnum() or not extension.isalnum():
        # pylint: disable-next = broad-exception-raised
        raise Exception("Validation error, image contained disallowed characters")
    cache_file = get_cache_file(sz, hsh, "jpg", position, frame)
    if not os.path.exists(cache_file):
        file_path = DB.get().get_path_from_hash(hsh)
        if file_path is None:
            return {"error": "File not found!"}
        video_frame = get_video_frame(file_path, frame)
        if video_frame is None:
            return {"error": "Unable to extract frame from the video"}
        _create_cache_file(video_frame.image, cache_file, sz, position, frame)
    return FileResponse(cache_file, filename=cache_file.split("/")[-1])


@dataclass
class LocClusterParams:
    nw: LocPoint
    se: LocPoint
    url: SearchQuery
    res: LocPoint
    of: float = 0.5


@app.post("/api/location_clusters")
def location_clusters_endpoint(params: LocClusterParams) -> t.List[LocationCluster]:
    clusters = DB.get().get_image_clusters(
        params.url,
        params.nw,
        params.se,
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
                            job.example_path_extension or "jpg",
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
        elif job.type_ == RemoteJobType.FACE_CLUSTER_ANNOTATION:
            pass
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
    extensions = {img.md5: img.extension for img in all_images.get()[0]}

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
                extensions.get(md5) or "jpg",
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
    db.mark_annotated([t for t, _, _ in tasks])
    await refresh_jobs(job_id)
    return job_id


@dataclass
class FaceIdentifier(DataClassJsonMixin):
    md5: str
    extension: str
    position: Position


@dataclass
class ManualIdentityClusterRequest(DataClassJsonMixin):
    identity: t.Optional[str]
    skip_reason: t.Optional[IdentitySkipReason]
    faces: t.List[FaceIdentifier]


def parse_manual_identity_cluster_requests(data: bytes) -> t.List[ManualIdentityClusterRequest]:
    return [ManualIdentityClusterRequest.from_dict(x) for x in json.loads(data.decode("utf-8"))]


@app.post("/api/manual_identity_annotation")
async def manual_identity_annotation_endpoint(clusters: t.List[ManualIdentityClusterRequest]) -> int:
    # Group by md5
    db = DB.get()
    by_md5: t.Dict[t.Tuple[str, str], t.List[ManualIdentity]] = {}
    for cluster in clusters:
        if cluster.identity is not None and cluster.faces:
            db.identities.add(cluster.identity, cluster.faces[0].md5, cluster.faces[0].extension, False)
        for face in cluster.faces:
            by_md5.setdefault((face.md5, face.extension), []).append(
                ManualIdentity(cluster.identity, cluster.skip_reason, face.position)
            )
    job_id = db.jobs.submit_job(
        RemoteJobType.FACE_CLUSTER_ANNOTATION,
        json.dumps([x.to_dict(encode_json=True) for x in clusters], ensure_ascii=False).encode("utf-8"),
        [
            (md5, ext, json.dumps([t.to_json_dict() for t in task]).encode("utf-8"))
            for (md5, ext), task in by_md5.items()
        ],
    )
    await refresh_jobs(job_id)
    return job_id


GEOLOCATOR = Geolocator()


@dataclass
class FoundLocation:
    latitude: float
    longitude: float
    address: str


@dataclass
class MapSearchResponse:
    response: None | t.List[FoundLocation]
    error: None | str


@app.post("/api/map_search")
def find_location(req: str) -> MapSearchResponse:
    try:
        result = GEOLOCATOR.search(req, limit=10) if req != "" else []
        return MapSearchResponse([FoundLocation(r.latitude, r.longitude, r.address) for r in result], None)
    # pylint: disable-next = broad-exception-caught
    except Exception as e:
        traceback.print_exc()
        return MapSearchResponse(None, f"{e}\n{traceback.format_exc()}")


@dataclass
class JobProgressState:
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
    state: t.Optional[JobProgressState] = None


@dataclass
class JobProgressStateResponse:
    state: JobProgressState
    # TODO: move these to server
    diff: JobProgressState | None
    eta_str: str | None  # noqa: F841


@app.post("/api/job_progress_state")
def job_progress_state(req: JobProgressRequest) -> JobProgressStateResponse:
    jobs = DB.get().jobs.get_jobs(skip_finished=False)
    state = JobProgressState(datetime.now().timestamp(), 0, 0, 0, 0, 0)
    for job in jobs:
        state.t_total += job.total
        state.t_finished += job.finished_tasks
        state.j_total += 1
        state.j_finished += int(job.total == job.finished_tasks)
        state.j_waiting += int(job.finished_tasks == 0)
    # TODO: diff should be computed in the typescript, to avoid sending of state here
    if req.state is not None and state.progressed(req.state):
        diff = state.diff(req.state)
        if state.t_total == state.t_finished or diff.ts < 1 or diff.t_finished == 0:
            eta = None
        else:
            eta = str(timedelta(seconds=int((state.t_total - state.t_finished) * diff.ts / diff.t_finished)))
    else:
        diff = None
        eta = None
    return JobProgressStateResponse(state, diff, eta)


@dataclass
class JobDescription:
    icon: str
    total: str
    id: int  # noqa: F841
    type: str
    replacements: str
    time: float
    latitude: float | None
    longitude: float | None
    query: MassLocationAndTextAnnotation | t.List[ManualIdentityClusterRequest] | None
    job: RemoteJob[bytes]
    example_path_md5: str | None
    example_path_extension: str | None


@app.get("/api/remote_jobs")
# pylint: disable-next = too-many-statements
def remote_jobs() -> t.List[JobDescription]:
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
        type_ = []
        replacements = []
        latitude = None
        longitude = None
        request: None | MassLocationAndTextAnnotation | t.List[ManualIdentityClusterRequest] = None
        if job.type_ == RemoteJobType.MASS_MANUAL_ANNOTATION:
            type_.append("🗺️")
            try:
                og_req = mass_manual_annotation_from_json(job.original_request)
                request = og_req
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

            # pylint: disable-next = broad-exception-caught
            except Exception as e:
                replacements.append(str(e))
        elif job.type_ == RemoteJobType.FACE_CLUSTER_ANNOTATION:
            type_.append("🤓")
            og_clusters = parse_manual_identity_cluster_requests(job.original_request)
            request = og_clusters
            has_skip = False
            has_identity = False
            identities = set()
            for cluster in og_clusters:
                if cluster.skip_reason is not None:
                    has_skip = True
                if cluster.identity is not None:
                    has_identity = True
                    identities.add(cluster.identity)
            if has_skip:
                type_.append("❌")
            if has_identity:
                type_.append("🛂")
            for identity in identities:
                replacements.append(f"🛂{identity}")
            try:
                pass
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
            JobDescription(
                icon,
                total,
                job.id_,
                "".join(type_),
                repls,
                (job.last_update or job.created).timestamp(),
                latitude,
                longitude,
                request,
                job,
                job.example_path_md5,
                job.example_path_extension,
            )
        )
    return jobs


@app.get("/api/system_status")
async def system_status(_request: Request) -> SystemStatus:
    return await get_system_status()


@dataclass
class GetAddressRequest:
    latitude: float
    longitude: float


@app.post("/api/get_address")
def get_address(req: GetAddressRequest) -> ImageAddress:
    return make_image_address(
        GEOLOCATOR.address(PathWithMd5("", ""), req.latitude, req.longitude).p,
        None,
    )


@app.post("/api/directories")
def matching_directories(url: SearchQuery) -> t.List[DirectoryStats]:
    return sorted(DB.get().get_matching_directories(url), key=lambda x: x.directory)


@dataclass
class GalleryRequest:
    query: SearchQuery
    paging: GalleryPaging
    sort: SortParams


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


@dataclass
class ReferenceStats:
    distance_m: float
    seconds: float  # noqa: F841


@dataclass
class PredictedLocation:
    loc: LocPoint
    earlier: t.Optional[ReferenceStats]
    later: t.Optional[ReferenceStats]  # noqa: F841


@dataclass
class PathSplit:
    dir: str  # noqa: F841
    file: str

    @staticmethod
    def from_filename(filename: str) -> PathSplit:
        return PathSplit(
            dir=os.path.dirname(filename),
            file=os.path.basename(filename),
        )


@dataclass
class ImageWithMeta:
    omg: ImageRow
    predicted_location: t.Optional[PredictedLocation]
    paths: t.List[PathSplit]


@dataclass
class ImageResponse:
    has_next_page: bool
    omgs: t.List[ImageWithMeta]
    some_location: ManualLocation | None


@app.post("/api/images")
async def image_page(params: GalleryRequest) -> ImageResponse:
    images = []
    omgs, has_next_page = DB.get().get_matching_images(params.query, params.sort, params.paging)
    fwdbwd = forward_backward(omgs, DateWithLoc.from_image)

    some_location = None
    for index, omg in enumerate(omgs):
        paths = []
        for file in DB.get().files(omg.md5):
            paths.append(PathSplit.from_filename(file.file))
            if file.og_file is not None:
                paths.append(PathSplit.from_filename(file.og_file))
        if omg.latitude is not None and omg.longitude is not None:
            some_location = ManualLocation(
                omg.latitude,
                omg.longitude,
                omg.address.name,
                omg.address.country,
            )
        predicted_location = predict_location(omg, fwdbwd[index][0], fwdbwd[index][1])
        images.append(ImageWithMeta(omg, predicted_location, paths))
    return ImageResponse(has_next_page, images, some_location)


@dataclass
class FaceWithMeta:
    position: Position
    md5: str
    extension: str
    identity: t.Optional[str]
    skip_reason: t.Optional[IdentitySkipReason]
    embedding: t.List[float]


@dataclass
class FacesResponse:
    has_next_page: bool
    faces: t.List[FaceWithMeta]
    top_identities: t.List[IdentityRowPayload]


@app.post("/api/top_identities")
async def top_identities() -> t.List[IdentityRowPayload]:
    return DB.get().identities.top_identities(100)


@app.post("/api/faces")
async def faces_on_page(params: GalleryRequest) -> FacesResponse:
    faces = []
    db = DB.get()
    omgs, has_next_page = db.get_matching_images(params.query, params.sort, params.paging)
    top_idents = db.identities.top_identities(100)

    for omg in omgs:
        fcs = db.get_face_embeddings(omg.md5)
        identities = db.get_manual_identities(omg.md5)
        if identities is not None:
            ident_dct = {
                identity.position: identity.identity
                for identity in identities.identities
                if identity.identity is not None
            }
            skip_dct = {
                identity.position: identity.skip_reason
                for identity in identities.identities
                if identity.skip_reason is not None
            }
        else:
            ident_dct = {}
            skip_dct = {}
        if fcs is not None:
            for face in fcs.faces:
                faces.append(
                    FaceWithMeta(
                        face.position,
                        omg.md5,
                        omg.extension,
                        ident_dct.get(face.position),
                        skip_dct.get(face.position),
                        face.embedding,
                    )
                )
    return FacesResponse(has_next_page, faces, top_idents)


@dataclass
class FaceFeatureRequest:
    md5: str
    extension: str


@app.post("/api/face")
async def face_features_for_image(params: FaceFeatureRequest) -> t.List[FaceWithMeta]:
    db = DB.get()
    fcs = db.get_face_embeddings(params.md5)
    identities = db.get_manual_identities(params.md5)
    faces = []
    if identities is not None:
        ident_dct = {
            identity.position: identity for identity in identities.identities if identity.identity is not None
        }
        skip_dct = {
            identity.position: identity
            for identity in identities.identities
            if identity.skip_reason is not None
        }
    else:
        ident_dct = {}
        skip_dct = {}
    empty_identity = ManualIdentity(None, None, Position(0, 0, 0, 0, None))
    if fcs is not None:
        for face in fcs.faces:
            faces.append(
                FaceWithMeta(
                    face.position,
                    params.md5,
                    params.extension,
                    ident_dct.pop(face.position, empty_identity).identity,
                    skip_dct.pop(face.position, empty_identity).skip_reason,
                    face.embedding,
                )
            )
    for ident in itertools.chain(ident_dct.values(), skip_dct.values()):
        faces.append(
            FaceWithMeta(ident.position, params.md5, params.extension, ident.identity, ident.skip_reason, [])
        )
    return faces


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


def distance_m(p1: LocPoint, p2: LocPoint) -> float:
    return t.cast(float, distance((p1.latitude, p1.longitude), (p2.latitude, p2.longitude)).m)


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
        if t_d == 0:
            loc_point = prev_loc.loc + (next_loc.loc - prev_loc.loc).scale(0.5)
        else:
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


@dataclass
class AggregateQuery:
    query: SearchQuery


@app.post("/api/aggregate")
def aggregate_images(param: AggregateQuery) -> ImageAggregation:
    aggr = DB.get().get_aggregate_stats(param.query)
    return aggr


@app.get("/index.html")
@app.get("/")
async def read_index() -> FileResponse:
    return FileResponse("static/index.html")
