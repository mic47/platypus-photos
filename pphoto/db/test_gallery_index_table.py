from datetime import datetime
import typing as t
import unittest

from pphoto.db.connection import GalleryConnection
from pphoto.db.directories_table import DirectoriesTable
from pphoto.db.gallery_index_table import GalleryIndexTable, WrongAggregateTypeReturned
from pphoto.db.types_image import Image, ImageAddress, ImageAggregation
from pphoto.db.types_location import LocPoint, LocationCluster
from pphoto.gallery.url import SearchQuery, GalleryPaging, SortParams


def connection() -> GalleryConnection:
    return GalleryConnection(":memory:")


def _image(
    md5: str,
    version: int = Image.current_version(),
    datetm: t.Optional[datetime] = datetime(2024, 1, 2, 10, 30, 47),
    dependent_features_last_update: int = 0,
    tags: t.Optional[t.Dict[str, float]] = None,
    caption: t.Optional[str] = "There is something fishy here",
    address: t.Optional[str] = "Bristol, Portlandia",
    lat: t.Optional[float] = 49.0,
    lon: t.Optional[float] = 12.0,
    alt: t.Optional[float] = 13.0,
) -> Image:
    if tags is None:
        tags = {"foo": 0.3, "bar": 1.457}
    return Image(
        md5,
        datetm,
        tags,
        caption,
        ImageAddress(
            None if address is None else address.split(",")[0].strip(),
            None if address is None else address.split(",")[-1].strip(),
            address,
        ),
        dependent_features_last_update,
        lat,
        lon,
        alt,
        ["ManualLocation"],
        version,
    )


