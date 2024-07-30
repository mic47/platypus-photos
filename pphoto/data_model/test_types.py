import datetime as dt
import json
import math
import unittest
import types
import typing as t

from hypothesis import given, example
from hypothesis.strategies import from_type, register_type_strategy, floats, datetimes, none

from pphoto.data_model.base import StorableData
from pphoto.data_model.exif import ImageExif
from pphoto.data_model.face import FaceEmbeddings
from pphoto.data_model.geo import GeoAddress
from pphoto.data_model.text import ImageClassification
from pphoto.data_model.manual import ManualLocation
from pphoto.data_model.manual import ManualText
from pphoto.data_model.manual import ManualIdentities
from pphoto.data_model.manual import ManualDate

# It's annoying to handle nan / infinity with json
register_type_strategy(float, floats(allow_nan=False, allow_infinity=False, allow_subnormal=False))
register_type_strategy(
    dt.datetime,
    # We want to avoid numeric errors, or known timezone issues
    datetimes(min_value=dt.datetime(1980, 1, 1), max_value=dt.datetime(2035, 1, 1), timezones=none()),
)

T = t.TypeVar("T", bound=StorableData)


class TestEncoding(unittest.TestCase):

    def assert_type_serialization_is_consistent(self, data: T, load: t.Callable[[t.Any], T]) -> None:
        serialized = json.dumps(data.to_json_dict()).encode("utf-8")
        deserialized = json.loads(serialized)
        self.assertEqual(deserialized, data.to_json_dict())
        self.assertEqual(load(data.to_json_dict()), data)
        self.assertEqual(load(deserialized), data)

    @given(from_type(ImageExif))
    def test_image_exif(self, s: ImageExif) -> None:
        self.assert_type_serialization_is_consistent(s, ImageExif.from_json_dict)

    @given(from_type(ManualLocation))
    def test_manual_location(self, s: ManualLocation) -> None:
        self.assert_type_serialization_is_consistent(s, ManualLocation.from_json_dict)

    @given(from_type(ManualText))
    def test_manual_text(self, s: ManualText) -> None:
        self.assert_type_serialization_is_consistent(s, ManualText.from_json_dict)

    @given(from_type(ManualIdentities))
    def test_manual_tdentities(self, s: ManualIdentities) -> None:
        self.assert_type_serialization_is_consistent(s, ManualIdentities.from_json_dict)

    @given(from_type(ManualDate))
    def test_manual_date(self, s: ManualDate) -> None:
        self.assert_type_serialization_is_consistent(s, ManualDate.from_json_dict)

    @given(from_type(FaceEmbeddings))
    def test_face_embeddings(self, s: FaceEmbeddings) -> None:
        self.assert_type_serialization_is_consistent(s, FaceEmbeddings.from_json_dict)

    @given(from_type(GeoAddress))
    def test_geo_address(self, s: GeoAddress) -> None:
        self.assert_type_serialization_is_consistent(s, GeoAddress.from_json_dict)

    @given(from_type(ImageClassification))
    def test_image_classification(self, s: ImageClassification) -> None:
        self.assert_type_serialization_is_consistent(s, ImageClassification.from_json_dict)
