from __future__ import annotations

from datetime import datetime, timedelta
import sys
import traceback
import typing as t

import exif
import exiftool

from pphoto.data_model.base import WithMD5, PathWithMd5, Error
from pphoto.data_model.exif import ImageExif, Date, Camera, GPSCoord, VideoInfo
from pphoto.db.types import Cache
from pphoto.utils.files import SupportedMedia, supported_media, supported_media_class, SupportedMediaClass
from pphoto.utils import assert_never

IGNORED_IMAGE_TAGS = [
    "aperture_value",
    "artist",
    "bits_per_sample",
    "brightness_value",
    "color_space",
    "components_configuration",
    "compressed_bits_per_pixel",
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
    "flashpix_version",
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
    "scene_type",
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
    # TODO: consider in future
    "image_description",
    "camera_owner_name",
]

EXTRACT_IMAGE_TAGS = [
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

IGNORED_VIDEO_TAGS = [
    "Composite:AvgBitrate",
    "Composite:GPSPosition",
    "Composite:ImageSize",
    "Composite:Megapixels",
    "Composite:Rotation",
    "ExifTool:ExifToolVersion",
    "File:Directory",
    "File:FileAccessDate",
    "File:FileInodeChangeDate",
    "File:FileModifyDate",
    "File:FileName",
    "File:FilePermissions",
    "File:FileSize",
    "File:FileType",
    "File:FileTypeExtension",
    "File:MIMEType",
    "QuickTime:AndroidCaptureFPS",
    "QuickTime:AndroidVersion",
    "QuickTime:AudioBitsPerSample",
    "QuickTime:AudioChannels",
    "QuickTime:AudioFormat",
    "QuickTime:AudioSampleRate",
    "QuickTime:Balance",
    "QuickTime:BitDepth",
    "QuickTime:ColorPrimaries",
    "QuickTime:ColorProfiles",
    "QuickTime:CompatibleBrands",
    "QuickTime:CompressorID",
    "QuickTime:CurrentTime",
    "QuickTime:GPSCoordinates",
    "QuickTime:GraphicsMode",
    "QuickTime:HandlerDescription",
    "QuickTime:HandlerType",
    "QuickTime:ImageHeight",
    "QuickTime:ImageWidth",
    "QuickTime:MajorBrand",
    "QuickTime:MatrixCoefficients",
    "QuickTime:MatrixStructure",
    "QuickTime:MediaDataOffset",
    "QuickTime:MediaDataSize",
    "QuickTime:MediaHeaderVersion",
    "QuickTime:MediaModifyDate",
    "QuickTime:MediaTimeScale",
    "QuickTime:MinorVersion",
    "QuickTime:ModifyDate",
    "QuickTime:MovieHeaderVersion",
    "QuickTime:NextTrackID",
    "QuickTime:OpColor",
    "QuickTime:PlayMode",
    "QuickTime:PosterTime",
    "QuickTime:PreferredRate",
    "QuickTime:PreferredVolume",
    "QuickTime:PreviewDuration",
    "QuickTime:PreviewTime",
    "QuickTime:SelectionDuration",
    "QuickTime:SelectionTime",
    "QuickTime:SourceImageHeight",
    "QuickTime:SourceImageWidth",
    "QuickTime:TimeScale",
    "QuickTime:TrackHeaderVersion",
    "QuickTime:TrackID",
    "QuickTime:TrackLayer",
    "QuickTime:TrackModifyDate",
    "QuickTime:TrackVolume",
    "QuickTime:TransferCharacteristics",
    "QuickTime:VideoFullRangeFlag",
    "QuickTime:XResolution",
    "QuickTime:YResolution",
    "SourceFile",
]

EXTRACT_VIDEO_TAGS = [
    "Composite:GPSLatitude",
    "Composite:GPSLongitude",
    "MakerNotes:SamsungModel",
    "QuickTime:Author",
    "QuickTime:CreateDate",
    "QuickTime:Duration",
    "QuickTime:MediaCreateDate",
    "QuickTime:MediaDuration",
    "QuickTime:TrackCreateDate",
    "QuickTime:TrackDuration",
    "QuickTime:VideoFrameRate",
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

    def get_first(self, *keys: str) -> t.Any:
        values = [self.get(key) for key in keys]
        for value in values:
            if value is not None or value != "":
                return value
        return None

    def all(self) -> t.Dict[str, t.Any]:
        ret = self._d
        self._d = {}
        return ret


def camera_from_image_tags(tags: UnparsedTags) -> Camera:
    return Camera(
        tags.get("make") or "",
        tags.get("model") or "",
        tags.get("body_serial_number") or "",
        tags.get("software") or "",
    )


def camera_from_video_tags(tags: UnparsedTags) -> Camera:
    make, model = None, None
    author = tags.get("QuickTime:Author")
    if author is not None and isinstance(author, str):
        x = author.lower().split(" ", maxsplit=1)
        if len(x) == 2 and x[0] in ["samsung"]:
            make, model = x
    if model is None:
        x = tags.get("MakerNotes:SamsungModel")
        if x is not None and isinstance(x, str):
            make = "samsung"
            model = x
    return Camera(
        make or "",
        model or "",
        "",
        "",
    )


def gpscoord_from_video_tags(tags: UnparsedTags) -> t.Optional[GPSCoord]:
    latitude = tags.get("Composite:GPSLatitude")
    longitude = tags.get("Composite:GPSLongitude")
    return GPSCoord(
        latitude,
        longitude,
        None,
        None,
    )


def date_from_video_tags(tags: UnparsedTags) -> t.Optional[Date]:
    datetime_base = tags.get_first(
        "QuickTime:MediaCreateDate", "QuickTime:TrackCreateDate", "QuickTime:CreateDate"
    )
    datetime_parts = datetime_base.split(" ")
    if len(datetime_parts) != 2:
        return None
    date_parts, time_parts = datetime_parts[0].split(":"), datetime_parts[1].split(":")
    if len(date_parts) != 3 or len(time_parts) != 3:
        return None
    try:
        date_ = datetime(
            int(date_parts[0]),
            int(date_parts[1]),
            int(date_parts[2]),
            int(time_parts[0]),
            int(time_parts[1]),
            int(time_parts[2]),
        )

        return Date(date_, date_.isoformat())
    # pylint: disable-next = broad-exception-caught
    except Exception as _:
        return None


def video_info_from_video_tags(tags: UnparsedTags) -> t.Optional[VideoInfo]:
    frame_rate = tags.get("QuickTime:VideoFrameRate")
    duration_seconds = tags.get_first(
        "QuickTime:Duration", "QuickTime:MediaDuration", "QuickTime:TrackDuration"
    )
    if frame_rate is not None or duration_seconds is not None:
        return VideoInfo(frame_rate, duration_seconds)
    return None


def gpscoord_from_image_tags(tags: UnparsedTags) -> t.Optional[GPSCoord]:
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
    # pylint: disable-next = broad-exception-caught
    except Exception as _:
        return None


def loc_to_number(x: t.Any) -> t.Optional[float]:
    if not isinstance(x, tuple):
        return None
    if len(x) != 3:
        return None
    a, b, c = x
    ret = a + b / 60 + c / 3600
    if ret == 0:
        return None
    return float(ret)


def date_from_image_tags(ut: UnparsedTags) -> t.Optional[Date]:
    datetime_ = parse_datetime(ut.get("datetime"), ut.get("offset_time"))
    datetime_digitized = parse_datetime(ut.get("datetime_digitized"), ut.get("offset_time_digitized"))
    datetime_original = parse_datetime(ut.get("datetime_original"), ut.get("offset_time_original"))
    date_ = datetime_original or datetime_digitized or datetime_
    if date_ is None:
        return None
    return Date(date_, date_.isoformat())


def parse_datetime(s: t.Optional[str], offset: t.Optional[str]) -> t.Optional[datetime]:
    if s is None:
        return None

    td = timedelta()
    if offset is not None:
        try:
            h, m = [int(x) for x in offset.split(":")]
            td = timedelta(0, m * 60 + h * 3600)
        # pylint: disable-next = broad-exception-caught
        except Exception as _:
            pass

    try:
        return datetime.strptime(s, "%Y:%m:%d %H:%M:%S") - td
    # pylint: disable-next = broad-exception-caught
    except Exception as _:
        pass
    return None


class Exif:
    def __init__(self, cache: Cache[ImageExif]) -> None:
        self._cache = cache
        self._version = ImageExif.current_version()
        self._exiftool = exiftool.ExifToolHelper()

    def process_file(self, inp: PathWithMd5) -> WithMD5[ImageExif]:
        ret = self._cache.get(inp.md5)
        if ret is not None and ret.payload is not None:
            return ret.payload
        media = supported_media(inp.path)
        media_class = supported_media_class(inp.path)
        if media_class is None or (
            media_class != SupportedMediaClass.VIDEO
            and (media_class == SupportedMediaClass.IMAGE and media != SupportedMedia.JPEG)
        ):
            ex: WithMD5[ImageExif] = WithMD5(
                inp.md5, self._version, None, Error("UnsupportedMedia", None, None)
            )
        else:
            if media_class == SupportedMediaClass.IMAGE:
                ex = self.process_image_impl(inp)
            elif media_class == SupportedMediaClass.VIDEO:
                ex = self.process_video_impl(inp)
            else:
                assert_never(media_class)
        return self._cache.add(ex)

    def process_video_impl(self: Exif, inp: PathWithMd5) -> WithMD5[ImageExif]:
        try:
            video_tags = self._exiftool.get_metadata(
                "/home/mic/Pictures/20240916_065356.mp4", params=["-c", "%.10f"]
            )[0]
        # pylint: disable-next = broad-exception-caught
        except Exception as e:
            traceback.print_exc()
            print("Error while processing exif path in ", inp, e, file=sys.stderr)
            return WithMD5(inp.md5, self._version, None, Error.from_exception(e))
        d = UnparsedTags()
        for tag, value in video_tags.items():
            if tag in IGNORED_VIDEO_TAGS:
                continue
            if value is None:
                continue
            if tag not in EXTRACT_VIDEO_TAGS:
                print("ERR: UNKNOWN VIDEO TAG", tag, value, file=sys.stderr)
            d.insert(tag, value)

        gps = gpscoord_from_video_tags(d)
        camera = camera_from_video_tags(d)
        date = date_from_video_tags(d)
        video_info = video_info_from_video_tags(d)

        for tag, value in d.all().items():
            print("ERR: unprocessed tag", tag, value, type(value), file=sys.stderr)

        return WithMD5(inp.md5, self._version, ImageExif(gps, camera, date, video_info), None)

    def process_image_impl(self: Exif, inp: PathWithMd5) -> WithMD5[ImageExif]:
        try:
            img = exif.Image(inp.path)
        # pylint: disable-next = broad-exception-caught
        except Exception as e:
            traceback.print_exc()
            print("Error while processing exif path in ", inp, e, file=sys.stderr)
            return WithMD5(inp.md5, self._version, None, Error.from_exception(e))
        d = UnparsedTags()
        for tag in img.list_all():
            if tag in IGNORED_IMAGE_TAGS:
                continue
            # Just temporary until I find all the tags
            value = img.get(tag)
            if value is None:
                continue
            if tag not in EXTRACT_IMAGE_TAGS:
                print("ERR: UNKNOWN IMAGE TAG", tag, value, file=sys.stderr)
            d.insert(tag, value)

        gps = gpscoord_from_image_tags(d)
        camera = camera_from_image_tags(d)
        date = date_from_image_tags(d)

        for tag, value in d.all().items():
            print("ERR: unprocessed tag", tag, value, type(value), file=sys.stderr)

        return WithMD5(inp.md5, self._version, ImageExif(gps, camera, date, None), None)
