import typing as t
import datetime
import random


def assert_never(x: t.NoReturn) -> t.NoReturn:
    assert False, f"Unhandled type: {type(x).__name__}"


K = t.TypeVar("K")
V = t.TypeVar("V")


class DefaultDict(dict[K, V]):
    def __init__(self, default_factory: t.Callable[[K], V]):
        super().__init__()
        self.default_factory = default_factory

    def __missing__(self, key: K) -> V:
        ret = self[key] = self.default_factory(key)
        return ret


class CacheTTL(t.Generic[V]):
    def __init__(self, ttl_low: datetime.timedelta, ttl_high: datetime.timedelta) -> None:
        self._ttl_low = int(ttl_low.total_seconds())
        self._ttl_high = int(ttl_high.total_seconds())
        self._items: t.Dict[V, datetime.datetime] = {}

    def _get_ttl(self) -> datetime.timedelta:
        return datetime.timedelta(seconds=random.randint(self._ttl_low, self._ttl_high))

    def mutable_should_update(self, value: V, now: t.Optional[datetime.datetime] = None) -> bool:
        if now is None:
            now = datetime.datetime.now()
        next_update = self._items.get(value)
        if next_update is None:
            # We have not seen this element, let's add it
            self._items[value] = now + self._get_ttl()
            return True
        if next_update > now:
            # We have seen this element recently
            return False
        # We've seen this element, but it was quite while ago
        self._items[value] = now + self._get_ttl()
        return True
