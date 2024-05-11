from dataclasses_json import DataClassJsonMixin
from cache import HasImage
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
    def __init__(self) -> None:
        pass

    def process(self, image: str) -> MD5Annot:
        return MD5Annot(image, VERSION, hashlib.md5(open("output-exif.jsonl", "rb").read()).hexdigest())
