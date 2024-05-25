import json
import time
import sys
import typing as t

from geopy.distance import distance
from geopy.geocoders import Nominatim

from data_model.features import GeoAddress, POI, NearestPOI
from db.cache import Cache


RATE_LIMIT_SECONDS = 1
RETRIES = 10


class Geolocator:
    def __init__(self, cache: Cache[GeoAddress]) -> None:
        self._cache = cache
        self.geolocator = Nominatim(user_agent="Mic's photo lookups")
        self.last_api = time.time() - 10
        self._version = GeoAddress.current_version()

    def address(self, image: str, lat: float, lon: float, recompute: bool = False) -> GeoAddress:
        ret = self._cache.get(image)
        if ret is not None and not recompute:
            return ret
        return self._cache.add(self.address_impl(image, lat, lon))

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
            # pylint: disable = broad-exception-caught
            except Exception as e:
                if retries_left <= 0:
                    raise
                print(
                    f"Gelolocation request for {image} failed. Retrying ({retries_left} left)",
                    e,
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
        # pylint: disable = broad-exception-caught
        except Exception as _:
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
        return GeoAddress(image, self._version, ret.address, country, name, raw_data, query)


class POIDetector:
    def __init__(self, pois: t.Iterable[POI]):
        self._max_distance = 0.25
        self._pois = list(pois)
        self._version = NearestPOI.current_version()

    def find(self, image: str, latitude: float, longitude: float) -> t.Optional[NearestPOI]:
        if not self._pois:
            return None
        best = min(
            ((distance((poi.latitude, poi.longitude), (latitude, longitude)), poi) for poi in self._pois),
            key=lambda x: t.cast(float, x[0]),
        )
        best_distance, poi = best
        if best_distance > self._max_distance:
            return None
        return NearestPOI(image, self._version, poi, best_distance)
