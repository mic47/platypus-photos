from geopy.distance import distance
from geopy.geocoders import Nominatim
from dataclasses_json import DataClassJsonMixin
from dataclasses import dataclass
import json
import time
import sys
import typing as t

from cache import HasImage, Cache

VERSION = 0


@dataclass
class GeoAddress(HasImage):
    image: str
    address: str
    country: t.Optional[str]
    name: t.Optional[str]
    raw: str
    query: str
    # TODO: add points of interestis -- i.e. home, work, ...

    @staticmethod
    def current_version() -> int:
        return VERSION


RATE_LIMIT_SECONDS = 1
RETRIES = 10


class Geolocator:
    def __init__(self, cache: Cache[GeoAddress]) -> None:
        self._cache = cache
        self.geolocator = Nominatim(user_agent="Mic's photo lookups")
        self.last_api = time.time() - 10

    def address(self, image: str, lat: float, lon: float) -> GeoAddress:
        ret = self._cache.get(image)
        if ret is not None:
            return ret
        return self.address_impl(image, lat, lon)

    def address_impl(self, image: str, lat: float, lon: float) -> GeoAddress:
        now = time.time()
        from_last_call = max(0, now - self.last_api)
        if from_last_call < RATE_LIMIT_SECONDS:
            time.sleep(RATE_LIMIT_SECONDS - from_last_call)
        retries_left = RETRIES
        query = f"{lat}, {lon}"
        while True:
            try:
                ret = self.geolocator.reverse(query, language="en")
                break
            except:
                if retries_left <= 0:
                    raise
                print(
                    f"Gelolocation request for {image} failed. Retrying ({retries_left} left)",
                    file=sys.stderr,
                )
                retries_left -= 1
                time.sleep(10)
        self.last_api = time.time()
        country = None
        name = None
        raw_add = ret.raw.get("address")
        try:
            raw_data = json.dumps(ret.raw, ensure_ascii=False)
        except:
            raw_data = str(ret.raw)
        if raw_add is not None:
            name = (
                str(
                    raw_add.get("city")
                    or raw_add.get("village")
                    or raw_add.get("town")
                    or ret.raw.get("name")
                )
                or None  # In case of empty string
            )
            country = raw_add.get("country")
        return GeoAddress(image, VERSION, ret.address, country, name, raw_data, query)


@dataclass
class POI(DataClassJsonMixin):
    name: str
    latitude: float
    longitude: float


@dataclass
class NearestPOI(HasImage):
    image: str
    poi: POI
    distance: float


class POIDetector:
    def __init__(self, pois: t.Iterable[POI]):
        self._max_distance = 0.25
        self._pois = list(pois)

    def find(self, image: str, latitude: float, longitude: float) -> t.Optional[NearestPOI]:
        if not self._pois:
            return None
        best = min(
            [(distance((poi.latitude, poi.longitude), (latitude, longitude)), poi) for poi in self._pois],
            key=lambda x: t.cast(float, x[0]),
        )
        distance, poi = best
        if distance > self._max_distance:
            return None
        return NearestPOI(image, VERSION, poi, distance)
