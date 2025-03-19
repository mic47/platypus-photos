from __future__ import annotations

import typing as t
import os
from datetime import datetime


from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from pphoto.db.types_image import ImageAddress

from pphoto.gallery.db import ImageSqlDB
from pphoto.gallery.url import SearchQuery, GalleryPaging, SortParams, SortBy, SortOrder
from pphoto.file_mgmt.archive import non_repeating_dirs, tar_stream, copy_stream
from pphoto.utils.files import pathify, expand_vars_in_path

from .common import DB, CONFIG

router = APIRouter(prefix="/api/export")


@router.get("/config_export_dirs")
def config_export_dirs_endpoint() -> t.List[str]:
    config = CONFIG.get()
    return sorted(list(config.export_directories.keys()))


@router.get(
    "/tar",
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

    pretty = pathify(actual_query.to_user_string().replace("/", "_").replace(":", "_"))
    if pretty:
        filename = f"export-{pretty}"
    else:
        filename = "export"
    tar = tar_stream(
        non_repeating_dirs(filename, image_iterator(db, actual_query), use_geo=False, use_filesystem=False)
    )
    return StreamingResponse(
        content=tar,
        headers={"Content-Disposition": f'attachment; filename*="{filename}.tar"'},
        media_type="application/x-tar",
    )


@router.get(
    "/dir",
    responses={
        200: {
            "description": "txt file with list of copied files",
            "content": {"text/plain": {"example": "No example available."}},
        }
    },
)
def export_photos_to_dir(query: str, base: str, subdir: str) -> StreamingResponse:
    config = CONFIG.get()
    base = expand_vars_in_path(config.export_directories[base])
    destination = os.path.realpath(f"{base}/{subdir}")
    # Make sure that it's still allowed directory
    if not destination.startswith(base + "/"):
        # pylint: disable-next = broad-exception-raised
        raise Exception("Directory is not allowed")
    if os.path.exists(destination):
        # pylint: disable-next = broad-exception-raised
        raise Exception("Directory already exists")
    db = DB.get()
    actual_query = SearchQuery.from_json(query)
    txt = copy_stream(
        non_repeating_dirs(destination, image_iterator(db, actual_query), use_geo=False, use_filesystem=True)
    )
    filename = pathify(actual_query.to_user_string().replace("/", "_").replace(":", "_"))
    return StreamingResponse(
        content=txt,
        headers={"Content-Disposition": f'attachment; filename*="export-{filename}.txt"'},
        media_type="text/plain",
    )


def image_iterator(
    db: ImageSqlDB,
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
