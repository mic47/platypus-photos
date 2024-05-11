import exif
import itertools
import typing as t
import sys
from dataclasses_json import DataClassJsonMixin
from dataclasses import dataclass
from datetime import datetime, timedelta

from cache import HasImage, Cache


IGNORED_TAGS = [
    "aperture_value",
    "artist",
    "bits_per_sample",
    "brightness_value",
    "color_space",
    "compression",
    "contrast",
    "copyright",
    "custom_rendered",
    "digital_zoom_ratio",
    "_exif_ifd_pointer",
    "exif_version",
    "exposure_bias_value",
    "exposure_mode",
    "exposure_program",
    "exposure_time",
    "flash",
    "f_number",
    "focal_length",
    "focal_length_in_35mm_film",
    "focal_plane_resolution_unit",
    "focal_plane_x_resolution",
    "focal_plane_y_resolution",
    "gain_control",
    "_gps_ifd_pointer",
    "gps_version_id",
    "image_height",
    "image_unique_id",
    "image_width",
    "jpeg_interchange_format",
    "jpeg_interchange_format_length",
    "lens_make",
    "lens_model",
    "lens_serial_number",
    "lens_specification",
    "light_source",
    "max_aperture_value",
    "metering_mode",
    "orientation",
    "photographic_sensitivity",
    "photometric_interpretation",
    "pixel_x_dimension",
    "pixel_y_dimension",
    "planar_configuration",
    "recommended_exposure_index",
    "resolution_unit",
    "samples_per_pixel",
    "saturation",
    "scene_capture_type",
    "sensing_method",
    "sensitivity_type",
    "sharpness",
    "shutter_speed_value",
    "subject_area",
    "subject_distance_range",
    "subsec_time",
    "subsec_time_digitized",
    "subsec_time_original",
    "user_comment",
    "white_balance",
    "x_resolution",
    "y_and_c_positioning",
    "y_resolution",
]

EXTRACT_TAGS = [
    "body_serial_number",
    "datetime",
    "datetime_digitized",
    "datetime_original",
    "gps_altitude",
    "gps_altitude_ref",
    "gps_datestamp",
    "gps_dest_bearing",
    "gps_dest_bearing_ref",
    "gps_horizontal_positioning_error",
    "gps_img_direction",
    "gps_img_direction_ref",
    "gps_latitude",
    "gps_latitude_ref",
    "gps_longitude",
    "gps_longitude_ref",
    "gps_speed",
    "gps_speed_ref",
    "gps_timestamp",
    "make",
    "model",
    "offset_time",
    "offset_time_digitized",
    "offset_time_original",
    "software",
]


class UnparsedTags:
    def __init__(self) -> None:
        self._d: t.Dict[str, t.Any] = {}

    def insert(self, key: str, value: t.Any) -> None:
        self._d[key] = value

    def get(self, key: str) -> t.Any:
        if key not in self._d:
            return None
        ret = self._d[key]
        del self._d[key]
        return ret

    def all(self) -> t.Dict[str, t.Any]:
        ret = self._d
        self._d = {}
        return ret


@dataclass
class Camera(DataClassJsonMixin):
    make: str
    model: str
    serial_number: str
    software: str

    @staticmethod
    def from_tags(tags: UnparsedTags) -> "Camera":
        return Camera(
            tags.get("make") or "",
            tags.get("model") or "",
            tags.get("body_serial_number") or "",
            tags.get("software") or "",
        )


