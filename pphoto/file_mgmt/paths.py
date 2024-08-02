import datetime
import os
import typing as t

from pphoto.utils.files import pathify


class HaveNameAndCountry(t.Protocol):
    country: t.Optional[str]
    name: t.Optional[str]


def resolve_dir(
    photos_dir: str,
    date: t.Optional[datetime.datetime],
    geo: t.Optional[HaveNameAndCountry],
    flat: bool = False,
) -> str:
    # f"{base_dir}/{year}/{month}-{day}-{place}/{filename}_{exists_suffix}.{extension}"
    path = photos_dir
    separator = "-" if flat else "/"
    if date is not None:
        path = f"{path}/{date.year:04d}{separator}{date.month:02d}-{date.day:02d}"
    else:
        path = f"{path}/UnknownDate"
    if geo is not None:
        address_parts = []
        if geo.country is not None:
            address_parts.append(geo.country)
        if geo.name is not None:
            address_parts.append(geo.name)
        if address_parts:
            address = "_".join(address_parts)
            path = f"{path}-{pathify(address)}"
    return path


def resolve_path(directory: str, og_path: str) -> str:
    path = directory
    filename = os.path.basename(og_path)
    splitted = filename.rsplit(".", maxsplit=1)
    extension = splitted[-1]
    basefile = ".".join(splitted[:-1])
    insert = ""
    count = 0
    while True:
        final_path = f"{path}/{basefile}{insert}.{extension}"
        if not os.path.exists(final_path):
            break
        insert = f"_{count:03d}"
        count += 1
    return final_path
