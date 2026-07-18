from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.keepa_raw_analyzer import analyze_keepa_response, build_candidate_image_urls, sanitize_request_params
from scripts.listing.keepa_product_client import parse_keepa_product


ROOT_DIR = Path(__file__).resolve().parents[1]


class KeepaRawAnalyzerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.request_params = {
            "key": "SECRET",
            "domain": 5,
            "asin": "B0TEST0001",
            "stats": 90,
            "history": 0,
            "offers": 20,
        }
        self.raw_response = {
            "tokensLeft": 42,
            "refillIn": 1234,
            "products": [
                {
                    "asin": "B0TEST0001",
                    "title": "Sample title",
                    "brand": "Sample brand",
                    "manufacturer": "Maker Inc",
                    "model": "MODEL-1",
                    "partNumber": "PART-1",
                    "color": "Black",
                    "size": "L",
                    "style": "Style A",
                    "features": ["Feature 1", "Feature 2"],
                    "description": "Description text",
                    "eanList": ["1234567890123"],
                    "categoryTree": [{"catId": 111}, {"catId": 222}],
                    "imagesCSV": None,
                    "images": [
                        {"l": "abc123.jpg", "m": "abc123_m.jpg"},
                        {"l": "abc123.jpg", "m": "abc123_m.jpg"},
                        {"m": "def456_m.jpg"},
                        {"l": "", "m": ""},
                    ],
                    "offers": [{"sellerId": "A1"}, {"sellerId": "A1"}],
                    "hazardousMaterials": ["ETHANOL"],
                    "isHeatSensitive": False,
                    "itemForm": "liquid",
                    "scent": "chapter65",
                    "unitCount": {"unitType": "ml", "unitValue": 60},
                    "isAdultProduct": True,
                    "stats": {
                        "buyBoxPrice": 198000,
                        "buyBoxShipping": 0,
                        "current": [None] * 11 + [1] + [5],
                        "avg90": [None] * 11 + [1] + [-1],
                        "totalOfferCount": 1,
                        "offerCountFBA": 1,
                        "offerCountFBM": 0,
                    },
                }
            ],
        }

    def test_sanitize_request_params_removes_key(self) -> None:
        sanitized = sanitize_request_params(self.request_params)
        self.assertNotIn("key", sanitized)
        self.assertEqual(sanitized["asin"], "B0TEST0001")

    def test_build_candidate_image_urls(self) -> None:
        urls = build_candidate_image_urls("abc123.jpg,def456_m.jpg")
        self.assertEqual(
            urls,
            [
                "https://m.media-amazon.com/images/I/abc123.jpg",
                "https://m.media-amazon.com/images/I/def456_m.jpg",
            ],
        )

    def test_analyze_keepa_response_builds_reports(self) -> None:
        parsed_product, field_report, mapping_report = analyze_keepa_response(
            asin="B0TEST0001",
            raw_response=self.raw_response,
            request_params=self.request_params,
        )

        self.assertEqual(parsed_product.ean, "1234567890123")
        self.assertEqual(parsed_product.category_id, 222)
        self.assertEqual(
            parsed_product.image_urls,
            [
                "https://m.media-amazon.com/images/I/abc123.jpg",
                "https://m.media-amazon.com/images/I/def456_m.jpg",
            ],
        )
        self.assertEqual(parsed_product.images_csv, "")
        self.assertEqual(parsed_product.image_source, "keepa_images")
        self.assertEqual(parsed_product.buy_box_price, 1980)
        self.assertEqual(parsed_product.current_new_offer_count, 1)
        self.assertEqual(parsed_product.avg90_new_offer_count, 1.0)
        self.assertEqual(parsed_product.avg90_seller_count, 1.0)
        self.assertEqual(parsed_product.total_offer_count, 1)
        self.assertEqual(parsed_product.offer_count_fba, 1)
        self.assertEqual(parsed_product.offer_count_fbm, 0)
        self.assertTrue(parsed_product.is_adult)
        self.assertEqual(parsed_product.is_adult_source, "isAdultProduct")

        self.assertEqual(field_report["request"]["asin"], "B0TEST0001")
        self.assertNotIn("key", field_report["request"]["requested_options"])
        self.assertEqual(field_report["response_meta"]["product_count"], 1)
        self.assertEqual(field_report["hazardous_materials_summary"]["count"], 1)

        image_mapping = next(item for item in mapping_report["mappings"] if item["rakuten_field"] == "image_candidates")
        count_mapping = next(item for item in mapping_report["mappings"] if item["rakuten_field"] == "new_offer_counts")
        self.assertEqual(image_mapping["recommended_source"], "products[0].images[].l")
        self.assertEqual(mapping_report["image_analysis"]["main_image_candidate"], "https://m.media-amazon.com/images/I/abc123.jpg")
        self.assertEqual(count_mapping["recommended_source"], "products[0].stats.avg90[11]")
        self.assertEqual(count_mapping["diagnosis"], "ok")

    def test_images_csv_fallback_when_images_missing(self) -> None:
        raw_response = {
            **self.raw_response,
            "products": [{**self.raw_response["products"][0], "images": [], "imagesCSV": "ghi789.jpg,jkl012.jpg"}],
        }
        parsed_product, _, mapping_report = analyze_keepa_response(
            asin="B0TEST0001",
            raw_response=raw_response,
            request_params=self.request_params,
        )
        self.assertEqual(parsed_product.image_source, "keepa_images_csv")
        self.assertEqual(
            parsed_product.image_urls,
            [
                "https://m.media-amazon.com/images/I/ghi789.jpg",
                "https://m.media-amazon.com/images/I/jkl012.jpg",
            ],
        )
        self.assertEqual(parsed_product.images_csv, "ghi789.jpg,jkl012.jpg")
        self.assertEqual(mapping_report["image_analysis"]["image_source_path"], "products[0].imagesCSV")

    def test_images_take_priority_over_images_csv(self) -> None:
        raw_response = {
            **self.raw_response,
            "products": [
                {
                    **self.raw_response["products"][0],
                    "imagesCSV": "csv_only_1.jpg,csv_only_2.jpg",
                }
            ],
        }
        parsed_product, _, _ = analyze_keepa_response(
            asin="B0TEST0001",
            raw_response=raw_response,
            request_params=self.request_params,
        )
        self.assertEqual(parsed_product.images_csv, "csv_only_1.jpg,csv_only_2.jpg")
        self.assertEqual(
            parsed_product.image_urls,
            [
                "https://m.media-amazon.com/images/I/abc123.jpg",
                "https://m.media-amazon.com/images/I/def456_m.jpg",
            ],
        )
        self.assertEqual(parsed_product.image_source, "keepa_images")

    def test_count_fields_handle_short_or_missing_arrays(self) -> None:
        parsed_product = parse_keepa_product(
            "B0TEST0002",
            {
                "title": "Short stats",
                "stats": {"current": [], "avg90": [None] * 11 + [-1]},
                "categoryTree": [],
            },
        )
        self.assertIsNone(parsed_product.current_new_offer_count)
        self.assertIsNone(parsed_product.avg90_new_offer_count)
        self.assertIsNone(parsed_product.avg90_seller_count)
        self.assertIsNone(parsed_product.total_offer_count)
        self.assertIsNone(parsed_product.offer_count_fba)
        self.assertIsNone(parsed_product.offer_count_fbm)

    def test_brand_model_fallback_fields_and_legacy_adult_key(self) -> None:
        parsed_product = parse_keepa_product(
            "B0TEST0003",
            {
                "title": "Fallback test",
                "brand": "",
                "manufacturer": "Maker Inc",
                "model": "",
                "partNumber": "PART-1",
                "isAdult": True,
                "categoryTree": [],
            },
        )
        self.assertEqual(parsed_product.brand, "")
        self.assertEqual(parsed_product.manufacturer, "Maker Inc")
        self.assertEqual(parsed_product.model, "")
        self.assertEqual(parsed_product.part_number, "PART-1")
        self.assertTrue(parsed_product.is_adult)
        self.assertEqual(parsed_product.is_adult_source, "isAdult")

    def test_saved_raw_can_regenerate_mapping_report(self) -> None:
        raw_path = ROOT_DIR / "output" / "keepa_inspect" / "B0CJR955SM_raw.json"
        raw_response = json.loads(raw_path.read_text(encoding="utf-8"))
        parsed_product, field_report, mapping_report = analyze_keepa_response(
            asin="B0CJR955SM",
            raw_response=raw_response,
            request_params={
                "domain": 5,
                "asin": "B0CJR955SM",
                "stats": 90,
                "history": 0,
                "offers": 20,
            },
        )

        self.assertEqual(len(parsed_product.image_urls), 4)
        self.assertEqual(parsed_product.images_csv, "")
        self.assertEqual(parsed_product.image_urls[0], "https://m.media-amazon.com/images/I/419M6DWuQVL.jpg")
        self.assertEqual(parsed_product.current_new_offer_count, 1)
        self.assertEqual(parsed_product.avg90_new_offer_count, 1.0)
        self.assertEqual(parsed_product.total_offer_count, 1)
        self.assertFalse(parsed_product.is_adult)
        self.assertEqual(parsed_product.is_adult_source, "isAdultProduct")
        self.assertEqual(field_report["hazardous_materials_summary"]["count"], 27)
        self.assertEqual(mapping_report["image_analysis"]["image_source_path"], "products[0].images[].l")
        self.assertEqual(mapping_report["image_analysis"]["main_image_candidate"], "https://m.media-amazon.com/images/I/419M6DWuQVL.jpg")
        count_mapping = next(item for item in mapping_report["mappings"] if item["rakuten_field"] == "new_offer_counts")
        self.assertEqual(count_mapping["current_value"]["current_new_offer_count"], 1)
        self.assertEqual(count_mapping["current_value"]["avg90_new_offer_count"], 1.0)
        self.assertEqual(count_mapping["current_value"]["total_offer_count"], 1)
        self.assertEqual(mapping_report["hazardous_materials_summary"]["sample"][0], "ETHANOL")


if __name__ == "__main__":
    unittest.main()
