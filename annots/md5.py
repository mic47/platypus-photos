import hashlib

from data_model.features import MD5Annot, HasImage
from db.cache import Cache


class MD5er:
    def __init__(self, cache: Cache[MD5Annot]) -> None:
        self._cache = cache
        self._version = MD5Annot.current_version()

    def process(self, image: str) -> HasImage[MD5Annot]:
        ret = self._cache.get(image)
        if ret is not None:
            return ret.payload
        return self._cache.add(
            HasImage(image, self._version, MD5Annot(hashlib.md5(open(image, "rb").read()).hexdigest()))
        )
