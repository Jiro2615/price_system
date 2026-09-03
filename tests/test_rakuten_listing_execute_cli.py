from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from scripts.listing.master_loader import load_master_data
from scripts.listing.models import AmazonCheckResult, KeepaProductData, to_jsonable
from scripts.listing.preflight_service import build_preflight_result
from scripts.listing.prepare_service import PrepareListingRequest, prepare_listing
from scripts.rakuten_listing_execute import build_execute_cli_result, main


ROOT_DIR = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT_DIR / "tests" / "fixtures"
REFERENCE_MASTER_DIR = ROOT_DIR / "reference" / "legacy_listing"


class RakutenListingExecuteCliTests(unittest.TestCase):
    def _build_eligible_fixture_result(self) -> dict[str, object]:
        return prepare_listing(
            PrepareListingRequest(
                asin="B0ELIGIBLE1",
                store_code="rakuten_1",
                master_dir=REFERENCE_MASTER_DIR,
                offline=True,
                allow_missing_master=True,
                store_settings_json=FIXTURE_DIR / "eligible_store_settings.json",
                amazon_result_json=FIXTURE_DIR / "eligible_amazon_result.json",
                keepa_result_json=FIXTURE_DIR / "eligible_keepa_result.json",
            ),
            master_data_loader=load_master_data,
        )

    def _build_b0cn39x1fc_result(self) -> dict[str, object]:
        saved = json.loads((ROOT_DIR / "output" / "listing" / "B0CN39X1FC_dry_run.json").read_text(encoding="utf-8"))
        return prepare_listing(
            PrepareListingRequest(
                asin="B0CN39X1FC",
                store_code="rakuten_1",
                master_dir=REFERENCE_MASTER_DIR,
                dry_run=True,
                allow_missing_master=True,
            ),
            master_data_loader=load_master_data,
            amazon_fetcher=lambda asin, page_timeout_ms: AmazonCheckResult(**saved["amazon_result"]),
            keepa_fetcher=lambda asin: KeepaProductData(**saved["keepa_result"]),
        )

    def _write_result(self, payload: dict[str, object]) -> Path:
        temp_dir = Path(tempfile.mkdtemp(dir=str(ROOT_DIR)))
        path = temp_dir / "input.json"
        path.write_text(json.dumps(to_jsonable(payload), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def test_plan_only_succeeds_for_eligible_fixture(self) -> None:
        dry_run_result = self._build_eligible_fixture_result()
        input_path = self._write_result(dry_run_result)
        result = build_execute_cli_result(
            dry_run_result,
            input_json_path=input_path,
            asin="B0ELIGIBLE1",
            management_number=str(dry_run_result["management_number"]),
            store="rakuten_1",
            mode="plan_only",
            approved=False,
        )
        self.assertEqual(result["mode"], "plan_only")
        self.assertEqual(result["preflight_status"], "warning")
        self.assertTrue(result["all_management_numbers_match"])
        self.assertTrue(result["ready_for_mock_execute"])
        self.assertTrue(result["ready_for_real_execute"] is False)
        self.assertEqual(len(result["image_execution_plan"]), 4)
        self.assertEqual(result["image_request_summary"]["image_count"], 4)
        self.assertEqual(result["item_request_summary"]["method"], "PUT")
        self.assertEqual(result["inventory_request_summary"]["method"], "PUT")
        self.assertFalse(result["external_actions_performed"])
        self.assertFalse(result["secrets_exposed"])

    def test_plan_only_blocks_on_asin_mismatch(self) -> None:
        dry_run_result = self._build_eligible_fixture_result()
        input_path = self._write_result(dry_run_result)
        result = build_execute_cli_result(
            dry_run_result,
            input_json_path=input_path,
            asin="B0WRONG000",
            management_number=str(dry_run_result["management_number"]),
            store="rakuten_1",
            mode="plan_only",
            approved=False,
        )
        self.assertEqual(result["preflight_status"], "blocked")
        check = {item["key"]: item for item in result["preflight_checks"]}
        self.assertEqual(check["asin_match"]["status"], "blocked")

    def test_plan_only_blocks_on_management_number_mismatch(self) -> None:
        dry_run_result = self._build_eligible_fixture_result()
        input_path = self._write_result(dry_run_result)
        result = build_execute_cli_result(
            dry_run_result,
            input_json_path=input_path,
            asin="B0ELIGIBLE1",
            management_number="wrong_management_number",
            store="rakuten_1",
            mode="plan_only",
            approved=False,
        )
        self.assertEqual(result["preflight_status"], "blocked")
        check = {item["key"]: item for item in result["preflight_checks"]}
        self.assertEqual(check["argument_management_number_match"]["status"], "blocked")

    def test_plan_only_blocks_when_business_ng(self) -> None:
        dry_run_result = self._build_eligible_fixture_result()
        dry_run_result["listing_status"] = "business_ng"
        dry_run_result["execution_allowed"] = False
        dry_run_result["blocking_reasons"] = ["business_ng: threshold"]
        input_path = self._write_result(dry_run_result)
        result = build_execute_cli_result(
            dry_run_result,
            input_json_path=input_path,
            asin="B0ELIGIBLE1",
            management_number=str(dry_run_result["management_number"]),
            store="rakuten_1",
            mode="plan_only",
            approved=False,
        )
        self.assertEqual(result["preflight_status"], "blocked")
        self.assertIn("business_ng: threshold", result["blocking_reasons"])

    def test_plan_only_blocks_when_payload_missing(self) -> None:
        dry_run_result = self._build_eligible_fixture_result()
        dry_run_result["item_payload"] = None
        input_path = self._write_result(dry_run_result)
        result = build_execute_cli_result(
            dry_run_result,
            input_json_path=input_path,
            asin="B0ELIGIBLE1",
            management_number=str(dry_run_result["management_number"]),
            store="rakuten_1",
            mode="plan_only",
            approved=False,
        )
        check = {item["key"]: item for item in result["preflight_checks"]}
        self.assertEqual(check["item_payload_present"]["status"], "blocked")

    def test_plan_only_blocks_when_legacy_spacing_review_exists(self) -> None:
        dry_run_result = self._build_eligible_fixture_result()
        dry_run_result["legacy_spacing_reviews"] = [{"field": "title"}]
        input_path = self._write_result(dry_run_result)
        result = build_execute_cli_result(
            dry_run_result,
            input_json_path=input_path,
            asin="B0ELIGIBLE1",
            management_number=str(dry_run_result["management_number"]),
            store="rakuten_1",
            mode="plan_only",
            approved=False,
        )
        check = {item["key"]: item for item in result["preflight_checks"]}
        self.assertEqual(check["legacy_spacing_reviews_empty"]["status"], "blocked")

    def test_plan_only_blocks_when_matched_forbidden_word_exists(self) -> None:
        dry_run_result = self._build_eligible_fixture_result()
        dry_run_result["matched_forbidden_words"] = [{"word": "NG"}]
        input_path = self._write_result(dry_run_result)
        result = build_execute_cli_result(
            dry_run_result,
            input_json_path=input_path,
            asin="B0ELIGIBLE1",
            management_number=str(dry_run_result["management_number"]),
            store="rakuten_1",
            mode="plan_only",
            approved=False,
        )
        check = {item["key"]: item for item in result["preflight_checks"]}
        self.assertEqual(check["matched_forbidden_words_empty"]["status"], "blocked")

    def test_plan_only_blocks_when_image_plan_is_missing(self) -> None:
        dry_run_result = self._build_eligible_fixture_result()
        dry_run_result["image_download_plan"] = None
        dry_run_result["image_urls"] = []
        input_path = self._write_result(dry_run_result)
        result = build_execute_cli_result(
            dry_run_result,
            input_json_path=input_path,
            asin="B0ELIGIBLE1",
            management_number=str(dry_run_result["management_number"]),
            store="rakuten_1",
            mode="plan_only",
            approved=False,
        )
        check = {item["key"]: item for item in result["preflight_checks"]}
        self.assertEqual(check["image_download_plan_present"]["status"], "blocked")
        self.assertEqual(check["image_urls_present"]["status"], "blocked")

    def test_plan_only_does_not_require_brand_or_model_when_genre_does_not_define_them(self) -> None:
        dry_run_result = deepcopy(self._build_eligible_fixture_result())
        dry_run_result["resolved_attributes"] = {
            name: value
            for name, value in dry_run_result["resolved_attributes"].items()
            if name not in {"ブランド名", "メーカー型番"}
        }
        variant = next(iter(dry_run_result["item_payload"]["variants"].values()))
        variant["attributes"] = [
            attribute
            for attribute in variant["attributes"]
            if attribute.get("name") not in {"ブランド名", "メーカー型番"}
        ]
        input_path = self._write_result(dry_run_result)

        result = build_preflight_result(
            dry_run_result,
            input_json_path=input_path,
            asin="B0ELIGIBLE1",
            management_number=str(dry_run_result["management_number"]),
            store="rakuten_1",
        )

        checks = {item["key"]: item for item in result["checks"]}
        self.assertEqual(checks["brand"]["status"], "ok")
        self.assertEqual(checks["brand"]["expected"], "not required for this genre")
        self.assertEqual(checks["model"]["status"], "ok")
        self.assertEqual(checks["model"]["expected"], "not required for this genre")
        self.assertNotIn("model: non-empty", result["blocking_reasons"])

    def test_b0cn39x1fc_plan_only_reports_allowed_phrase_and_warning_spec(self) -> None:
        dry_run_result = self._build_b0cn39x1fc_result()
        input_path = self._write_result(dry_run_result)
        result = build_execute_cli_result(
            dry_run_result,
            input_json_path=input_path,
            asin="B0CN39X1FC",
            management_number=str(dry_run_result["management_number"]),
            store="rakuten_1",
            mode="plan_only",
            approved=False,
        )
        self.assertEqual(result["preflight_status"], "warning")
        self.assertTrue(result["human_confirmation_required"])
        self.assertEqual(result["listing_status"], "eligible")
        self.assertIn("unresolved specifications require human confirmation before real execute", result["warnings"])
        self.assertEqual(result["item_request_summary"]["method"], "PUT")
        self.assertTrue(any(item["allowed_phrase"] == "クリア" and item["field"] == "title" for item in result["allowed_phrase_matches"]))
        self.assertEqual(result["matched_forbidden_words"], [])
        self.assertEqual(result["legacy_spacing_reviews"], [])

    def test_execute_mode_blocks_on_unresolved_specification(self) -> None:
        dry_run_result = self._build_b0cn39x1fc_result()
        input_path = self._write_result(dry_run_result)
        result = build_execute_cli_result(
            dry_run_result,
            input_json_path=input_path,
            asin="B0CN39X1FC",
            management_number=str(dry_run_result["management_number"]),
            store="rakuten_1",
            mode="execute",
            approved=True,
        )
        self.assertEqual(result["preflight_status"], "blocked")
        self.assertEqual(result["execute_status"], "blocked")
        self.assertFalse(result["ready_for_real_execute"])

    def test_mock_execute_uses_mocks_and_completes(self) -> None:
        dry_run_result = self._build_eligible_fixture_result()
        input_path = self._write_result(dry_run_result)
        result = build_execute_cli_result(
            dry_run_result,
            input_json_path=input_path,
            asin="B0ELIGIBLE1",
            management_number=str(dry_run_result["management_number"]),
            store="rakuten_1",
            mode="mock_execute",
            approved=False,
        )
        self.assertEqual(result["preflight_status"], "warning")
        self.assertIn("mock_execute_result", result)
        self.assertEqual(result["mock_execute_result"]["execute_status"], "completed")
        self.assertFalse(result["external_actions_performed"])

    def test_main_writes_plan_only_json(self) -> None:
        dry_run_result = self._build_eligible_fixture_result()
        input_path = self._write_result(dry_run_result)
        output_path = input_path.parent / "execute_plan.json"
        exit_code = main(
            [
                "--input-json",
                str(input_path),
                "--asin",
                "B0ELIGIBLE1",
                "--management-number",
                str(dry_run_result["management_number"]),
                "--store",
                "rakuten_1",
                "--plan-only",
                "--output-json",
                str(output_path),
            ]
        )
        self.assertEqual(exit_code, 0)
        saved = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["mode"], "plan_only")
        self.assertEqual(saved["preflight_status"], "warning")

    def test_result_is_json_serializable_and_does_not_expose_secret_keys(self) -> None:
        dry_run_result = self._build_eligible_fixture_result()
        input_path = self._write_result(dry_run_result)
        result = build_execute_cli_result(
            dry_run_result,
            input_json_path=input_path,
            asin="B0ELIGIBLE1",
            management_number=str(dry_run_result["management_number"]),
            store="rakuten_1",
            mode="plan_only",
            approved=False,
        )
        text = json.dumps(result, ensure_ascii=False)
        self.assertIn("secrets_exposed", text)
        self.assertNotIn("Authorization", text)
        self.assertNotIn("Cookie", text)


if __name__ == "__main__":
    unittest.main()
