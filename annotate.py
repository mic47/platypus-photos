import os
import glob
import re
import itertools
import typing as t
from datetime import datetime

from tqdm import tqdm
from dataclasses_json import dataclass_json
from dataclasses import dataclass

from image_to_text import Models, ImageClassification
from image_exif import Exif, ImageExif
from md5_annot import MD5er, MD5Annot
from geolocation import Geolocator, GeoAddress
from cache import JsonlCache, HasImage
from filename_to_date import PathDateExtractor
from config import Config

VERSION = 0


@dataclass
class ImageAnnotations(HasImage):
    image: str
    version: int
    md5: str
    exif: ImageExif
    address: t.Optional[GeoAddress]
    text_classification: t.Optional[ImageClassification]
    date_from_path: t.Optional[datetime]

    @staticmethod
    def current_version() -> int:
        return VERSION


if __name__ == "__main__":
    config = Config.load("config.yaml")

    path_to_date = PathDateExtractor(config.directory_matching)

    models_cache = JsonlCache("output-image-to-text.jsonl", ImageClassification)
    models = Models(models_cache)

    exif_cache = JsonlCache("output-exif.jsonl", ImageExif)
    exif = Exif(exif_cache)

    geolocator_cache = JsonlCache("output-geo.jsonl", GeoAddress)
    geolocator = Geolocator(geolocator_cache)

    md5 = MD5er()
    md5_cache = JsonlCache("output-md5.jsonl", MD5Annot)

    paths = [
        file
        for pattern in tqdm(config.input_patterns, desc="Listing files")
        for file in glob.glob(re.sub("^~/", os.environ["HOME"] + "/", pattern))
    ]

    try:
        for path in tqdm(paths, total=len(paths), desc="Image batches"):
            exif_item = exif.process_image(path)
            geo = None
            if exif_item.gps is not None:
                geo = geolocator.address(path, exif_item.gps.latitude, exif_item.gps.longitude)
            itt = list(models.process_image_batch([path]))[0]
            md5hsh_ret = md5_cache.get(path)
            if md5hsh_ret is None:
                md5hsh = md5.process(path)
                md5_cache.add(md5hsh)
            else:
                md5hsh = md5hsh_ret
            path_date = path_to_date.extract_date(path)
            img = ImageAnnotations(path, VERSION, md5hsh.md5, exif_item, geo, itt, path_date)
        print(img)
    finally:
        del models_cache
        del exif_cache
        del geolocator_cache
        del md5_cache
