import enum
import glob
import os
import re
import typing as t


class SupportedMedia(enum.Enum):
    JPEG = 0
    PNG = 1
    GIF = 2
    WEBP = 3
    # VIDEO = 1 TODO


_EXTENSIONS = {
    "jpg": SupportedMedia.JPEG,
    "jpeg": SupportedMedia.JPEG,
    "png": SupportedMedia.PNG,
    "gif": SupportedMedia.GIF,
    "webp": SupportedMedia.WEBP,
}


def supported_media(path: str) -> t.Optional[SupportedMedia]:
    extension = path.rsplit(".", 1)[-1].lower()
    return _EXTENSIONS.get(extension)


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
