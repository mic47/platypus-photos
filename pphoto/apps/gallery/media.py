from __future__ import annotations

import typing as t
import os
import enum

from PIL import Image

from fastapi import APIRouter, Query, Path as PathParam
from fastapi.responses import FileResponse

from pphoto.data_model.face import Position
from pphoto.utils import assert_never

from pphoto.utils.files import supported_media_class, SupportedMediaClass
from pphoto.utils.video import get_video_frame

from .common import DB

# Intentionally do not have prefix.
router = APIRouter()


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
@router.get(
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
