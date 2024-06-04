import unittest

from db.connection import Connection
from db.features_table import FeaturesTable
from db.types import FeaturePayload


def connection() -> Connection:
    return Connection(":memory:")


class TestFeaturesTable(unittest.TestCase):
    def test_create_and_migrate_table(self) -> None:
        conn = connection()
        FeaturesTable(conn)
        FeaturesTable(conn)

    def test_add_and_get_payload(self) -> None:
        table = FeaturesTable(connection())
        old_payload = b"Yay this is old payload!"
        new_payload = b"Yay this is new payload!"
        type_ = "CorrectType"
        wrong_type = "WrongType"
        md5 = "foo_bar"
        new_version = 1
        old_version = 0
        # Make sure it does not exists
        self.assertIsNone(table.get_payload(type_, md5))
        self.assertIsNone(table.get_payload(wrong_type, md5))
        # Add old version
        table.add(old_payload, type_, md5, old_version)
        # This should not be returned
        self.assertIsNone(table.get_payload(wrong_type, md5))
        ret = table.get_payload(type_, md5)
        if ret is None:
            self.assertIsNotNone(ret, "Inserted element should be returned")
            return
        self.assertEqual(ret, FeaturePayload(old_payload, old_version, ret.last_update, ret.rowid))
        old_return = ret

        # Add new version
        table.add(new_payload, type_, md5, new_version)
        ret = table.get_payload(type_, md5)
        if ret is None:
            self.assertIsNotNone(ret, "Inserted element should be returned")
            return
        self.assertEqual(ret, FeaturePayload(new_payload, new_version, ret.last_update, ret.rowid))
        self.assertLessEqual(old_return.last_update, ret.last_update)
        new_return = ret

        # Old version should not be added
        table.add(old_payload, type_, md5, old_version)
        ret = table.get_payload(type_, md5)
        # Nothing should be added, as version is older
        self.assertEqual(ret, new_return)

    def test_dirty_md5s(self) -> None:
        table = FeaturesTable(connection())
        table.add(b"P1", "T1", "M1", 0)
        table.add(b"P2", "T2", "M2", 0)
        table.add(b"P3", "T3", "M1", 0)
        table.add(b"P4", "T1", "M4", 0)
        e1 = table.get_payload("T1", "M1")
        e2 = table.get_payload("T2", "M2")
        e3 = table.get_payload("T3", "M1")
        e4 = table.get_payload("T1", "M4")

        if e1 is None or e2 is None or e3 is None or e4 is None:
            assert False, "Unable to setup test, elements were not inserted"

        # Everything is dirty
        dirty = sorted(list(table.dirty_md5s(["T1", "T2", "T3"])))
        self.assertListEqual(dirty, [("M1", e1.last_update), ("M2", e3.last_update), ("M4", e4.last_update)])

        dirty = list(table.dirty_md5s(["T2"]))
        self.assertListEqual(dirty, [("M2", e2.last_update)])

        # Should do the same, as timestamp is low
        table.undirty("M2", ["T1", "T2", "T3"], 0)
        dirty = list(table.dirty_md5s(["T2"]))
        self.assertListEqual(dirty, [("M2", e2.last_update)])

        # Undirty M2, it shoudl become not dirty
        table.undirty("M2", ["T1", "T2", "T3"], max(e1.last_update, e2.last_update, e3.last_update))
        dirty = list(table.dirty_md5s(["T2"]))
        self.assertListEqual(dirty, [])

        # Rest of it should be dirty
        dirty = sorted(list(table.dirty_md5s(["T1", "T2", "T3"])))
        self.assertListEqual(dirty, [("M1", e1.last_update), ("M4", e4.last_update)])

        # Empty list is like all types
        dirty = sorted(list(table.dirty_md5s([])))
        self.assertListEqual(dirty, [("M1", e1.last_update), ("M4", e4.last_update)])

        # Limit should return one element
        dirty = sorted(list(table.dirty_md5s(["T1", "T2", "T3"], limit=1)))
        self.assertEqual(len(dirty), 1, "Should return only 1 element")
        assert dirty[0] == ("M1", e1.last_update) or dirty[0] == (
            "M4",
            e4.last_update,
        ), "Limit returned wrong element"

        # Need to undirty all features for file not to be dirty
        table.undirty("M1", ["T1"], max(e1.last_update, e2.last_update, e3.last_update, e4.last_update))
        dirty = sorted(list(table.dirty_md5s(["T1", "T2", "T3"])))
        self.assertListEqual(dirty, [("M1", e1.last_update), ("M4", e4.last_update)])
        table.undirty("M1", ["T3"], max(e1.last_update, e2.last_update, e3.last_update, e4.last_update))
        dirty = sorted(list(table.dirty_md5s(["T1", "T2", "T3"])))
        self.assertListEqual(dirty, [("M4", e4.last_update)])

        # Need to undirty right feature
        table.undirty("M4", ["T3"], max(e1.last_update, e2.last_update, e3.last_update, e4.last_update))
        dirty = sorted(list(table.dirty_md5s(["T1", "T2", "T3"])))
        self.assertListEqual(dirty, [("M4", e4.last_update)])

        # Need to undiry with good timestamp
        table.undirty("M4", ["T1"], 0)
        dirty = sorted(list(table.dirty_md5s(["T1", "T2", "T3"])))
        self.assertListEqual(dirty, [("M4", e4.last_update)])
        # Need to undiry with good timestamp

        table.undirty("M4", ["T1"], e4.last_update)
        dirty = sorted(list(table.dirty_md5s(["T1", "T2", "T3"])))
        self.assertListEqual(dirty, [])


if __name__ == "__main__":
    unittest.main()
