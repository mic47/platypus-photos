from __future__ import annotations

import os
import sys
import traceback

from PIL import Image, ImageFile
from ffmpeg import probe

from pphoto.data_model.base import WithMD5, PathWithMd5, Error
from pphoto.data_model.dimensions import ImageDimensions
from pphoto.db.types import Cache
from pphoto.utils.files import supported_media_class, SupportedMediaClass
from pphoto.utils import assert_never

ImageFile.LOAD_TRUNCATED_IMAGES = True


class Dimensions:
    def __init__(self, cache: Cache[ImageDimensions]) -> None:
        self._cache = cache
        self._version = ImageDimensions.current_version()

    def process_file(self, inp: PathWithMd5) -> WithMD5[ImageDimensions]:
        ret = self._cache.get(inp.md5)
        if ret is not None and ret.payload is not None:
            return ret.payload
        media_class = supported_media_class(inp.path)
        if media_class is None:
            ex: WithMD5[ImageDimensions] = WithMD5(
                inp.md5, self._version, None, Error("UnsupportedMedia", None, None)
            )
        else:
            try:
                file_size = os.path.getsize(inp.path)
            # pylint: disable-next = broad-exception-caught
            except Exception as e:
                traceback.print_exc()
                print("Error while processing dimensions path in ", inp, e, file=sys.stderr)
                return WithMD5(inp.md5, self._version, None, Error.from_exception(e))

            if media_class == SupportedMediaClass.IMAGE:
                ex = self.process_image_impl(inp, file_size)
            elif media_class == SupportedMediaClass.VIDEO:
                ex = self.process_video_impl(inp, file_size)
            else:
                assert_never(media_class)
        return self._cache.add(ex)

    def process_image_impl(self: Dimensions, inp: PathWithMd5, file_size: int) -> WithMD5[ImageDimensions]:
        try:
            image = Image.open(inp.path)
            width, height = image.size
        # pylint: disable-next = broad-exception-caught
        except Exception as e:
            traceback.print_exc()
            print("Error while processing dimensions path in ", inp, e, file=sys.stderr)

        return WithMD5(inp.md5, self._version, ImageDimensions(width, height, file_size), None)

    def process_video_impl(self: Dimensions, inp: PathWithMd5, file_size: int) -> WithMD5[ImageDimensions]:
        try:
            width, height = max(
                (p["width"], p["height"])
                for p in probe(inp.path)["streams"]
                if p.get("codec_type") == "video"
            )
        # pylint: disable-next = broad-exception-caught
        except Exception as e:
            traceback.print_exc()
            print("Error while processing dimensions path in ", inp, e, file=sys.stderr)

        return WithMD5(inp.md5, self._version, ImageDimensions(width, height, file_size), None)
