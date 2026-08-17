from __future__ import annotations

import unittest

from scripts.listing.text_sanitizer import sanitize_payload_text_for_rakuten_api


class TextSanitizerTests(unittest.TestCase):
    def test_preserves_exact_rakuten_attribute_name(self) -> None:
        payload = {
            "variants": {
                "test": {
                    "attributes": [
                        {"name": "原産国／製造国", "values": ["日本㎏"]},
                    ]
                }
            }
        }

        actual = sanitize_payload_text_for_rakuten_api(payload)

        attribute = actual["variants"]["test"]["attributes"][0]
        self.assertEqual(attribute["name"], "原産国／製造国")
        self.assertEqual(attribute["values"], ["日本kg"])

    def test_repairs_legacy_half_width_attribute_name(self) -> None:
        actual = sanitize_payload_text_for_rakuten_api(
            {"name": "原産国/製造国", "values": ["日本"]}
        )

        self.assertEqual(actual["name"], "原産国／製造国")


if __name__ == "__main__":
    unittest.main()
