import typing as t
import unittest

from db.connection import PhotosConnection
from db.files_table import FilesTable, FilesTableWrongLifecycleParams
from db.types import FileRow, ManagedLifecycle


def connection() -> PhotosConnection:
    return PhotosConnection(":memory:")


def sanitize(row: t.Optional[FileRow]) -> t.Optional[FileRow]:
    if row is None:
        return row
    row.rowid = 0
    row.last_update = 0
    return row


def sanitize_list(rows: t.List[FileRow]) -> t.List[FileRow]:
    return [x for x in (sanitize(r) for r in rows) if x is not None]


class TestFilesTable(unittest.TestCase):

    def assert_table_without_paths(self, table: FilesTable, paths: t.List[str]) -> None:
        for path in paths:
            ret = table.by_path(path)
            self.assertIsNone(ret, f"Path '{path}' already exists")

    def test_create_and_migrate_table(self) -> None:
        conn = connection()
        FilesTable(conn)
        FilesTable(conn)

    def test_add_update_vs_add_only(self) -> None:
        table = FilesTable(connection())
        self.assert_table_without_paths(table, ["foo"])

        u1 = FileRow("foo", None, "og/foo", None, ManagedLifecycle.NOT_MANAGED, 0, 0)
        u2 = FileRow("foo", "omnomnom", "og/goo", "hohoho", ManagedLifecycle.BEING_MOVED_AROUND, 0, 0)
        expected = FileRow("foo", "omnomnom", "og/foo", "hohoho", ManagedLifecycle.BEING_MOVED_AROUND, 0, 0)
        table.add_or_update(u1.file, u1.md5, u1.og_file, u1.managed, u1.tmp_file)
        ret = sanitize(table.by_path("foo"))
        self.assertEqual(ret, u1)
        self.assertNotEqual(ret, expected)
        table.add_if_not_exists(u2.file, u2.md5, u2.og_file, u2.managed, u2.tmp_file)
        ret = sanitize(table.by_path("foo"))
        self.assertEqual(ret, u1)
        table.add_or_update(u2.file, u2.md5, u2.og_file, u2.managed, u2.tmp_file)
        ret = sanitize(table.by_path("foo"))
        self.assertEqual(ret, expected)

    def test_change_path(self) -> None:
        table = FilesTable(connection())
        self.assert_table_without_paths(table, ["foo", "bar"])

        u1 = FileRow("foo", None, "og/foo", None, ManagedLifecycle.SYNCED, 0, 0)
        table.add_or_update(u1.file, u1.md5, u1.og_file, u1.managed, u1.tmp_file)
        ret = sanitize(table.by_path("foo"))
        self.assertEqual(ret, u1)
        table.change_path("foo", "bar")
        ret = table.by_path("foo")
        self.assertIsNone(ret, "Foo should be moved, but ti still exists")
        u1.file = "bar"
        ret = sanitize(table.by_path("bar"))
        self.assertEqual(ret, u1, "Foo was not removed")

    def test_set_lifecycle(self) -> None:
        table = FilesTable(connection())
        self.assert_table_without_paths(table, ["foo"])

        u1 = FileRow("foo", None, "og/foo", None, ManagedLifecycle.NOT_MANAGED, 0, 0)
        table.add_or_update(u1.file, u1.md5, u1.og_file, u1.managed, u1.tmp_file)
        ret = sanitize(table.by_path("foo"))
        self.assertEqual(ret, u1)
        # TODO: test wrong params
        table.set_lifecycle(u1.file, ManagedLifecycle.BEING_MOVED_AROUND, "lol")
        ret = sanitize(table.by_path("foo"))
        self.assertEqual(
            ret, FileRow(u1.file, u1.md5, u1.og_file, "lol", ManagedLifecycle.BEING_MOVED_AROUND, 0, 0)
        )
        table.set_lifecycle(u1.file, ManagedLifecycle.SYNCED, None)
        ret = sanitize(table.by_path("foo"))
        self.assertEqual(ret, FileRow(u1.file, u1.md5, u1.og_file, None, ManagedLifecycle.SYNCED, 0, 0))

    def test_validations(self) -> None:
        table = FilesTable(connection())
        for c in ManagedLifecycle:
            if c == ManagedLifecycle.BEING_MOVED_AROUND:
                tmp_path = None
            else:
                tmp_path = "sdfsdf"
            with self.assertRaises(
                FilesTableWrongLifecycleParams,
                msg=f"{c} {tmp_path}",
            ):
                table.add_or_update("asdf", None, "fdsf", c, tmp_path)
            with self.assertRaises(
                FilesTableWrongLifecycleParams,
                msg=f"{c} {tmp_path}",
            ):
                table.add_if_not_exists("asdf", None, "fdsf", c, tmp_path)
            with self.assertRaises(
                FilesTableWrongLifecycleParams,
                msg=f"{c} {tmp_path}",
            ):
                table.set_lifecycle("asdf", c, tmp_path)

    def test_add_and_get_by_path(self) -> None:
        table = FilesTable(connection())
        self.assert_table_without_paths(table, ["foo"])

        table.add_or_update("foo", None, "og/foo", ManagedLifecycle.NOT_MANAGED, None)
        ret = table.by_path("foo")
        if ret is None:
            self.assertIsNotNone(ret, "Inserted element was not found")
            return
        self.assertEqual(ret.file, "foo", "Returned element is wrong")
        self.assertEqual(ret.og_file, "og/foo", "Returned element is wrong")
        self.assertEqual(ret.managed, ManagedLifecycle.NOT_MANAGED, "Returned element is wrong")
        self.assertEqual(ret.tmp_file, None, "Returned element is wrong")

    def test_example_by_md5(self) -> None:
        table = FilesTable(connection())
        ret = table.example_by_md5("wat")
        self.assertIsNone(ret, "Element already exists")

        table.add_or_update("bar", "wat", "og/bar", ManagedLifecycle.BEING_MOVED_AROUND, "lol")
        ret = table.example_by_md5("wat")
        if ret is None:
            self.assertIsNotNone(ret, "Inserted element was not found")
            return
        self.assertEqual(ret.file, "bar", "Returned element is wrong")
        self.assertEqual(ret.og_file, "og/bar", "Returned element is wrong")
        self.assertEqual(ret.md5, "wat", "Returned element is wrong")
        self.assertEqual(ret.managed, ManagedLifecycle.BEING_MOVED_AROUND, "Returned element is wrong")
        self.assertEqual(ret.tmp_file, "lol", "Returned element is wrong")

    def test_by_md5(self) -> None:
        table = FilesTable(connection())
        ret = table.by_md5("bar")
        self.assertListEqual(ret, [], "Element already exists")

        table.add_or_update("bar", "wat", "og/bar", ManagedLifecycle.IMPORTED, None)
        table.add_or_update("foo", "wat", None, ManagedLifecycle.BEING_MOVED_AROUND, "x/foo")
        table.add_or_update("should not be found", "random stuff", None, ManagedLifecycle.NOT_MANAGED, None)
        ret = table.by_md5("wat")
        self.assertNotEqual(ret, [], "Inserted elements were not found")
        ret.sort(key=lambda x: x.file)
        for r in ret:
            # These are assigned by DB
            r.rowid = 0
            r.last_update = 0
        self.assertListEqual(
            ret,
            [
                FileRow("bar", "wat", "og/bar", None, ManagedLifecycle.IMPORTED, 0, 0),
                FileRow("foo", "wat", None, "x/foo", ManagedLifecycle.BEING_MOVED_AROUND, 0, 0),
            ],
        )

    def test_by_managed_lifecycle(self) -> None:
        table = FilesTable(connection())
        self.assert_table_without_paths(table, ["foo", "bar", "foobar"])

        u1 = FileRow("foo", None, "og/foo", None, ManagedLifecycle.NOT_MANAGED, 0, 0)
        u2 = FileRow("bar", "omnomnom", "og/goo", "hohoho", ManagedLifecycle.BEING_MOVED_AROUND, 0, 0)
        u3 = FileRow("foobar", "omnomnom", "og/goobar", None, ManagedLifecycle.NOT_MANAGED, 0, 0)
        table.add_or_update(u1.file, u1.md5, u1.og_file, u1.managed, u1.tmp_file)
        table.add_or_update(u2.file, u2.md5, u2.og_file, u2.managed, u2.tmp_file)
        table.add_or_update(u3.file, u3.md5, u3.og_file, u3.managed, u3.tmp_file)
        self.assertListEqual([], sanitize_list(table.by_managed_lifecycle(ManagedLifecycle.SYNCED)))
        self.assertListEqual(
            [u2], sanitize_list(table.by_managed_lifecycle(ManagedLifecycle.BEING_MOVED_AROUND))
        )
        self.assertListEqual(
            [u1, u3],
            sorted(
                sanitize_list(table.by_managed_lifecycle(ManagedLifecycle.NOT_MANAGED)), key=lambda x: x.file
            ),
        )

    def test_dirty_files(self) -> None:
        table = FilesTable(connection())
        table.add_or_update("p1", "m1", None, ManagedLifecycle.SYNCED, None)
        table.add_or_update("p2", "m2", None, ManagedLifecycle.BEING_MOVED_AROUND, "tmp2")
        table.add_or_update("p3", "m3", "og3", ManagedLifecycle.SYNCED, None)
        table.add_or_update("p4", "m4", None, ManagedLifecycle.IMPORTED, None)
        table.add_or_update("p5", "m5", None, ManagedLifecycle.NOT_MANAGED, None)

        self.assertListEqual(sorted(table.dirty_md5s()), ["m1", "m3", "m5"])

        table.undirty("m1", 0.0)
        self.assertListEqual(sorted(table.dirty_md5s()), ["m1", "m3", "m5"])

        table.undirty("m1", 171822378600.0)
        self.assertListEqual(sorted(table.dirty_md5s()), ["m3", "m5"])

        table.change_path("p1", "p1'")
        self.assertListEqual(sorted(table.dirty_md5s()), ["m1", "m3", "m5"])


if __name__ == "__main__":
    unittest.main()
