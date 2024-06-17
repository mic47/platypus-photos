import dataclasses
import enum

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
