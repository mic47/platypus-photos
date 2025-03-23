from __future__ import annotations

import json
import typing as t

from datetime import datetime
from dataclasses import dataclass, field

from pphoto.data_model.base import StorableData

T = t.TypeVar("T")


@dataclass
class GPSCoord:
    latitude: float
    longitude: float
    altitude: t.Optional[float]
    date: t.Optional[datetime]

    def to_json_dict(self) -> t.Any:
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "altitude": self.altitude,
            "date": None if self.date is None else self.date.timestamp(),
        }

    @staticmethod
    def from_json_dict(d: t.Dict[str, t.Any]) -> GPSCoord:
        alt = d.get("altitude")
        date = d.get("date")
        return GPSCoord(
            float(d["latitude"]),
            float(d["longitude"]),
            None if alt is None else float(alt),
            None if date is None else datetime.fromtimestamp(date),
        )


@dataclass
class Camera:
    make: str  # noqa: F841
    model: str
    serial_number: str  # noqa: F841
    software: str  # noqa: F841

    @staticmethod
    def from_json_dict(d: t.Dict[str, t.Any]) -> Camera:
        return Camera(
            d["make"],
            d["model"],
            d["serial_number"],
            d["software"],
        )

    def to_json_dict(self) -> t.Any:
        return {
            "make": self.make,
            "model": self.model,
            "serial_number": self.serial_number,
            "software": self.software,
        }


@dataclass
class VideoInfo:
    frame_rate: t.Optional[float]
    duration_seconds: t.Optional[float]

    @staticmethod
    def from_json_dict(d: t.Dict[str, t.Any]) -> VideoInfo:
        frame_rate = d.get("frame_rate")
        duration_seconds = d.get("duration_seconds")
        return VideoInfo(
            None if frame_rate is None else float(frame_rate),
            None if duration_seconds is None else float(duration_seconds),
        )

    def to_json_dict(self) -> t.Any:
        return {
            "frame_rate": self.frame_rate,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class Date:
    datetime: t.Optional[datetime]
    time_str: t.Optional[str]  # noqa: F841

    @staticmethod
    def from_json_dict(d: t.Dict[str, t.Any]) -> Date:
        dt = d.get("datetime")
        return Date(
            None if dt is None else datetime.fromtimestamp(dt),
            d.get("time_str"),
        )

    def to_json_dict(self) -> t.Any:
        return {
            "datetime": None if self.datetime is None else self.datetime.timestamp(),
            "time_str": self.time_str,
        }


@dataclass
class ImageExif(StorableData):
    gps: t.Optional[GPSCoord]
    camera: Camera
    date: t.Optional[Date]
    orientation: t.Optional[int]
    video_info: t.Optional[VideoInfo] = field(default=None)

    def to_json_dict(self) -> t.Any:
        return {
            "gps": None if self.gps is None else self.gps.to_json_dict(),
            "camera": self.camera.to_json_dict(),
            "date": None if self.date is None else self.date.to_json_dict(),
            "orientation": self.orientation,
            "video_info": None if self.video_info is None else self.video_info.to_json_dict(),
        }

    @staticmethod
    def from_json_dict(d: t.Dict[str, t.Any]) -> ImageExif:
        gps = d.get("gps")
        date = d.get("date")
        video_info = d.get("video_info")
        return ImageExif(
            None if gps is None else GPSCoord.from_json_dict(gps),
            Camera.from_json_dict(d["camera"]),
            None if date is None else Date.from_json_dict(date),
            d.get("orientation"),
            None if video_info is None else VideoInfo.from_json_dict(video_info),
        )

    @staticmethod
    def from_json_bytes(x: bytes) -> ImageExif:
        return ImageExif.from_json_dict(json.loads(x))

    @staticmethod
    def current_version() -> int:
        return 1
