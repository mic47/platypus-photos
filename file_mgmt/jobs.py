import dataclasses
import datetime
import os
import shutil
import typing as t
import sys

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


class Jobs:
    def __init__(self, managed_folder: str, files: FilesTable, annotator: Annotator):
        self.photos_dir = managed_folder
        self._files = files
        self._annotator = annotator

    async def image_to_text(self, path: PathWithMd5) -> None:
        # This is relatively simple job, does not wait
        await self._annotator.image_to_text(path)

    def get_path_with_md5_to_enqueue(self, path: str, can_add: bool) -> t.Optional[PathWithMd5]:
        if not _is_valid_file(path):
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

    def import_file(self, path: str) -> t.Optional[EnqueuePathAction]:
        if not _is_valid_file(path):
            return None
        path_with_md5 = compute_md5(path)
        if any(os.path.exists(x.file) and x.file != path for x in self._files.by_md5(path_with_md5.md5)):
            # There exists file with this md5, we can skip this file.
            # TODO: maybe we should delete it (or delete with parameters?)
            return None
        # Do cheap annotation
        (_path, exif, geo, path_date) = self._annotator.cheap_features(path_with_md5)
        date = (None if exif.p is None or exif.p.date is None else exif.p.date.datetime) or path_date
        # Move file
        # TODO: we need to extract date and location from the path
        new_dir = _resolve_dir(self.photos_dir, date, None if geo is None else geo.p)
        os.makedirs(new_dir, exist_ok=True)
        new_path: PathWithMd5 = PathWithMd5(
            _resolve_path(new_dir, path_with_md5.path),
            path_with_md5.md5,
        )
        # TODO: what happens if this file is watched
        # TODO: annotate date by path + geofile
        # TODO: this should not exists, right? Maybe just add?
        self._files.add_if_not_exists(
            new_path.path, new_path.md5, path_with_md5.path, ManagedLifecycle.IMPORTED, None
        )
        shutil.move(path_with_md5.path, new_path.path)
        self._files.set_lifecycle(new_path.path, ManagedLifecycle.SYNCED, None)
        # Schedule expensive annotation
        return EnqueuePathAction(new_path, IMPORT_PRIORITY)

    def cheap_features(self, path: PathWithMd5) -> None:
        # Annotate features
        (path, exif, geo, path_date) = self._annotator.cheap_features(path)

        # Figure out if file should be moved
        date = (None if exif.p is None or exif.p.date is None else exif.p.date.datetime) or path_date
        new_dir = _resolve_dir(self.photos_dir, date, None if geo is None else geo.p)
        old_dir = os.path.dirname(path.path)
        if old_dir == new_dir:
            # Dir is same, not moving file
            return

        file_row = self._files.by_path(path.path)
        if file_row is None or file_row.managed == ManagedLifecycle.NOT_MANAGED:
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

    def fix_in_progress_moved_files_at_startup(self) -> None:
        for file_row in self._files.by_managed_lifecycle(ManagedLifecycle.BEING_MOVED_AROUND):
            old_path = file_row.file
            new_path = file_row.tmp_file
            if new_path is None:
                print("ERROR in BEING_MOVED_AROUND sync state", file_row, file=sys.stderr)
                continue
            if old_path != new_path and (
                not os.path.exists(new_path) or compute_md5(new_path).md5 != file_row.md5
            ):
                shutil.move(old_path, new_path)
            if old_path != new_path:
                self._files.change_path(old_path, new_path)
            self._files.set_lifecycle(new_path, ManagedLifecycle.SYNCED, None)

    def fix_imported_files_at_startup(self) -> None:
        for file_row in self._files.by_managed_lifecycle(ManagedLifecycle.IMPORTED):
            old_path = file_row.og_file
            new_path = file_row.file
            if old_path is None:
                print("ERROR in IMPORTED sync state", file_row, file=sys.stderr)
                continue
            if old_path != new_path and (
                not os.path.exists(new_path) or compute_md5(new_path).md5 != file_row.md5
            ):
                shutil.move(old_path, new_path)
            self._files.set_lifecycle(new_path, ManagedLifecycle.SYNCED, None)


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


def _is_valid_file(path: str) -> bool:
    if not os.path.exists(path):
        return False
    if not os.path.isfile(path):
        return False
    if supported_media(path) is None:
        return False
    return True
