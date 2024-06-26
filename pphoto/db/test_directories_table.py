import unittest

from pphoto.db.connection import GalleryConnection
from pphoto.db.directories_table import DirectoriesTable


def connection() -> GalleryConnection:
    return GalleryConnection(":memory:")


class TestDirectoriesTable(unittest.TestCase):

    def test_create_and_migrate_table(self) -> None:
        conn = connection()
        DirectoriesTable(conn)
        DirectoriesTable(conn)

    def test_add_and_get(self) -> None:
        conn = connection()
        table = DirectoriesTable(conn)

        table.add("foo/bar/sdfs", "lol")
        table.add("foo/bar/fdsakljfjlekw", "wtf")
        table.add("foo/sdflskdf/sdfs", "rofl")
        table.add("foo/sdfjksdjfksdf/sdfs", "lol")
        table.add("foo/bar/sdfs", "lol")
        table.add("foo/bar2/sdfs", "wtf")

        self.assertListEqual(table.by_md5("non existend"), [])
        self.assertListEqual(sorted(table.by_md5("lol")), ["foo/bar/sdfs", "foo/sdfjksdjfksdf/sdfs"])
        self.assertListEqual(sorted(table.by_md5("wtf")), ["foo/bar/fdsakljfjlekw", "foo/bar2/sdfs"])
        self.assertListEqual(table.by_md5("rofl"), ["foo/sdflskdf/sdfs"])

    def test_multi_add_and_get(self) -> None:
        conn = connection()
        table = DirectoriesTable(conn)

        table.multi_add(
            [
                ("foo/bar/sdfs", "lol"),
                ("foo/bar/fdsakljfjlekw", "wtf"),
                ("foo/sdflskdf/sdfs", "rofl"),
                ("foo/sdfjksdjfksdf/sdfs", "lol"),
                ("foo/bar/sdfs", "lol"),
                ("foo/bar2/sdfs", "wtf"),
            ]
        )

        self.assertListEqual(table.by_md5("non existend"), [])
        self.assertListEqual(sorted(table.by_md5("lol")), ["foo/bar/sdfs", "foo/sdfjksdjfksdf/sdfs"])
        self.assertListEqual(sorted(table.by_md5("wtf")), ["foo/bar/fdsakljfjlekw", "foo/bar2/sdfs"])
        self.assertListEqual(table.by_md5("rofl"), ["foo/sdflskdf/sdfs"])
