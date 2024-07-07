from dataclasses import dataclass
import enum
import typing as t


class DateClusterGroupBy(enum.Enum):
    COUNTRY = "country"
    CAMERA = "camera"
    HAS_LOCATION = "has_location"
    ADDRESS_NAME = "address_name"


@dataclass
class DateClusterGroup:
    address_name: t.Optional[str]
    country: t.Optional[str]
    camera: t.Optional[str]
    has_location: t.Optional[bool]


@dataclass
class DateCluster:
    example_path_md5: str
    example_path_extension: str
    bucket_min: float
    bucket_max: float
    overfetched: bool
    min_timestamp: float
    max_timestamp: float
    avg_timestamp: float
    total: int
    group_by: DateClusterGroup
