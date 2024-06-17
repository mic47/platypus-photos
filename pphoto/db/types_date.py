from dataclasses import dataclass


@dataclass
class DateCluster:
    example_path_md5: str
    bucket_min: float
    bucket_max: float
    overfetched: bool
    min_timestamp: float
    max_timestamp: float
    avg_timestamp: float
    total: int
