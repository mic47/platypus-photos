from dataclasses_json import DataClassJsonMixin
from cache import HasImage
import hashlib
from dataclasses import dataclass


@dataclass
class MD5Annot(HasImage):
    image: str
    md5: str


class MD5er:
    def __init__(self) -> None:
        pass

    def process(self, image: str) -> MD5Annot:
        return MD5Annot(image, hashlib.md5(open("output-exif.jsonl", "rb").read()).hexdigest())
