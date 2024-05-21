from dataclasses_json import DataClassJsonMixin
from dataclasses import dataclass
import json
import os
import yaml

import typing as t


@dataclass
class DirectoryMatchingConfig(DataClassJsonMixin):
    date_directory_filters: t.List[str]
    no_date_in_path_filters: t.List[str]
    path_to_date: t.Dict[str, str]


@dataclass
class Config(DataClassJsonMixin):
    input_patterns: t.List[str]
    input_directories: t.List[str]
    directory_matching: DirectoryMatchingConfig

    @staticmethod
    def load(file: str) -> "Config":
        with open(file, encoding="utf-8") as f:
            if file.endswith(".yaml"):
                data = yaml.load(f)
            elif file.endswith(".json"):
                data = json.load(f)
            else:
                raise Exception(f"Unsupported file type {file}")
        return Config.from_dict(data)
