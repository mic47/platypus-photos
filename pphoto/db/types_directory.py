from dataclasses import dataclass
import typing as t


@dataclass
class DirectoryStats:
    directory: str
    total_images: int
    has_location: int
    has_timestamp: int
    being_annotated: int
    since: t.Optional[float]
    until: t.Optional[float]
