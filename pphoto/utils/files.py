import enum
import glob
import os
import re
import typing as t

from pphoto.utils.typing_support import assert_never


class SupportedMedia(enum.Enum):
    JPEG = 0
    PNG = 1
    GIF = 2
    WEBP = 3
    MP4 = 4
    MOV = 5
    AVI = 6
    WMV = 7
    WEBM = 8
    BMP = 9
    MP3 = 10
    M4A = 11


class SupportedMediaClass(enum.Enum):
    IMAGE = 0
    VIDEO = 1
    AUDIO = 2


_EXTENSIONS = {
    "jpg": SupportedMedia.JPEG,
    "jpeg": SupportedMedia.JPEG,
    "png": SupportedMedia.PNG,
    "gif": SupportedMedia.GIF,
    "webp": SupportedMedia.WEBP,
    "bmp": SupportedMedia.BMP,
    "mp4": SupportedMedia.MP4,
    "mov": SupportedMedia.MOV,
    "avi": SupportedMedia.AVI,
    "wmv": SupportedMedia.WMV,
    "webm": SupportedMedia.WEBM,
    "mp3": SupportedMedia.MP3,
    "m4a": SupportedMedia.M4A,
}


def supported_media(path: str) -> t.Optional[SupportedMedia]:
    extension = path.rsplit(".", 1)[-1].lower()
    return _EXTENSIONS.get(extension)


def supported_media_class(path: str) -> t.Optional[SupportedMediaClass]:
    media = supported_media(path)
    if (
        # pylint: disable-next = consider-using-in
        media == SupportedMedia.JPEG
        or media == SupportedMedia.PNG
        or media == SupportedMedia.GIF
        or media == SupportedMedia.WEBP
        or media == SupportedMedia.BMP
    ):
        return SupportedMediaClass.IMAGE
    if (
        # pylint: disable-next = consider-using-in
        media == SupportedMedia.MP4
        or media == SupportedMedia.MOV
        or media == SupportedMedia.AVI
        or media == SupportedMedia.WMV
        or media == SupportedMedia.WEBM
    ):
        return SupportedMediaClass.VIDEO
    if (
        # pylint: disable-next = consider-using-in
        media == SupportedMedia.M4A
        or media == SupportedMedia.MP3
    ):
        return SupportedMediaClass.AUDIO
    if media is None:
        return None
    assert_never(media)


def walk_tree(path: str) -> t.Iterable[str]:
    for directory, _subdirs, files in os.walk(path):
        yield from (f"{directory}/{file}" for file in files if supported_media(file) is not None)


def get_paths(input_patterns: t.List[str], input_directories: t.List[str]) -> t.Iterable[str]:
    for pattern in input_patterns:
        yield from glob.glob(expand_vars_in_path(pattern))
    for directory in input_directories:
        yield from walk_tree(expand_vars_in_path(directory))


def expand_vars_in_path(path: str) -> str:
    return re.sub("^~/", os.environ["HOME"] + "/", path)


REMOVE_FROM_PATH_PART = re.compile(r"[^-:\w]+")


def pathify(path: str) -> str:
    return REMOVE_FROM_PATH_PART.sub("_", path)
