import os
import sys
import glob
import re
import typing as t

from tqdm import tqdm

from image_to_text import Models, ImageClassification
from image_exif import Exif, ImageExif
from md5_annot import MD5er, MD5Annot
from geolocation import Geolocator, GeoAddress
from cache import JsonlCache
from filename_to_date import PathDateExtractor
from config import Config

VERSION = 0


def walk_tree(path: str, extensions: t.Optional[t.List[str]] = None) -> t.Iterable[str]:
    if extensions is None:
        extensions = ["jpg", "jpeg", "JPG", "JEPG"]
    for directory, _subdirs, files in os.walk(path):
        yield from (f"{directory}/{file}" for file in files if file.split(".")[-1] in extensions)


def main() -> None:
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

    paths = [
        file
        for pattern in tqdm(config.input_patterns, desc="Listing files")
        for file in glob.glob(re.sub("^~/", os.environ["HOME"] + "/", pattern))
    ]
    for directory in tqdm(config.input_directories, desc="Listing directories"):
        paths.extend(walk_tree(re.sub("^~/", os.environ["HOME"] + "/", directory)))

    def process_path(path: str, skip_image_to_text: bool) -> t.Any:
        exif_item = exif.process_image(path)
        geo = None
        if exif_item.gps is not None:
            geo = geolocator.address(
                path, exif_item.gps.latitude, exif_item.gps.longitude, recompute=exif_item.changed()
            )
        if skip_image_to_text:
            itt = None
        else:
            itt = list(models.process_image_batch([path]))[0]
        md5hsh = md5.process(path)
        path_date = path_to_date.extract_date(path)
        return (path, md5hsh, exif_item, geo, itt, path_date)

    try:
        for path in tqdm(paths, total=len(paths), desc="Cheap features"):
            try:
                img = process_path(path, skip_image_to_text=True)
            except Exception as e:
                print("Error while processing path", path, e, file=sys.stderr)
        print(img)
        for path in tqdm(paths, total=len(paths), desc="Expensive features"):
            try:
                img = process_path(path, skip_image_to_text=False)
            except Exception as e:
                print("Error while processing path", path, e, file=sys.stderr)
        print(img)
    finally:
        del models_cache
        del exif_cache
        del geolocator_cache
        del md5_cache


if __name__ == "__main__":
    main()
