from __future__ import annotations

import itertools
import typing as t
import os
from dataclasses import dataclass


from fastapi import APIRouter

from pphoto.data_model.face import Position
from pphoto.data_model.manual import ManualIdentity, IdentitySkipReason
from pphoto.db.types_location import LocationCluster, LocPoint, LocationBounds
from pphoto.db.types_date import DateCluster, DateClusterGroupBy
from pphoto.db.types_directory import DirectoryStats
from pphoto.db.types_image import ImageAggregation
from pphoto.db.types_identity import IdentityRowPayload
from pphoto.remote_jobs.types import (
    ManualLocation,
)

from pphoto.gallery.db import Image as ImageRow
from pphoto.gallery.url import SearchQuery, GalleryPaging, SortParams

from .common import (
    DateWithLoc,
    DB,
    forward_backward,
    PredictedLocation,
    predict_location,
)

router = APIRouter(prefix="/api/web")


@dataclass
class LocClusterParams:
    nw: LocPoint
    se: LocPoint
    url: SearchQuery
    res: LocPoint
    of: float = 0.5


@router.post("/location_clusters")
def location_clusters_endpoint(params: LocClusterParams) -> t.List[LocationCluster]:
    clusters = DB.get().get_image_clusters(
        params.url,
        params.nw,
        params.se,
        params.res.latitude,
        params.res.longitude,
        params.of,
    )
    return clusters


@router.post("/bounds")
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


@router.post("/date_clusters")
def date_clusters_endpoint(params: DateClusterParams) -> t.List[DateCluster]:
    clusters = DB.get().get_date_clusters(
        params.url,
        params.group_by,
        params.buckets,
    )
    return clusters


@dataclass
class GalleryRequest:
    query: SearchQuery
    paging: GalleryPaging
    sort: SortParams


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


@router.post("/images")
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


@router.post("/directories")
def matching_directories(url: SearchQuery) -> t.List[DirectoryStats]:
    return sorted(DB.get().get_matching_directories(url), key=lambda x: x.directory)


@router.post("/top_identities")
async def top_identities() -> t.List[IdentityRowPayload]:
    return DB.get().identities.top_identities(100)


@dataclass
class AggregateQuery:
    query: SearchQuery


@router.post("/aggregate")
def aggregate_images(param: AggregateQuery) -> ImageAggregation:
    aggr = DB.get().get_aggregate_stats(param.query)
    return aggr


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


@router.post("/faces")
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


@router.post("/face")
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
