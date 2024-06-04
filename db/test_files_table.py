import unittest

from db.connection import Connection
from db.files_table import FilesTable
from db.types import FileRow


def connection() -> Connection:
    return Connection(":memory:")


class TestStringMethods(unittest.TestCase):
    def test_create_and_migrate_table(self) -> None:
        conn = connection()
        FilesTable(conn)
        FilesTable(conn)

    def test_add_and_get_by_path(self) -> None:
        table = FilesTable(connection())
        ret = table.by_path("foo")
        self.assertIsNone(ret, "Element already exists")
        table.add("foo", None)
        ret = table.by_path("foo")
        if ret is None:
            self.assertIsNotNone(ret, "Inserted element was not found")
            return
        self.assertEqual(ret.file, "foo", "Returned element is wrong")

    def test_example_by_md5(self) -> None:
        table = FilesTable(connection())
        ret = table.example_by_md5("wat")
        self.assertIsNone(ret, "Element already exists")
        table.add("bar", "wat")
        ret = table.example_by_md5("wat")
        if ret is None:
            self.assertIsNotNone(ret, "Inserted element was not found")
            return
        self.assertEqual(ret.file, "bar", "Returned element is wrong")
        self.assertEqual(ret.md5, "wat", "Returned element is wrong")

    def test_by_md5(self) -> None:
        table = FilesTable(connection())
        ret = table.by_md5("bar")
        self.assertListEqual(ret, [], "Element already exists")
        table.add("bar", "wat")
        table.add("foo", "wat")
        table.add("should not be found", "random stuff")
        ret = table.by_md5("wat")
        self.assertNotEqual(ret, [], "Inserted elements were not found")
        ret.sort(key=lambda x: x.file)
        for r in ret:
            # These are assigned by DB
            r.rowid = 0
            r.last_update = 0
        self.assertListEqual(ret, [FileRow("bar", "wat", 0, 0), FileRow("foo", "wat", 0, 0)])


if __name__ == "__main__":
    unittest.main()
