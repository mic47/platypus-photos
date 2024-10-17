import json
import time
import typing as t
import sys

from geopy.geocoders import Nominatim
from geopy.location import Location

from pphoto.data_model.base import WithMD5, PathWithMd5, Error
from pphoto.data_model.geo import GeoAddress
from pphoto.db.types import Cache, NoCache


RATE_LIMIT_SECONDS = 1
RETRIES = 10


class Geolocator:
    def __init__(self, cache: t.Optional[Cache[GeoAddress]] = None) -> None:
        self.cache = cache or NoCache()
        self.geolocator = Nominatim(user_agent="Mic's photo lookups")
        self.last_api = time.time() - 10
        self._version = GeoAddress.current_version()
        self._search_cache: t.Dict[t.Tuple[str, int], t.List[Location]] = {}
        self._address_cache: t.Dict[t.Tuple[float, float], GeoAddress] = {}

    def address(
        self, inp: PathWithMd5, lat: float, lon: float, recompute: bool = False
    ) -> WithMD5[GeoAddress]:
        ret = self.cache.get(inp.md5)
        if ret is not None and ret.payload is not None and not recompute:
            return ret.payload
        return self.cache.add(self.address_impl(inp, lat, lon))

    def search(self, query: str, limit: int) -> t.List[Location]:
        key = (query, limit)
        value = self._search_cache.get(key)
        if value is not None:
            return value
        ret = self.search_impl(query, limit)
        self._search_cache[key] = ret
        return ret

    def search_impl(self, query: str, limit: int) -> t.List[Location]:
        self._rate_limit()
        ret = self.geolocator.geocode(query, exactly_one=False, limit=limit)
        if ret is None:
            return []
        if isinstance(ret, Location):
            return [ret]
        if isinstance(ret, list):
            return ret
        return []

    def _rate_limit(self) -> None:
        now = time.time()
        from_last_call = max(0, now - self.last_api)
        if from_last_call < RATE_LIMIT_SECONDS:
            time.sleep(RATE_LIMIT_SECONDS - from_last_call)

    def address_impl(self, inp: PathWithMd5, lat: float, lon: float) -> WithMD5[GeoAddress]:
        cache_key = (lat, lon)
        cached = self._address_cache.get(cache_key)
        if cached is not None:
            return WithMD5(inp.md5, self._version, cached, None)
        self._rate_limit()
        retries_left = RETRIES
        query = f"{lat}, {lon}"
        while True:
            try:
                ret = self.geolocator.reverse(query, language="en")
                break
            # pylint: disable-next = broad-exception-caught
            except Exception as e:
                if retries_left <= 0:
                    # This is valid case of transient error, we raise exception
                    raise
                print(
                    f"Gelolocation request ({query}) for {inp.path} {inp.md5} failed. Retrying ({retries_left} left)",
                    e,
                    file=sys.stderr,
                )
                retries_left -= 1
                time.sleep(10)
        self.last_api = time.time()
        country = None
        name = None
        if ret is None:
            return WithMD5(inp.md5, self._version, None, Error("NoAddressReturned", None, None))
        if ret.raw is not None:
            raw_add = ret.raw.get("address")
        else:
            raw_add = None
        try:
            raw_data = json.dumps(ret.raw, ensure_ascii=False)
        # pylint: disable-next = broad-exception-caught
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
        geo_address = GeoAddress(ret.address, country, name, raw_data, query)
        self._address_cache[cache_key] = geo_address
        return WithMD5(inp.md5, self._version, geo_address, None)