class TestGalleryIndexTable(unittest.TestCase):
    def test_create_and_migrate_table(self) -> None:
        conn = connection()
        GalleryIndexTable(conn)
        GalleryIndexTable(conn)

    def test_add_and_get(self) -> None:
        table = GalleryIndexTable(connection())
        old_version = 0
        new_version = Image.current_version()
        old_omg = _image("M1", version=old_version)
        new_omg = _image("M1", version=new_version)
        changed_omg = _image("M1", version=new_version, caption="WAAAT")
        changed_old_omg = _image(
            "M1", caption="WAAAT", dependent_features_last_update=100, version=old_version
        )
        table.add(old_omg)
        res = table.get_matching_images(SearchQuery(), SortParams(), GalleryPaging())[0]
        self.assertEqual(len(res), 1)
        self.assertEqual(old_omg, res[0])

        table.add(new_omg)
        res = table.get_matching_images(SearchQuery(), SortParams(), GalleryPaging())[0]
        self.assertEqual(len(res), 1)
        self.assertEqual(new_omg, res[0])

        table.add(changed_omg)
        res = table.get_matching_images(SearchQuery(), SortParams(), GalleryPaging())[0]
        self.assertEqual(len(res), 1)
        self.assertEqual(new_omg, res[0])

        table.add(changed_old_omg)
        res = table.get_matching_images(SearchQuery(), SortParams(), GalleryPaging())[0]
        self.assertEqual(len(res), 1)
        self.assertEqual(new_omg, res[0])

    def test_old_version(self) -> None:
        table = GalleryIndexTable(connection())
        omg = _image("M1")
        table.add(omg)
        omg_old = _image("M2", version=0)
        table.add(omg_old)
        res = list(table.old_versions_md5())
        self.assertEqual(len(res), 1)
        self.assertEqual(omg_old.md5, res[0])

    def test_get_aggregate_stats(self) -> None:
        table = GalleryIndexTable(connection())
        table.add(_image("M1", alt=127.47, caption=None, tags={}, lon=32.0))
        table.add(_image("M2", tags={"lol": 10.0}, caption="This is ridiculous"))
        table.add(_image("M3", address="Jaskd, Foudlekf", lat=12.0, lon=-18.0, alt=None))
        table.add(_image("M4", lon=34.0))
        stats = table.get_aggregate_stats(SearchQuery())
        expected = ImageAggregation(
            4,
            {"Bristol": 3, "Portlandia": 3, "Foudlekf": 1, "Jaskd": 1},
            {"bar": 2, "foo": 2, "lol": 1},
            {"There is something fishy here": 2, "This is ridiculous": 1},
            (12.0, 49.0),
            (-18.0, 34.0),
            (13.0, 127.47),
        )
        self.assertEqual(stats, expected)
        stats = table.get_aggregate_stats(SearchQuery(tag="missing"))
        self.assertEqual(stats, ImageAggregation(0, {}, {}, {}, None, None, None))

    def test_get_image_clusters(self) -> None:
        table = GalleryIndexTable(connection())
        table.add(_image("M1", alt=127.47, caption=None, tags={}, lon=32.0))
        table.add(_image("M2", tags={"lol": 10.0}, caption="This is ridiculous"))
        table.add(_image("M3", address="Jaskd, Foudlekf", lat=12.0, lon=-18.0, alt=None))
        table.add(_image("M4", lon=34.0))
        clusters = sorted(
            table.get_image_clusters(SearchQuery(), LocPoint(1000, -1000), LocPoint(-1000, 30), 10, 10, 0.0),
            key=lambda x: x.example_path_md5,
        )
        self.assertListEqual(
            clusters,
            [
                LocationCluster(
                    "M2",
                    "This is ridiculous",
                    1,
                    "Portlandia",
                    "Bristol",
                    LocPoint(49.0, 12.0),
                    LocPoint(49.0, 12.0),
                    LocPoint(49.0, 12.0),
                ),
                LocationCluster(
                    "M3",
                    "There is something fishy here",
                    1,
                    "Foudlekf",
                    "Jaskd",
                    LocPoint(12.0, -18.0),
                    LocPoint(12.0, -18.0),
                    LocPoint(12.0, -18.0),
                ),
            ],
        )
        # Try overfetch
        clusters = sorted(
            table.get_image_clusters(SearchQuery(), LocPoint(1000, -1000), LocPoint(-1000, 30), 10, 10, 0.5),
            key=lambda x: x.example_path_md5,
        )
        self.assertListEqual(
            clusters,
            [
                LocationCluster(
                    example_path_md5="M1",
                    example_classification="This is ridiculous",
                    size=3,
                    address_name="Portlandia",
                    address_country="Bristol",
                    top_left=LocPoint(latitude=49.0, longitude=34.0),
                    bottom_right=LocPoint(latitude=49.0, longitude=12.0),
                    position=LocPoint(latitude=49.0, longitude=26.0),
                ),
                LocationCluster(
                    example_path_md5="M3",
                    example_classification="There is something fishy here",
                    size=1,
                    address_name="Foudlekf",
                    address_country="Jaskd",
                    top_left=LocPoint(latitude=12.0, longitude=-18.0),
                    bottom_right=LocPoint(latitude=12.0, longitude=-18.0),
                    position=LocPoint(latitude=12.0, longitude=-18.0),
                ),
            ],
        )

    def test_querying(self) -> None:
        con = connection()
        table = GalleryIndexTable(con)
        directories = DirectoriesTable(con)
        i1 = _image(
            "M1", alt=127.47, caption=None, tags=None, lon=32.0, datetm=datetime(2023, 1, 1, 12, 12, 12)
        )
        i2 = _image("M2", tags={"lol": 10.0}, caption="This is ridiculous")
        i3 = _image("M3", address="Jaskd, Foudlekf", lat=12.0, lon=-18.0, alt=None)
        i4 = _image("M4", lon=34.0, datetm=None)
        table.add(i1)
        table.add(i2)
        table.add(i3)
        table.add(i4)
        ret = table.get_matching_images(SearchQuery(addr="Foud"), SortParams(), GalleryPaging())[0]
        self.assertListEqual(ret, [i3])
        ret = table.get_matching_images(SearchQuery(addr="Foud", cls="fishy"), SortParams(), GalleryPaging())[
            0
        ]
        self.assertListEqual(ret, [i3])
        ret = sorted(
            table.get_matching_images(SearchQuery(cls="fishy"), SortParams(), GalleryPaging())[0],
            key=lambda x: x.md5,
        )
        self.assertListEqual(ret, [i3, i4])
        ret = sorted(
            table.get_matching_images(SearchQuery(cls="fishy"), SortParams(), GalleryPaging())[0],
            key=lambda x: x.md5,
        )
        self.assertListEqual(ret, [i3, i4])
        ret = table.get_matching_images(SearchQuery(directory="/foo/bar"), SortParams(), GalleryPaging())[0]
        self.assertListEqual(ret, [])
        directories.add("/foo/bar", "M1")
        directories.add("/foo/lol", "M1")
        directories.add("/foo/lol", "M3")
        directories.add("/foo/bar", "M2")
        ret = sorted(
            table.get_matching_images(SearchQuery(directory="/foo/bar"), SortParams(), GalleryPaging())[0],
            key=lambda x: x.md5,
        )
        self.assertListEqual(ret, [i1, i2])
        ret = sorted(
            table.get_matching_images(SearchQuery(directory="/foo/lol"), SortParams(), GalleryPaging())[0],
            key=lambda x: x.md5,
        )
        self.assertListEqual(ret, [i1, i3])
        ret = sorted(
            table.get_matching_images(SearchQuery(directory="/foo"), SortParams(), GalleryPaging())[0],
            key=lambda x: x.md5,
        )
        self.assertListEqual(ret, [i1, i2, i3])
        ret = sorted(
            table.get_matching_images(SearchQuery(directory="/wat"), SortParams(), GalleryPaging())[0],
            key=lambda x: x.md5,
        )
        self.assertListEqual(ret, [])

    def test_errors_aggregate_states(self) -> None:
        table = GalleryIndexTable(connection())
        self.assertRaises(
            WrongAggregateTypeReturned,
            lambda: table.get_aggregate_stats(
                SearchQuery(),
                _extra_query_for_tests="UNION ALL SELECT 'what', null, COUNT(1) FROM matched_images",
            ),
        )
        self.assertRaises(
            WrongAggregateTypeReturned,
            lambda: table.get_aggregate_stats(
                SearchQuery(),
                _extra_query_for_tests="UNION ALL SELECT 'lat', 'wut', COUNT(1) FROM matched_images",
            ),
        )
