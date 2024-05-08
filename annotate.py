import sys
from tqdm import tqdm
import itertools
import typing as t
from dataclasses_json import dataclass_json
from dataclasses import dataclass

from image_to_text import Models, ImageClassification
from image_exif import Exif, ImageExif
from geolocation import Geolocator, GeoAddress
from cache import JsonlCache


@dataclass_json
@dataclass
class ImageAnnotations:
    image: str
    exif: ImageExif
    address: t.Optional[GeoAddress]
    text_classification: t.Optional[ImageClassification]


if __name__ == "__main__":
    models = Models()
    exif = Exif()
    geolocator = Geolocator()
    paths = sys.argv[1:]
    itt_cache = JsonlCache("output-image-to-text.jsonl", ImageClassification, ["output.jsonl"])
    exif_cache = JsonlCache("output-exif.jsonl", ImageExif)
    geo_cache = JsonlCache("output-geo.jsonl", GeoAddress)

    try:
        for path in tqdm(paths, total=len(paths), desc="Image batches"):
            exif_item_m = exif_cache.get(path)
            if exif_item_m is None:
                exif_item = list(exif.process_image_batch([path]))[0]
                exif_cache.add(exif_item)
            else:
                # Because typecheck
                exif_item = exif_item_m
            if exif_item.gps is not None:
                geo = geo_cache.get(path)
                if geo is None:
                    geo = geolocator.address(path, exif_item.gps.latitude, exif_item.gps.longitude)
                    geo_cache.add(geo)
            itt = itt_cache.get(path)
            if itt is None:
                itt = list(models.process_image_batch([path]))[0]
                itt_cache.add(itt)
        img = ImageAnnotations(path, exif_item, geo, itt)
        print(img)
    finally:
        del itt_cache
        del exif_cache
        del geo_cache
