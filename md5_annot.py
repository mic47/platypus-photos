from dataclasses_json import DataClassJsonMixin
from cache import HasImage, Cache
import hashlib
from dataclasses import dataclass

VERSION = 0


@dataclass
class MD5Annot(HasImage):
    image: str
    version: int
    md5: str

    @staticmethod
    def current_version() -> int:
        return VERSION


class MD5er:
    def __init__(self, cache: Cache[MD5Annot]) -> None:
        self._cache = cache

    def process(self, image: str) -> MD5Annot:
        ret = self._cache.get(image)
        if ret is not None:
            return ret
        return self._cache.add(
            MD5Annot(image, VERSION, hashlib.md5(open("output-exif.jsonl", "rb").read()).hexdigest())
        )
