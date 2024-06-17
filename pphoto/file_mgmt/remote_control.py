import dataclasses
import enum
import json

import dataclasses_json


class ImportMode(enum.Enum):
    MOVE = "move"
    MOVE_OR_DELETE = "move_or_delete"
    COPY = "copy"

    def should_delete_original_if_exists(self) -> bool:
        return self == ImportMode.MOVE_OR_DELETE


@dataclasses.dataclass
class ImportCommand(dataclasses_json.DataClassJsonMixin):
    import_path: str
    mode: ImportMode = dataclasses.field(default=ImportMode.COPY)


@dataclasses.dataclass
class RefreshJobs(dataclasses_json.DataClassJsonMixin):
    job_id: int


Jobs = ImportCommand | RefreshJobs


def serialize_rc_job(job: Jobs) -> str:
    dct = job.to_dict(encode_json=True)
    dct["__type__"] = type(job).__name__
    return json.dumps(str, ensure_ascii=False)


def write_serialized_rc_job(path: str, job: Jobs) -> None:
    with open(path, "a", encoding="utf-8") as f:
        serialized = serialize_rc_job(job)
        f.write(f"{serialized}\n")
        f.flush()


def parse_rc_job(line: str) -> Jobs:
    dct = json.loads(line)
    type_ = dct["__type__"]
    if type_ == RefreshJobs.__name__:
        return RefreshJobs.from_dict(dct)
    if type_ == ImportCommand.__name__:
        return ImportCommand.from_dict(dct)
    if "import_path" in dct:
        return ImportCommand.from_dict(dct)
    if "job_id" in dct:
        return RefreshJobs.from_dict(dct)
    raise InvalidRemoteControlValue(line)


class InvalidRemoteControlValue(Exception):
    def __init__(self, value: str):
        super().__init__(f"Unable to deserialize {value}")
