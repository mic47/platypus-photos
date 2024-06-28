from dataclasses import dataclass, fields
import typing as t

from dataclasses_json import DataClassJsonMixin

from pphoto.gallery.url import SearchQuery, GalleryPaging, SortParams
from pphoto.gallery.unicode import UnicodeEmojiData


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


if __name__ == "__main__":
    main()