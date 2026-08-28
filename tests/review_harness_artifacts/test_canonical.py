"""JSONの一意な直列化と曖昧な入力の拒否を確認する。"""

from __future__ import annotations

import unittest

from review_harness_artifacts.canonical import (
    canonicalize,
    parse_json_bytes,
    sha256_hex,
)
from review_harness_artifacts.errors import ArtifactError


class CanonicalJsonTests(unittest.TestCase):
    def test_same_value_has_same_bytes_and_hash(self) -> None:
        first = parse_json_bytes(b'{"b":1,"a":2}')
        second = parse_json_bytes(b'{\n  "a": 2, "b": 1\n}')
        self.assertEqual(canonicalize(first), canonicalize(second))
        self.assertEqual(
            sha256_hex(canonicalize(first)),
            sha256_hex(canonicalize(second)),
        )

    def test_duplicate_json_key_is_rejected(self) -> None:
        with self.assertRaisesRegex(ArtifactError, "json_object_keys_must_be_unique"):
            parse_json_bytes(b'{"a":1,"a":2}')

    def test_bom_is_rejected(self) -> None:
        with self.assertRaisesRegex(ArtifactError, "json_must_not_have_bom"):
            parse_json_bytes(b'\xef\xbb\xbf{"a":1}')

    def test_out_of_range_integer_is_rejected(self) -> None:
        with self.assertRaisesRegex(ArtifactError, "json_integer_must_be_ijson_exact"):
            canonicalize({"value": 9_007_199_254_740_992})


if __name__ == "__main__":
    unittest.main()
