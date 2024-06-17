from dataclasses import dataclass
import enum
import typing as t


class ManagedLifecycle(enum.IntEnum):
    NOT_MANAGED = 0
    # File is where is should be (`file`)
    SYNCED = 1
    # File metadata changed, file is being moved.
    BEING_MOVED_AROUND = 2
    # File just has been imported, moving from `og_file` to `file` location
    IMPORTED = 3


@dataclass
class FileRow:
    file: str
    md5: t.Optional[str]
    og_file: t.Optional[str]
    tmp_file: t.Optional[str]
    managed: ManagedLifecycle  # File location is managed by application
    last_update: int
    rowid: int
