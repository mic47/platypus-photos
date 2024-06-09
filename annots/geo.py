import json
import time
import sys

from geopy.geocoders import Nominatim

from data_model.features import GeoAddress, WithMD5, PathWithMd5
from db.cache import Cache


RATE_LIMIT_SECONDS = 1
RETRIES = 10


class Geolocator:
    def __init__(self, cache: Cache[GeoAddress]) -> None:
        self.cache = cache
        self.geolocator = Nominatim(user_agent="Mic's photo lookups")
        self.last_api = time.time() - 10
        self._version = GeoAddress.current_version()

    def address(
        self, inp: PathWithMd5, lat: float, lon: float, recompute: bool = False
    ) -> WithMD5[GeoAddress]:
        ret = self.cache.get(inp.md5)
        if ret is not None and ret.payload is not None and not recompute:
            return ret.payload
        return self.cache.add(self.address_impl(inp, lat, lon))

    def address_impl(self, inp: PathWithMd5, lat: float, lon: float) -> WithMD5[GeoAddress]:
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
                    # This is valid case of transient error, we raise exception
                    raise
                print(
                    f"Gelolocation request for {inp.path} {inp.md5} failed. Retrying ({retries_left} left)",
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
        return WithMD5(inp.md5, self._version, GeoAddress(ret.address, country, name, raw_data, query), None)
