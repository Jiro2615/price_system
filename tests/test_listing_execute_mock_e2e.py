from __future__ import annotations

import json
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path

from scripts.listing.image_validator import ValidatedImageResult
from scripts.listing.listing_execute_service import ExecuteListingRequest, execute_listing
from scripts.listing.master_loader import load_master_data
from scripts.listing.prepare_service import PrepareListingRequest, prepare_listing
from scripts.listing.rakuten_image_client import RakutenImageClient, RakutenImageUploadResult
from scripts.listing.rakuten_inventory_client import RakutenInventoryClient, RakutenInventoryResult
from scripts.listing.rakuten_item_client import RakutenItemClient, RakutenItemResult


ROOT_DIR = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT_DIR / "tests" / "fixtures"
REFERENCE_MASTER_DIR = ROOT_DIR / "reference" / "legacy_listing"


class ListingExecuteMockE2ETests(unittest.TestCase):
    def _build_eligible_dry_run(self) -> dict[str, object]:
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

    def _http_get(self, url: str, timeout_seconds: float, allow_redirects: bool):  # noqa: ANN001
        class Response:
            status_code = 200
            headers = {"Content-Type": "image/jpeg"}
            content = b"fake-image-bytes"
            final_url = url

        return Response()

    def _mock_validator_success(self, items):  # noqa: ANN001
        validated_items = []
        for item in items:
            validated_items.append(
                ValidatedImageResult(
                    role=getattr(item, "role", None),
                    order=getattr(item, "order", None),
                    source_url=getattr(item, "source_url", None),
                    planned_filename=getattr(item, "planned_filename", None),
                    relative_path=getattr(item, "relative_path", None),
                    local_path=getattr(item, "local_path", None),
                    local_exists=True,
                    download_status=getattr(item, "download_status", None),
                    http_status=getattr(item, "http_status", None),
                    content_type=getattr(item, "content_type", None),
                    file_size=getattr(item, "file_size", 16),
                    width=1000,
                    height=1000,
                    sha256=sha256(str(getattr(item, "local_path", "")).encode("utf-8")).hexdigest(),
                    validation_status="valid",
                    validation_errors=[],
                    upload_status=getattr(item, "upload_status", "not_uploaded"),
                    rakuten_image_url=getattr(item, "rakuten_image_url", None),
                    error_type=None,
                    error_message=None,
                )
            )
        return {
            "items": validated_items,
            "valid_count": len(validated_items),
            "invalid_count": 0,
            "failed_count": 0,
        }

    def test_eligible_with_approval_reaches_completed(self) -> None:
        dry_run_result = self._build_eligible_dry_run()
        with tempfile.TemporaryDirectory(dir=str(ROOT_DIR)) as temp_dir:
            image_client = RakutenImageClient(
                uploader=lambda request: RakutenImageUploadResult(
                    upload_status="uploaded",
                    rakuten_image_url=f"https://image.rakuten.example/{request.filename}",
                    request_summary={"filename": request.filename},
                    response_status=201,
                )
            )
            item_client = RakutenItemClient(
                sender=lambda request: RakutenItemResult(
                    success=True,
                    management_number=request.management_number,
                    http_status=200,
                    response_body_summary={"result": "ok"},
                    retryable=False,
                    request_summary={"url": request.url},
                )
            )
            inventory_client = RakutenInventoryClient(
                sender=lambda request: RakutenInventoryResult(
                    success=True,
                    management_number=request.management_number,
                    http_status=200,
                    response_body_summary={"result": "ok"},
                    retryable=False,
                    request_summary={"url": request.url},
                )
            )

            result = execute_listing(
                ExecuteListingRequest(
                    dry_run_result=dry_run_result,
                    execute=True,
                    approved=True,
                    asin="B0ELIGIBLE1",
                    management_number=str(dry_run_result["management_number"]),
                    output_root=Path(temp_dir),
                    image_headers={"Authorization": "Bearer top-secret", "Cookie": "session=abc"},
                    item_headers={"Authorization": "ESA secret"},
                    inventory_headers={"Authorization": "ESA secret"},
                ),
                http_get=self._http_get,
                image_validator=self._mock_validator_success,
                image_client=image_client,
                item_client=item_client,
                inventory_client=inventory_client,
            )

        self.assertEqual(result["execute_status"], "completed")
        self.assertEqual(result["final_state"], "completed")
        self.assertEqual(len(result["rakuten_image_urls_after"]), 4)
        self.assertIsNotNone(result["item_result"])
        self.assertIsNotNone(result["inventory_result"])
        self.assertNotEqual(result["original_item_payload_hash"], result["executed_item_payload_hash"])
        self.assertEqual(dry_run_result["item_payload"]["images"][0]["location"], f"/{dry_run_result['management_number']}_1.jpg")

    def test_no_approval_stops_before_any_client_call(self) -> None:
        dry_run_result = self._build_eligible_dry_run()
        call_log: list[str] = []

        def http_get(url: str, timeout_seconds: float, allow_redirects: bool):  # noqa: ANN001
            call_log.append("http")
            return self._http_get(url, timeout_seconds, allow_redirects)

        result = execute_listing(
            ExecuteListingRequest(dry_run_result=dry_run_result, execute=True, approved=False, asin="B0ELIGIBLE1"),
            http_get=http_get,
        )

        self.assertEqual(result["execute_status"], "approval_required")
        self.assertEqual(call_log, [])
        self.assertIsNone(result["download_result"])

    def test_business_ng_stops_before_any_client_call(self) -> None:
        dry_run_result = self._build_eligible_dry_run()
        dry_run_result["listing_status"] = "business_ng"
        dry_run_result["execution_allowed"] = False
        dry_run_result["blocking_reasons"] = ["business_ng: threshold"]

        call_log: list[str] = []

        def http_get(url: str, timeout_seconds: float, allow_redirects: bool):  # noqa: ANN001
            call_log.append("http")
            return self._http_get(url, timeout_seconds, allow_redirects)

        result = execute_listing(
            ExecuteListingRequest(dry_run_result=dry_run_result, execute=True, approved=True, asin="B0ELIGIBLE1"),
            http_get=http_get,
        )

        self.assertEqual(result["execute_status"], "validation_failed")
        self.assertEqual(call_log, [])

    def test_image_download_failure_blocks_later_steps(self) -> None:
        dry_run_result = self._build_eligible_dry_run()
        with tempfile.TemporaryDirectory(dir=str(ROOT_DIR)) as temp_dir:
            result = execute_listing(
                ExecuteListingRequest(
                    dry_run_result=dry_run_result,
                    execute=True,
                    approved=True,
                    asin="B0ELIGIBLE1",
                    output_root=Path(temp_dir),
                ),
                http_get=lambda url, timeout_seconds, allow_redirects: (_ for _ in ()).throw(RuntimeError("network disabled")),
            )

        self.assertEqual(result["execute_status"], "image_failed")
        self.assertIsNone(result["item_result"])
        self.assertIsNone(result["inventory_result"])

    def test_validation_failure_blocks_upload_and_api(self) -> None:
        dry_run_result = self._build_eligible_dry_run()
        with tempfile.TemporaryDirectory(dir=str(ROOT_DIR)) as temp_dir:
            result = execute_listing(
                ExecuteListingRequest(
                    dry_run_result=dry_run_result,
                    execute=True,
                    approved=True,
                    asin="B0ELIGIBLE1",
                    output_root=Path(temp_dir),
                ),
                http_get=self._http_get,
                image_validator=lambda items: {"items": [type("Bad", (), {"validation_status": "invalid"})()]},
            )

        self.assertEqual(result["execute_status"], "image_failed")
        self.assertEqual(result["image_upload_results"], [])
        self.assertIsNone(result["item_result"])

    def test_image_upload_failure_blocks_item_and_inventory(self) -> None:
        dry_run_result = self._build_eligible_dry_run()
        with tempfile.TemporaryDirectory(dir=str(ROOT_DIR)) as temp_dir:
            image_client = RakutenImageClient(
                uploader=lambda request: RakutenImageUploadResult(
                    upload_status="failed",
                    rakuten_image_url=None,
                    request_summary={"filename": request.filename},
                    response_status=500,
                    error_type="upload_error",
                    error_message="upload failed",
                )
            )
            result = execute_listing(
                ExecuteListingRequest(
                    dry_run_result=dry_run_result,
                    execute=True,
                    approved=True,
                    asin="B0ELIGIBLE1",
                    output_root=Path(temp_dir),
                ),
                http_get=self._http_get,
                image_client=image_client,
                image_validator=self._mock_validator_success,
            )

        self.assertEqual(result["execute_status"], "image_failed")
        self.assertIsNone(result["item_result"])
        self.assertIsNone(result["inventory_result"])

    def test_item_failure_blocks_inventory(self) -> None:
        dry_run_result = self._build_eligible_dry_run()
        with tempfile.TemporaryDirectory(dir=str(ROOT_DIR)) as temp_dir:
            image_client = RakutenImageClient(
                uploader=lambda request: RakutenImageUploadResult(
                    upload_status="uploaded",
                    rakuten_image_url=f"https://image.rakuten.example/{request.filename}",
                    request_summary={"filename": request.filename},
                    response_status=201,
                )
            )
            item_client = RakutenItemClient(
                sender=lambda request: RakutenItemResult(
                    success=False,
                    management_number=request.management_number,
                    http_status=500,
                    response_body_summary={"result": "ng"},
                    retryable=True,
                    request_summary={"url": request.url},
                    error_type="server_error",
                    error_message="item failed",
                )
            )
            inventory_calls: list[str] = []
            inventory_client = RakutenInventoryClient(
                sender=lambda request: inventory_calls.append("inventory") or RakutenInventoryResult(
                    success=True,
                    management_number=request.management_number,
                    http_status=200,
                    response_body_summary={"result": "ok"},
                    retryable=False,
                    request_summary={"url": request.url},
                )
            )
            result = execute_listing(
                ExecuteListingRequest(
                    dry_run_result=dry_run_result,
                    execute=True,
                    approved=True,
                    asin="B0ELIGIBLE1",
                    output_root=Path(temp_dir),
                ),
                http_get=self._http_get,
                image_client=image_client,
                image_validator=self._mock_validator_success,
                item_client=item_client,
                inventory_client=inventory_client,
            )

        self.assertEqual(result["execute_status"], "item_failed")
        self.assertEqual(inventory_calls, [])

    def test_inventory_failure_preserves_item_success(self) -> None:
        dry_run_result = self._build_eligible_dry_run()
        with tempfile.TemporaryDirectory(dir=str(ROOT_DIR)) as temp_dir:
            image_client = RakutenImageClient(
                uploader=lambda request: RakutenImageUploadResult(
                    upload_status="uploaded",
                    rakuten_image_url=f"https://image.rakuten.example/{request.filename}",
                    request_summary={"filename": request.filename},
                    response_status=201,
                )
            )
            item_client = RakutenItemClient(
                sender=lambda request: RakutenItemResult(
                    success=True,
                    management_number=request.management_number,
                    http_status=200,
                    response_body_summary={"result": "ok"},
                    retryable=False,
                    request_summary={"url": request.url},
                )
            )
            inventory_client = RakutenInventoryClient(
                sender=lambda request: RakutenInventoryResult(
                    success=False,
                    management_number=request.management_number,
                    http_status=503,
                    response_body_summary={"result": "retry"},
                    retryable=True,
                    request_summary={"url": request.url},
                    error_type="server_error",
                    error_message="inventory failed",
                )
            )
            result = execute_listing(
                ExecuteListingRequest(
                    dry_run_result=dry_run_result,
                    execute=True,
                    approved=True,
                    asin="B0ELIGIBLE1",
                    output_root=Path(temp_dir),
                ),
                http_get=self._http_get,
                image_client=image_client,
                image_validator=self._mock_validator_success,
                item_client=item_client,
                inventory_client=inventory_client,
            )

        self.assertEqual(result["execute_status"], "inventory_failed")
        self.assertEqual(result["final_state"], "partial_failure")
        self.assertEqual(result["item_result"]["http_status"], 200)
        self.assertEqual(result["inventory_result"]["http_status"], 503)

    def test_authorization_and_cookie_are_not_leaked(self) -> None:
        dry_run_result = self._build_eligible_dry_run()
        with tempfile.TemporaryDirectory(dir=str(ROOT_DIR)) as temp_dir:
            image_client = RakutenImageClient(
                uploader=lambda request: RakutenImageUploadResult(
                    upload_status="uploaded",
                    rakuten_image_url=f"https://image.rakuten.example/{request.filename}",
                    request_summary={"headers": {"Authorization": "secret", "Cookie": "session=abc"}},
                    response_status=201,
                )
            )
            item_client = RakutenItemClient(
                sender=lambda request: RakutenItemResult(
                    success=True,
                    management_number=request.management_number,
                    http_status=200,
                    response_body_summary={"result": "ok"},
                    retryable=False,
                    request_summary={"headers": {"Authorization": "secret"}},
                )
            )
            inventory_client = RakutenInventoryClient(
                sender=lambda request: RakutenInventoryResult(
                    success=True,
                    management_number=request.management_number,
                    http_status=200,
                    response_body_summary={"result": "ok"},
                    retryable=False,
                    request_summary={"headers": {"Authorization": "secret"}},
                )
            )
            result = execute_listing(
                ExecuteListingRequest(
                    dry_run_result=dry_run_result,
                    execute=True,
                    approved=True,
                    asin="B0ELIGIBLE1",
                    output_root=Path(temp_dir),
                    image_headers={"Authorization": "Bearer top-secret", "Cookie": "session=abc"},
                    item_headers={"Authorization": "ESA secret"},
                    inventory_headers={"Authorization": "ESA secret"},
                ),
                http_get=self._http_get,
                image_client=image_client,
                image_validator=self._mock_validator_success,
                item_client=item_client,
                inventory_client=inventory_client,
            )

        serialized = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("top-secret", serialized)
        self.assertNotIn("session=abc", serialized)
        self.assertNotIn("ESA secret", serialized)


if __name__ == "__main__":
    unittest.main()
