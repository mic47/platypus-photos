from dataclasses import dataclass
import json
import typing as t
import yaml

from dataclasses_json import DataClassJsonMixin


@dataclass
class DBFilesConfig:
    image_to_text_jsonl: str = "data/output-image-to-text.jsonl"
    exif_jsonl: str = "data/output-exif.jsonl"
    geo_address_jsonl: str = "data/output-geo.jsonl"
    photos_db: str = "data/photos.db"


@dataclass
class DirectoryMatchingConfig(DataClassJsonMixin):
    date_directory_filters: t.List[str]
    no_date_in_path_filters: t.List[str]
    path_to_date: t.Dict[str, str]


class UnsupportedFileType(Exception):
    def __init__(self, file: str) -> None:
        super().__init__(f"Unsupported file type {file}")
        self.file = file


@dataclass
class Config(DataClassJsonMixin):
    input_patterns: t.List[str]
    input_directories: t.List[str]
    watched_directories: t.List[str]
    directory_matching: DirectoryMatchingConfig

    @staticmethod
    def load(file: str) -> "Config":
        with open(file, encoding="utf-8") as f:
            if file.endswith(".yaml"):
                data = yaml.load(f)
            elif file.endswith(".json"):
                data = json.load(f)
            else:
                raise UnsupportedFileType(file)
        return Config.from_dict(data)
