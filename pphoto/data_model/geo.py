import typing as t

from dataclasses import dataclass

from pphoto.data_model.base import HasCurrentVersion

T = t.TypeVar("T")


@dataclass
class GeoAddress(HasCurrentVersion):
    address: str
    country: t.Optional[str]
    name: t.Optional[str]
    raw: str
    query: str
    # TODO: add points of interestis -- i.e. home, work, ...

    @staticmethod
    def current_version() -> int:
        return 0
