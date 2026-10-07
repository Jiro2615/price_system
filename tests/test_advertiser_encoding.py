"""Local config and mock-only send guard tests. No live DB or HTTP operations."""
from __future__ import annotations

from contextlib import redirect_stdout
import html
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from scripts.listing import quasi_drug_compliance as compliance
from scripts.listing.compliance_text import ComplianceTextError, validate_advertiser_name, validate_advertiser_payload
from scripts.listing.listing_evaluator import build_regulated_product_disclosure
from scripts.listing.listing_execute_service import ExecuteListingRequest, execute_listing
from scripts.listing.rakuten_item_client import build_item_request
from scripts import diagnose_listing_advertiser as diagnostic


GOOD = "株式会社ライト"
BAD = "譬ェ蠑丈シ夂、セ繝ゥ繧、繝・"
NAME_KEY = "RAKUTEN_2_COMPLIANCE_ADVERTISER_NAME"
PHONE_KEY = "RAKUTEN_2_COMPLIANCE_ADVERTISER_PHONE"


class AdvertiserConfigTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.env_path = Path(temp.name) / ".env"
        for patcher in (patch.object(compliance, "ENV_PATH", self.env_path),
                        patch.dict(os.environ, {}, clear=True)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def save(self, name, *, encoding="utf-8", phone="000-0000-0000"):
        self.env_path.write_text(f'{NAME_KEY}="{name}"\n{PHONE_KEY}={phone}\n', encoding=encoding)

    def test_utf8_and_bom_preserve_name_without_global_environment_mutation(self):
        for encoding in ("utf-8", "utf-8-sig"):
            with self.subTest(encoding=encoding):
                self.save(GOOD, encoding=encoding)
                self.assertEqual(compliance._configured("rakuten_2")["advertiser_name"], GOOD)
                self.assertNotIn(NAME_KEY, os.environ)

    def test_current_file_overrides_stale_corrupted_parent_and_is_reread(self):
        os.environ[NAME_KEY] = BAD
        self.save(GOOD)
        self.assertEqual(compliance._configured("rakuten_2")["advertiser_name"], GOOD)
        self.save("株式会社テスト")
        self.assertEqual(compliance._configured("rakuten_2")["advertiser_name"], "株式会社テスト")
        self.assertEqual(os.environ[NAME_KEY], BAD)

    def test_explicit_blank_does_not_restore_old_environment_setting(self):
        os.environ.update({NAME_KEY: GOOD, PHONE_KEY: "old-phone"})
        self.save("")
        self.assertIsNone(compliance._configured("rakuten_2"))

    def test_missing_file_supports_environment_only_deployment(self):
        os.environ.update({NAME_KEY: GOOD, PHONE_KEY: "000-0000-0000"})
        self.assertEqual(compliance._configured("rakuten_2")["advertiser_name"], GOOD)

    def test_corrupted_configuration_raises_not_missing_evidence_even_without_phone(self):
        for phone in ("", "000-0000-0000"):
            self.save(BAD, phone=phone)
            with self.assertRaises(ComplianceTextError) as raised:
                compliance._configured("rakuten_2")
            self.assertIn(NAME_KEY, str(raised.exception))
            self.assertNotIn(BAD, str(raised.exception))
            self.assertNotIn("000-0000-0000", str(raised.exception))

    def test_cp932_file_requires_explicit_utf8_save(self):
        self.save(GOOD, encoding="cp932")
        with self.assertRaisesRegex(ComplianceTextError, "UTF-8"):
            compliance._configured("rakuten_2")

    def test_invalid_config_cannot_turn_into_bypassable_missing_regulated_evidence(self):
        self.save(BAD)
        with patch.object(compliance, "_search_same_jan_items") as search:
            with self.assertRaises(ComplianceTextError):
                compliance.lookup_japanese_regulated_product_evidence(
                    jan_code="0000000000000", manufacturer="メーカー", store_code="rakuten_2", category="化粧品")
            search.assert_not_called()

    def test_store_scoping_and_blank_store(self):
        self.save(GOOD)
        self.assertIsNone(compliance._configured("rakuten_1"))
        self.assertIsNone(compliance._configured(""))


class AdvertiserPayloadTests(unittest.TestCase):
    def test_normal_company_names_are_preserved(self):
        for name in (GOOD, "ライフフォレスト", "譬商事", "株式会社繝", "LifeForest Co., Ltd.", "㈱テスト"):
            validate_advertiser_name(name)

    def test_proven_mojibake_and_replacement_are_blocked_before_or_after_normalization(self):
        misdecoded = GOOD.encode("utf-8").decode("cp932", errors="replace")
        for name in (BAD, misdecoded, "繝ｩ繧､繝輔ヵ繧ｩ繝ｬ繧ｹ繝・", "test\ufffd", "test\x00"):
            with self.subTest(name=name), self.assertRaises(ComplianceTextError):
                validate_advertiser_name(name)

    def test_only_labelled_advertiser_is_checked_in_pc_sp_sales_and_html(self):
        for field in ("pc", "sp", "salesDescription"):
            body = f"広告文責：<span>{BAD}</span><br />電話番号: not-logged"
            payload = ({"salesDescription": body} if field == "salesDescription" else
                       {"productDescription": {field: body}})
            with self.subTest(field=field), self.assertRaises(ComplianceTextError):
                validate_advertiser_payload(payload)
        validate_advertiser_payload({"productDescription": {"pc": f"商品名: {BAD}<br />広告文責: {GOOD}"}})
        validate_advertiser_payload({"productDescription": None})
        validate_advertiser_payload({"productDescription": "legacy malformed field"})
        with self.assertRaises(ComplianceTextError):
            validate_advertiser_payload({"productDescription": {"pc": "広告文責: " + html.escape(BAD)}})

    def test_disclosure_and_api_builder_cannot_reintroduce_corrupted_name(self):
        evidence = {"advertiser_name": BAD, "advertiser_phone": "000-0000-0000", "manufacturer": "メーカー",
                    "product_category": "化粧品"}
        with self.assertRaises(ComplianceTextError):
            build_regulated_product_disclosure(evidence)
        with self.assertRaises(ComplianceTextError):
            build_item_request("test-item", {"productDescription": {"pc": f"広告文責: {BAD}"}}, {})
        evidence["advertiser_name"] = GOOD
        body = build_regulated_product_disclosure(evidence)
        payload = {"productDescription": {"pc": body, "sp": body}}
        self.assertEqual(build_item_request("test-item", payload, {}).payload["productDescription"]["pc"], body)

    def test_stale_forced_listing_files_block_before_any_image_or_api_write(self):
        dry = {"asin": "B000TEST01", "store_code": "rakuten_2", "management_number": "test-item",
               "listing_status": "eligible", "execution_allowed": True, "blocking_reasons": [],
               "item_payload": {"productDescription": {"pc": f"広告文責: {BAD}"}},
               "inventory_payload": {}, "forced_bypass_checks": [{"rule": "regulated_evidence"}]}
        download = Mock(return_value={"items": []})
        image = Mock()
        item = Mock()
        inventory = Mock()
        result = execute_listing(ExecuteListingRequest(dry_run_result=dry, execute=True, approved=True),
                                 image_downloader=download, image_client=image, item_client=item,
                                 inventory_client=inventory)
        self.assertEqual(result["execute_status"], "validation_failed")
        self.assertEqual(result["final_state"], "blocked")
        self.assertIn("広告文責", result["errors"][0])
        download.assert_not_called()
        image.upload_image.assert_not_called()
        item.put_item.assert_not_called()
        inventory.bulk_upsert.assert_not_called()
        dry["item_payload"]["productDescription"]["pc"] = f"広告文責: {GOOD}"
        result = execute_listing(ExecuteListingRequest(dry_run_result=dry, execute=True, approved=True),
                                 image_downloader=download)
        self.assertEqual(result["execute_status"], "image_failed")
        download.assert_called_once()

    def test_diagnostic_omits_phone_credentials_and_catches_bad_configuration(self):
        output = io.StringIO()
        with patch("sys.argv", ["diagnose_listing_advertiser.py"]), patch.object(diagnostic, "_configured", return_value={
            "advertiser_name": GOOD, "advertiser_phone": "private-phone-never-output"}), redirect_stdout(output):
            self.assertEqual(diagnostic.main(), 0)
        self.assertEqual(json.loads(output.getvalue())["advertiser_name"], GOOD)
        self.assertNotIn("private-phone-never-output", output.getvalue())
        output = io.StringIO()
        with patch("sys.argv", ["diagnose_listing_advertiser.py"]), patch.object(diagnostic, "_configured", side_effect=ComplianceTextError("invalid")), redirect_stdout(output):
            self.assertEqual(diagnostic.main(), 1)
        self.assertEqual(json.loads(output.getvalue())["status"], "invalid_configuration")


if __name__ == "__main__":
    unittest.main()
