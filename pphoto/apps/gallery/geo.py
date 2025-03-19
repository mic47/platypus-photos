from __future__ import annotations

import typing as t
import traceback
from dataclasses import dataclass


from fastapi import APIRouter

from pphoto.annots.geo import Geolocator
from pphoto.data_model.base import PathWithMd5
from pphoto.db.types_image import ImageAddress
from pphoto.gallery.image import make_image_address

router = APIRouter(prefix="/api/export")

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


@router.post("/map_search")
def find_location(req: str) -> MapSearchResponse:
    try:
        result = GEOLOCATOR.search(req, limit=10) if req != "" else []
        return MapSearchResponse([FoundLocation(r.latitude, r.longitude, r.address) for r in result], None)
    # pylint: disable-next = broad-exception-caught
    except Exception as e:
        traceback.print_exc()
        return MapSearchResponse(None, f"{e}\n{traceback.format_exc()}")


@dataclass
class GetAddressRequest:
    latitude: float
    longitude: float


@router.post("/get_address")
def get_address(req: GetAddressRequest) -> ImageAddress:
    return make_image_address(
        GEOLOCATOR.address(PathWithMd5("", ""), req.latitude, req.longitude).p,
        None,
    )
