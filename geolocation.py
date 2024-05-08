from geopy.geocoders import Nominatim
from dataclasses_json import dataclass_json
from dataclasses import dataclass
import time
import typing as t

from cache import HasImage


@dataclass
class GeoAddress(HasImage):
    image: str
    address: str
    country: t.Optional[str]
    city: t.Optional[str]
    # TODO: add points of interestis -- i.e. home, work, ...


RATE_LIMIT_SECONDS = 1


class Geolocator:
    def __init__(self):
        self.geolocator = Nominatim(user_agent="Mic's photo lookups")
        self.last_api = time.time() - 10

    def address(self, image: str, lat: float, lon: float) -> GeoAddress:
        now = time.time()
        from_last_call = max(0, now - self.last_api)
        if from_last_call < RATE_LIMIT_SECONDS:
            time.sleep(RATE_LIMIT_SECONDS - from_last_call)
        ret = self.geolocator.reverse(f"{lat}, {lon}")
        country = None
        city = None
        raw_add = ret.raw.get("address")
        if raw_add is not None:
            city = raw_add.get("city") or raw_add.get("village") or raw_add.get("town")
            country = raw_add.get("country")
        return GeoAddress(image, ret.address, country, city)
