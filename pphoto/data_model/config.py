from dataclasses import dataclass
import json
import typing as t
import yaml

from dataclasses_json import DataClassJsonMixin

from pphoto.utils.files import expand_vars_in_path


@dataclass
class DBFilesConfig:
    image_to_text_jsonl: str = "data/output-image-to-text.jsonl"
    face_embeddings_jsonl: str = "data/output-face-embeddings.jsonl"
    exif_jsonl: str = "data/output-exif.jsonl"
    geo_address_jsonl: str = "data/output-geo.jsonl"
    manual_location_jsonl: str = "data/output-manual-location.jsonl"
    manual_identity_jsonl: str = "data/output-manual-identity.jsonl"
    manual_date_jsonl: str = "data/output-manual-date.jsonl"
    manual_text_jsonl: str = "data/output-manual-text.jsonl"
    photos_db: str = "data/photos.db"
    gallery_db: str = "data/gallery.db"
    jobs_db: str = "data/jobs.db"


@dataclass
class DirectoryMatchingConfig(DataClassJsonMixin):
    date_directory_filters: t.List[str]
    no_date_in_path_filters: t.List[str]
    path_to_date: t.Dict[str, str]

    def resolve_vars(self) -> "DirectoryMatchingConfig":
        self.date_directory_filters = [expand_vars_in_path(x) for x in self.date_directory_filters]
        self.no_date_in_path_filters = [expand_vars_in_path(x) for x in self.no_date_in_path_filters]
        self.path_to_date = {expand_vars_in_path(x): v for x, v in self.path_to_date.items()}
        return self


class UnsupportedFileType(Exception):
    def __init__(self, file: str) -> None:
        super().__init__(f"Unsupported file type {file}")
        self.file = file


@dataclass
class Config(DataClassJsonMixin):
    managed_folder: str
    input_patterns: t.List[str]
    input_directories: t.List[str]
    watched_directories: t.List[str]
    directory_matching: DirectoryMatchingConfig

    @staticmethod
    def load(file: str) -> "Config":
        with open(file, encoding="utf-8") as f:
            if file.endswith(".yaml"):
                data = yaml.load(f, Loader=yaml.SafeLoader)
            elif file.endswith(".json"):
                data = json.load(f)
            else:
                raise UnsupportedFileType(file)
        return Config.from_dict(data).resolve_vars()

    def resolve_vars(self) -> "Config":
        self.managed_folder = expand_vars_in_path(self.managed_folder)
        self.input_patterns = [expand_vars_in_path(x) for x in self.input_patterns]
        self.input_directories = [expand_vars_in_path(x) for x in self.input_directories]
        self.watched_directories = [expand_vars_in_path(x) for x in self.watched_directories]
        self.directory_matching = self.directory_matching.resolve_vars()
        return self
