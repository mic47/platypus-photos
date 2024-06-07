import dataclasses
import datetime
import os
import shutil
import typing as t

from annots.md5 import compute_md5
from annots.annotator import Annotator
from data_model.features import PathWithMd5, GeoAddress
from db import FilesTable
from db.types import ManagedLifecycle
from utils.files import supported_media, pathify

IMPORT_PRIORITY = 46
DEFAULT_PRIORITY = 47
REALTIME_PRIORITY = 23


@dataclasses.dataclass
class EnqueuePathAction:
    path_with_md5: PathWithMd5
    priority: int


JobAction = EnqueuePathAction


class Jobs:
    def __init__(self, files: FilesTable, annotator: Annotator):
        self.photos_dir = "/home/mic/Gallery"
        self._files = files
        self._annotator = annotator

    async def image_to_text(self, path: PathWithMd5) -> None:
        # This is relatively simple job, does not wait
        await self._annotator.image_to_text(path)

    def get_path_with_md5_to_enqueue(self, path: str, can_add: bool) -> t.Optional[PathWithMd5]:
        if not os.path.exists(path):
            return None
        if not os.path.isfile(path):
            return None
        if supported_media(path) is None:
            return None
        file_row = self._files.by_path(path)
        if file_row is None:
            if not can_add:
                # TODO: error?
                return None
            # File does not exists
            path_with_md5 = compute_md5(path)
            # TODO: if path is in managed files, make it managed?
            self._files.add_if_not_exists(path, path_with_md5.md5, None, ManagedLifecycle.NOT_MANAGED, None)
        else:
            md5 = file_row.md5
            if md5 is None:
                path_with_md5 = compute_md5(path)
                self._files.add_or_update(
                    file_row.file, path_with_md5.md5, file_row.og_file, file_row.managed, file_row.tmp_file
                )
            else:
                path_with_md5 = PathWithMd5(path, md5)
        return path_with_md5

    def import_file(self, path: PathWithMd5) -> EnqueuePathAction:
        # Do not import if file exists, delete if it exists
        # TODO: make this async
        if not path.md5:
            path = compute_md5(path.path)
        # Do cheap annotation
        (_path, exif, geo, path_date) = self._annotator.cheap_features(path)
        date = (None if exif.p.date is None else exif.p.date.datetime) or path_date
        # Move file
        # TODO: we need to extract date and location from this one
        new_dir = _resolve_dir(self.photos_dir, date, None if geo is None else geo.p)
        os.makedirs(new_dir, exist_ok=True)
        new_path: PathWithMd5 = PathWithMd5(
            _resolve_path(new_dir, path.path),
            path.md5,
        )
        # TODO: what happens if this file is watched
        # TODO: annotate date by path + geofile
        # TODO: this should not exists, right? Maybe just add?
        self._files.add_if_not_exists(new_path.path, new_path.md5, path.path, ManagedLifecycle.IMPORTED, None)
        shutil.move(path.path, new_path.path)
        self._files.set_lifecycle(new_path.path, ManagedLifecycle.SYNCED, None)
        # Schedule expensive annotation
        return EnqueuePathAction(new_path, IMPORT_PRIORITY)

    def cheap_features(self, path: PathWithMd5) -> None:
        # Annotate features
        (path, exif, geo, path_date) = self._annotator.cheap_features(path)

        # Figure out if file should be moved
        date = (None if exif.p.date is None else exif.p.date.datetime) or path_date
        new_dir = _resolve_dir(self.photos_dir, date, None if geo is None else geo.p)
        old_dir = os.path.dirname(path.path)
        if old_dir == new_dir:
            # Dir is same, not moving file
            return

        file_row = self._files.by_path(path.path)
        if file_row is None or file_row.managed is None:
            # File is not managed, skipping
            return

        new_path: PathWithMd5 = PathWithMd5(
            _resolve_path(new_dir, path.path),
            path.md5,
        )
        os.makedirs(new_dir, exist_ok=True)
        self._files.set_lifecycle(path.path, ManagedLifecycle.BEING_MOVED_AROUND, new_path.path)
        shutil.move(path.path, new_path.path)
        self._files.change_path(path.path, new_path.path)
        self._files.set_lifecycle(new_path.path, ManagedLifecycle.SYNCED, None)


def _resolve_dir(photos_dir: str, date: t.Optional[datetime.datetime], geo: t.Optional[GeoAddress]) -> str:
    # f"{base_dir}/{year}/{month}-{day}-{place}/{filename}_{exists_suffix}.{extension}"
    path = photos_dir
    if date is not None:
        path = f"{path}/{date.year}/{date.month}-{date.day}"
    else:
        path = f"{path}/UnknownDate"
    if geo is not None:
        path = f"{path}-{pathify(geo.address)}"
    return path


def _resolve_path(directory: str, og_path: str) -> str:
    path = directory
    filename = os.path.basename(og_path)
    splitted = filename.rsplit(".", maxsplit=1)
    extension = splitted[-1]
    basefile = ".".join(splitted[:-1])
    insert = ""
    count = 0
    while True:
        final_path = f"{path}/{basefile}{insert}.{extension}"
        if not os.path.exists(final_path):
            break
        insert = f"_{count:03d}"
        count += 1
    return final_path
