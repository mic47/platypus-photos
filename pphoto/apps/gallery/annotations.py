from __future__ import annotations

import json
import typing as t
from datetime import datetime, timedelta
from dataclasses import dataclass

from dataclasses_json import DataClassJsonMixin

from fastapi import APIRouter, Request

from pphoto.communication.client import get_system_status, refresh_jobs, SystemStatus
from pphoto.data_model.face import Position
from pphoto.data_model.manual import ManualIdentity, IdentitySkipReason
from pphoto.utils import assert_never, Lazy
from pphoto.remote_jobs.types import (
    RemoteJob,
    RemoteJobType,
    ManualLocation,
    ManualAnnotationTask,
    ManualDate,
)

from pphoto.gallery.db import ImageSqlDB, Image as ImageRow
from pphoto.gallery.url import SearchQuery, GalleryPaging, SortParams, SortBy, SortOrder
from pphoto.gallery.unicode import flag

from .common import (
    DB,
    forward_backward,
    DateWithLoc,
    predict_location,
    MassLocationAndTextAnnotation,
    LocationTypes,
    ManualLocationOverride,
    DateTypes,
    TextAnnotationOverride,
    mass_manual_annotation_from_json,
)

router = APIRouter(prefix="/api/annotations")


MassManualAnnotation = MassLocationAndTextAnnotation


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


@router.post("/mass_manual_annotation")
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


@router.post("/manual_identity_annotation")
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


@router.post("/job_progress_state")
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


@router.get("/remote_jobs")
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


@router.get("/system_status")
async def system_status(_request: Request) -> SystemStatus:
    return await get_system_status()
