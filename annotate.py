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
from image_annotation import ImageAnnotator, ImageAnnotations
from filename_to_date import PathDateExtractor
from config import Config

VERSION = 0


if __name__ == "__main__":
    config = Config.load("config.yaml")

    path_to_date = PathDateExtractor(config.directory_matching)

    models_cache = JsonlCache("output-image-to-text.jsonl", ImageClassification)
    models = Models(models_cache)

    exif_cache = JsonlCache("output-exif.jsonl", ImageExif)
    exif = Exif(exif_cache)

    geolocator_cache = JsonlCache("output-geo.jsonl", GeoAddress)
    geolocator = Geolocator(geolocator_cache)

    md5_cache = JsonlCache("output-md5.jsonl", MD5Annot)
    md5 = MD5er(md5_cache)

    annotator_cache = JsonlCache("output-all.jsonl", ImageAnnotations)
    annotator = ImageAnnotator(annotator_cache)

    paths = [
        file
        for pattern in tqdm(config.input_patterns, desc="Listing files")
        for file in glob.glob(re.sub("^~/", os.environ["HOME"] + "/", pattern))
    ]

    try:
        for path in tqdm(paths, total=len(paths), desc="Image batches"):
            try:
                exif_item = exif.process_image(path)
                geo = None
                if exif_item.gps is not None:
                    geo = geolocator.address(
                        path, exif_item.gps.latitude, exif_item.gps.longitude, recompute=exif_item.changed()
                    )
                itt = list(models.process_image_batch([path]))[0]
                md5hsh = md5.process(path)
                path_date = path_to_date.extract_date(path)
                img = annotator.process(path, md5hsh, exif_item, geo, itt, path_date)
            except:
                print("Error while processing path", path, file=sys.stderr)
                raise
        print(img)
    finally:
        del models_cache
        del exif_cache
        del geolocator_cache
        del md5_cache
        del annotator_cache
