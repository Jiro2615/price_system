from __future__ import annotations

import unittest
from unittest.mock import patch

from scripts.listing.quasi_drug_compliance import (
    has_same_jan_rakuten_candidate,
    lookup_japanese_regulated_product_evidence,
)


class _Response:
    status_code = 200
    headers: dict[str, str] = {}

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return {
            # The current Ichiba API returns its collection under the
            # capitalised key.  Keep this fixture aligned with production.
            "Items": [
                {
                    "shopName": "楽天24",
                    "itemUrl": "https://item.rakuten.co.jp/rakuten24/example/",
                    "itemCaption": (
                        "商品区分：医薬部外品"
                        "【原産国】日本"
                        "【ブランド】アクアレーベル"
                        "【発売元、製造元、輸入元又は販売元】資生堂"
                        "・単品JAN：4909978180294"
                    ),
                }
            ]
        }


class QuasiDrugComplianceTests(unittest.TestCase):
    @patch("scripts.listing.quasi_drug_compliance.requests.get")
    @patch("scripts.listing.quasi_drug_compliance.os.getenv")
    def test_exact_jan_candidate_is_detected_without_regulated_caption_facts(self, getenv, get) -> None:
        getenv.return_value = "configured"
        response = _Response()
        response.json = lambda: {
            "Items": [
                {
                    "shopName": "美容用品店",
                    "itemName": "美容器具 4972525533379",
                    "itemCaption": "商品仕様のみ",
                }
            ]
        }
        get.return_value = response

        self.assertTrue(has_same_jan_rakuten_candidate(jan_code="4972525533379"))

    @patch("scripts.listing.quasi_drug_compliance._configured")
    @patch("scripts.listing.quasi_drug_compliance.requests.get")
    @patch("scripts.listing.quasi_drug_compliance.os.getenv")
    def test_same_jan_caption_accepts_japan_operating_company_alias(
        self,
        getenv,
        get,
        configured,
    ) -> None:
        configured.return_value = {"advertiser_name": "LifeForest", "advertiser_phone": "000-0000-0000"}
        getenv.return_value = "configured"
        get.return_value = _Response()

        evidence = lookup_japanese_regulated_product_evidence(
            jan_code="4909978180294",
            manufacturer="資生堂ジャパン (SHISEIDO JAPAN)",
            store_code="rakuten_2",
            category="医薬部外品",
        )

        self.assertIsNotNone(evidence)
        assert evidence is not None
        self.assertEqual(evidence["manufacturer"], "資生堂ジャパン (SHISEIDO JAPAN)")
        self.assertEqual(evidence["country_of_origin"], "日本")
        self.assertEqual(evidence["product_category"], "医薬部外品")
        self.assertEqual(evidence["evidence_source"], "rakuten_same_jan_search")


if __name__ == "__main__":
    unittest.main()
