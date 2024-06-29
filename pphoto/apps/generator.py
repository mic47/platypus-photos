from dataclasses import dataclass, fields
import json
import typing as t

from dataclasses_json import DataClassJsonMixin

from fastapi.openapi.utils import get_openapi

from pphoto.gallery.url import SearchQuery, GalleryPaging, SortParams
from pphoto.gallery.unicode import UnicodeEmojiData

from pphoto.apps.gallery import app as gallery_app


@dataclass
class UrlFieldPartitioning(DataClassJsonMixin):
    search_query: t.List[str]  # noqa: F841
    paging: t.List[str]  # noqa: F841
    sort: t.List[str]  # noqa: F841


@dataclass
class GeneratedData(DataClassJsonMixin):
    fields: UrlFieldPartitioning  # noqa: F841
    unicode: UnicodeEmojiData  # noqa: F841


def main() -> None:
    with open("typescript/data_model.generated.json", "w", encoding="utf-8") as f:
        print(
            GeneratedData(
                UrlFieldPartitioning(
                    search_query=[x.name for x in fields(SearchQuery)],
                    paging=[x.name for x in fields(GalleryPaging)],
                    sort=[x.name for x in fields(SortParams)],
                ),
                UnicodeEmojiData.create(),
            ).to_json(ensure_ascii=False, indent=2),
            file=f,
        )
    with open("schema/pygallery.openapi.json", "w", encoding="utf-8") as f:
        json.dump(
            get_openapi(
                title=gallery_app.title,
                version=gallery_app.version,
                openapi_version=gallery_app.openapi_version,
                description=gallery_app.description,
                routes=gallery_app.routes,
            ),
            f,
        )


if __name__ == "__main__":
    main()
