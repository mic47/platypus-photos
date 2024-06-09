import typing as t
import datetime
import gc
import random
import sys


def assert_never(x: t.NoReturn) -> t.NoReturn:
    assert False, f"Unhandled type: {type(x).__name__}"


T = t.TypeVar("T")
K = t.TypeVar("K")
V = t.TypeVar("V")

_LAZY_WITH_TTL: "t.List[Lazy[t.Any]]" = []


class Lazy(t.Generic[T]):
    def __init__(self, constructor: t.Callable[[], T], ttl: t.Optional[datetime.timedelta] = None) -> None:
        self._constructor = constructor
        self._value: t.Optional[T] = None
        self._ttl = ttl
        self._last_use = datetime.datetime.now()
        if self._ttl is not None:
            _LAZY_WITH_TTL.append(self)

    @staticmethod
    def check_ttl() -> None:
        now = datetime.datetime.now()
        freed = False
        for lz in _LAZY_WITH_TTL:
            freed |= lz.internal_check_ttl(now)
        if freed:
            gc.collect()

    def internal_check_ttl(self, now: datetime.datetime) -> bool:
        if self._value is not None and self._ttl is not None and self._last_use + self._ttl < now:
            gc.collect()
            if len(gc.get_referrers(self._value)) > 1:
                print(
                    "ERROR: Not freeing memory for as there are multiple references",
                    type(self._value).__name__,
                    file=sys.stderr,
                )
            else:
                print("Freeing memory for", type(self._value).__name__, file=sys.stderr)
                del self._value
                self._value = None
                return True
        return False

    def get(self) -> T:
        if self._ttl is not None:
            self._last_use = datetime.datetime.now()
        if self._value is not None:
            return self._value
        self._value = (self._constructor)()
        if self._ttl is None:
            del self._constructor
        return self._value


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

    def delete(self, value: V) -> None:
        if value in self._items:
            del self._items[value]

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
