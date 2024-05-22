from dataclasses import dataclass
import hashlib

from cache import HasImage, Cache


@dataclass
class MD5Annot(HasImage):
    image: str
    version: int
    md5: str

    @staticmethod
    def current_version() -> int:
        return 1


class MD5er:
    def __init__(self, cache: Cache[MD5Annot]) -> None:
        self._cache = cache
        self._version = MD5Annot.current_version()

    def process(self, image: str) -> MD5Annot:
        ret = self._cache.get(image)
        if ret is not None:
            return ret
        return self._cache.add(
            MD5Annot(image, self._version, hashlib.md5(open(image, "rb").read()).hexdigest())
        )
