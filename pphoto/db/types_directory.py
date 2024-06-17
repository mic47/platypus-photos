from dataclasses import dataclass


@dataclass
class DirectoryStats:
    directory: str
    total_images: int
    has_location: int
    has_timestamp: int
    being_annotated: int