@dataclass
class GPSCoord(DataClassJsonMixin):
    latitude: float
    longitude: float
    altitude: t.Optional[float]
    date: t.Optional[datetime]

    @staticmethod
    def from_tags(tags: UnparsedTags) -> "t.Optional[GPSCoord]":
        # TODO: distinguish missing vs wrong
        altitude_ref = 1 if tags.get("gps_altitude_ref") == exif.GpsAltitudeRef.ABOVE_SEA_LEVEL else -1
        latitude_ref = 1 if tags.get("gps_latitude_ref") == "N" else -1
        longitude_ref = 1 if tags.get("gps_longitude_ref") == "E" else -1
        latitude = loc_to_number(tags.get("gps_latitude"))
        longitude = loc_to_number(tags.get("gps_longitude"))
        altitude = loc_to_number(tags.get("gps_altitude"))
        date = gps_to_datetime(tags.get("gps_datestamp"), tags.get("gps_timestamp"))

        if latitude is None or longitude is None:
            return None

        # TODO
        # https://exiftool.org/TagNames/GPS.html
        tags.get("gps_speed_ref")
        tags.get("gps_speed")
        tags.get("gps_img_direction_ref")
        tags.get("gps_img_direction")
        tags.get("gps_dest_bearing_ref")
        tags.get("gps_dest_bearing")
        tags.get("gps_horizontal_positioning_error")

        return GPSCoord(
            latitude * latitude_ref,
            longitude * longitude_ref,
            altitude * altitude_ref if altitude is not None else None,
            date,
        )
        pass


def gps_to_datetime(
    date: t.Optional[str], time: t.Optional[t.Tuple[float, float, float]]
) -> t.Optional[datetime]:
    if date is None:
        return None
    try:
        y, m, d = [int(x) for x in date.split(":")]
        if time is None:
            return datetime(y, m, d)
        h, mn, s = [int(x) for x in time]
        return datetime(y, m, d, h, mn, s)
    except:
        return None


def loc_to_number(x: t.Any) -> t.Optional[float]:
    if type(x) != tuple:
        return None
    if len(x) != 3:
        return None
    a, b, c = x
    ret = a + b / 60 + c / 3600
    if ret == 0:
        return None
    return float(ret)


@dataclass
class Date(DataClassJsonMixin):
    datetime: t.Optional[datetime]
    time_str: t.Optional[str]

    @staticmethod
    def from_tags(t: UnparsedTags) -> "t.Optional[Date]":
        datetime = parse_datetime(t.get("datetime"), t.get("offset_time"))
        datetime_digitized = parse_datetime(t.get("datetime_digitized"), t.get("offset_time_digitized"))
        datetime_original = parse_datetime(t.get("datetime_original"), t.get("offset_time_original"))
        date = datetime_original or datetime_digitized or datetime
        if date is None:
            return None
        return Date(date, date.isoformat())


def parse_datetime(s: t.Optional[str], offset: t.Optional[str]) -> t.Optional[datetime]:
    if s is None:
        return None

    td = timedelta()
    if offset is not None:
        try:
            h, m = [int(x) for x in offset.split(":")]
            td = timedelta(0, m * 60 + h * 3600)
        except:
            pass

    try:
        return datetime.strptime(s, "%Y:%m:%d %H:%M:%S") - td
    except:
        pass
    return None


VERSION = 0


@dataclass
class ImageExif(HasImage):
    image: str
    version: int
    gps: t.Optional[GPSCoord]
    camera: Camera
    date: t.Optional[Date]

    @staticmethod
    def current_version() -> int:
        return VERSION


class Exif:
    def __init__(self, cache: Cache[ImageExif]) -> None:
        self._cache = cache

    def process_image(self, path: str) -> ImageExif:
        ret = self._cache.get(path)
        if ret is not None:
            return ret
        return self._cache.add(self.process_image_impl(path))

    def process_image_impl(self: "Exif", path: str) -> ImageExif:
        img = exif.Image(path)
        d = UnparsedTags()
        for tag in img.list_all():
            if tag in IGNORED_TAGS:
                continue
            # Just temporary until I find all the tags
            value = img.get(tag)
            if value is None:
                continue
            if tag not in EXTRACT_TAGS:
                print("ERR: UNKNOWN TAG", tag, value, file=sys.stderr)
            d.insert(tag, value)

        gps = GPSCoord.from_tags(d)
        camera = Camera.from_tags(d)
        date = Date.from_tags(d)

        for tag, value in d.all().items():
            print("ERR: unprocessed tag", tag, value, type(value), file=sys.stderr)

        return ImageExif(path, VERSION, gps, camera, date)
