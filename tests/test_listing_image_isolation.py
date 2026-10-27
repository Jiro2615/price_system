"""Regression coverage for the September 26 same-second image collisions.

All images and service responses are generated locally; network/DB calls fail.
"""
from __future__ import annotations

import copy
import io
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image

from scripts.listing.image_downloader import HttpFetchResponse, download_image_plan
from scripts.listing.image_plan import build_image_download_plan, normalize_image_download_plan
from scripts.listing.image_overlay import overlay_downloader
from scripts.listing.listing_execute_service import ExecuteListingRequest, execute_listing
from scripts.listing.rakuten_image_client import RakutenImageClient, RakutenImageUploadResult
from scripts.listing.rakuten_item_client import RakutenItemClient, RakutenItemResult
from scripts.listing.rakuten_inventory_client import RakutenInventoryClient, RakutenInventoryResult
from scripts.listing.real_execute_plan_service import _build_image_plan
from scripts.listing.real_execute_service import _restore_uploaded_image_plan, RealExecuteRequest, build_real_execute_result


PAIRS = (
    (("B00LL40EWI", "20260926202326_187_4f86"), ("B00LL40F0Y", "20260926202326_187_0382")),
    (("B00LL40KVS", "20260926202350_187_64c1"), ("B00LL40J3M", "20260926202350_187_d5e3")),
    (("B0013N0G2A", "20260926202756_187_8a84"), ("B001C09BS4", "20260926202756_187_2107")),
)


def jpeg(color):
    stream = io.BytesIO()
    Image.new("RGB", (16, 16), color).save(stream, "JPEG")
    return stream.getvalue()


def prepared(asin, management_number, *, legacy=False):
    source = f"https://images.example/{asin}.jpg"
    plan = build_image_download_plan(asin=asin, image_base_name=management_number,
                                    image_urls=[source], image_source="fixture", listing_status="eligible")
    cabinet = {"folder_path": "13649221/2026081701", "folder_id": 1, "shop_url": "lifeforest"}
    if legacy:
        plan.pop("filename_policy")
        name = management_number.rsplit("_", 1)[0] + "_1.jpg"
        plan["items"][0].update(planned_filename=name, planned_relative_path=f"images/legacy/{name}",
                                item_location=f"/{cabinet['folder_path']}/{name}")
    return dict(asin=asin, store_code="rakuten_2", management_number=management_number,
                management_number_candidates={"legacy_candidate": management_number.rsplit("_", 1)[0]},
                listing_status="eligible", execution_allowed=True, blocking_reasons=[],
                store_settings={"cabinet": cabinet}, image_urls=[source], image_download_plan=plan,
                item_payload={"title": "文具", "variants": {management_number: {"standardPrice": "1000"}}},
                inventory_payload={"mode": "ABSOLUTE", "quantity": 1})


class ImageIsolationTests(unittest.TestCase):
    def setUp(self):
        for name in ("psycopg.connect", "requests.sessions.Session.request"):
            guard = patch(name, side_effect=AssertionError("Live services forbidden"))
            guard.start()
            self.addCleanup(guard.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.red, self.blue = jpeg("red"), jpeg("blue")

    def fetch(self, payload):
        return Mock(return_value=HttpFetchResponse(200, {"Content-Type": "image/jpeg"}, payload))

    def run_listing(self, dry, *, http_get=None, fail_item=False, **flags):
        uploaded, item_requests, inventories = [], [], []

        def upload(request):
            uploaded.append((request, Path(request.local_path).read_bytes()))
            return RakutenImageUploadResult("uploaded", request.metadata["item_location"], {}, 200)

        def put_item(request):
            item_requests.append(request)
            if fail_item:
                return RakutenItemResult(False, request.management_number, 500, {}, True, {}, error_message="test failure")
            return RakutenItemResult(True, request.management_number, 200, {}, False, {})

        def put_inventory(request):
            inventories.append(request)
            return RakutenInventoryResult(True, request.management_number, 200, {}, False, {})

        result = execute_listing(
            ExecuteListingRequest(dry, execute=True, approved=True, output_root=self.root, **flags),
            http_get=http_get or self.fetch(self.red), category_checker=lambda _: None,
            image_client=RakutenImageClient(uploader=upload), item_client=RakutenItemClient(sender=put_item),
            inventory_client=RakutenInventoryClient(sender=put_inventory),
        )
        return result, uploaded, item_requests, inventories

    def test_three_reported_pairs_keep_distinct_names_and_actual_upload_bytes(self):
        for pair in PAIRS:
            with self.subTest(pair=pair):
                requests = []
                for identity, payload in zip(pair, (self.red, self.blue)):
                    dry = prepared(*identity, legacy=True)
                    before = copy.deepcopy(dry)
                    result, uploaded, items, inventory = self.run_listing(dry, http_get=self.fetch(payload))
                    self.assertEqual(result["execute_status"], "completed", result)
                    request, sent_bytes = uploaded[0]
                    self.assertEqual(sent_bytes, payload)
                    self.assertEqual(items[0].payload["images"][0]["location"], request.metadata["item_location"])
                    self.assertEqual(len(inventory), 1)
                    self.assertEqual(dry, before, "saved input should not be mutated")
                    self.assertNotEqual(request.filename, dry["image_download_plan"]["items"][0]["planned_filename"])
                    self.assertRegex(request.filename, r"^[a-z2-7]{16}\.jpg$")
                    self.assertLessEqual(len(request.filename.encode("ascii")), 20)
                    requests.append(request)
                self.assertNotEqual(requests[0].filename, requests[1].filename)
                self.assertNotEqual(requests[0].metadata["item_location"], requests[1].metadata["item_location"])

    def test_full_management_suffix_source_order_and_asin_all_isolate_names(self):
        original = prepared(*PAIRS[0][0])
        plans = [original["image_download_plan"]]
        for change in ({"asin": "B000OTHER1"}, {"image_base_name": PAIRS[0][1][1]},
                       {"image_urls": ["https://images.example/changed.jpg"]}):
            args = dict(asin=original["asin"], image_base_name=original["management_number"],
                        image_urls=original["image_urls"], image_source="fixture", listing_status="eligible")
            plans.append(build_image_download_plan(**(args | change)))
        names = [plan["items"][0]["planned_filename"] for plan in plans]
        self.assertEqual(len(set(names)), 4)
        multi = build_image_download_plan(asin=original["asin"], image_base_name=original["management_number"],
            image_urls=original["image_urls"] * 2, image_source="fixture", listing_status="eligible")
        self.assertEqual(multi["items"][0]["planned_filename"], names[0])
        self.assertNotEqual(multi["items"][0]["planned_filename"], multi["items"][1]["planned_filename"])

    def test_preview_preparation_and_upload_use_the_same_name(self):
        for legacy in (False, True):
            dry = prepared(*PAIRS[0][1], legacy=legacy)
            preview = _build_image_plan(dry, {"cabinet_config": dry["store_settings"]["cabinet"]}, dry["asin"])
            result, uploaded, _, _ = self.run_listing(dry)
            self.assertEqual(result["execute_status"], "completed")
            self.assertEqual(preview["items"][0]["file_name"], uploaded[0][0].filename)
            self.assertEqual(preview["items"][0]["item_location"], uploaded[0][0].metadata["item_location"])
            if not legacy:
                self.assertEqual(preview["items"][0]["file_name"], dry["image_download_plan"]["items"][0]["planned_filename"])

    def test_store1_also_uses_isolated_images(self):
        dry = prepared(*PAIRS[0][0], legacy=True)
        dry["store_code"] = "rakuten_1"
        result, uploaded, _, _ = self.run_listing(dry)
        self.assertEqual(result["execute_status"], "completed")
        self.assertNotEqual(uploaded[0][0].filename, dry["image_download_plan"]["items"][0]["planned_filename"])

    def test_existing_file_is_never_reused_by_existence_alone(self):
        plan = prepared(*PAIRS[0][0], legacy=True)["image_download_plan"]
        old = self.root / plan["items"][0]["planned_relative_path"]
        old.parent.mkdir(parents=True)
        old.write_bytes(self.red)
        fetch = self.fetch(self.blue)
        result = download_image_plan(plan, output_root=self.root, http_get=fetch)
        fetch.assert_called_once()
        image = result["items"][0]
        self.assertEqual(image.download_status, "downloaded")
        self.assertNotEqual(Path(image.local_path), old)
        self.assertEqual(Path(image.local_path).read_bytes(), self.blue)
        self.assertEqual(old.read_bytes(), self.red)

    def test_concurrent_downloads_with_identical_legacy_paths_are_isolated(self):
        plan = prepared(*PAIRS[0][0], legacy=True)["image_download_plan"]
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(download_image_plan, plan, output_root=self.root, http_get=self.fetch(data))
                       for data in (self.red, self.blue)]
            images = [future.result()["items"][0] for future in futures]
        self.assertNotEqual(images[0].local_path, images[1].local_path)
        self.assertEqual(Path(images[0].local_path).read_bytes(), self.red)
        self.assertEqual(Path(images[1].local_path).read_bytes(), self.blue)

    def test_failed_download_does_not_fall_back_to_old_file_or_send(self):
        dry = prepared(*PAIRS[0][0])
        old = self.root / dry["image_download_plan"]["items"][0]["planned_relative_path"]
        old.parent.mkdir(parents=True)
        old.write_bytes(self.red)
        for fetch in (Mock(side_effect=TimeoutError("timeout")), Mock(return_value=HttpFetchResponse(404, {}, b""))):
            result, uploaded, items, inventories = self.run_listing(dry, http_get=fetch)
            self.assertEqual(result["execute_status"], "image_failed")
            self.assertEqual((uploaded, items, inventories), ([], [], []))
            self.assertEqual(old.read_bytes(), self.red)

    def test_invalid_image_never_reaches_cabinet(self):
        result, uploaded, items, inventories = self.run_listing(prepared(*PAIRS[0][0]), http_get=self.fetch(b"bad jpeg"))
        self.assertEqual(result["execute_status"], "image_failed")
        self.assertEqual((uploaded, items, inventories), ([], [], []))

    def test_new_image_upload_resume_retains_new_names_without_download(self):
        dry = prepared(*PAIRS[0][0])
        fetch = Mock(side_effect=AssertionError("resume must not download"))
        result, uploaded, items, inventories = self.run_listing(dry, http_get=fetch, resume_after_image_upload=True)
        self.assertEqual(result["execute_status"], "completed", result)
        self.assertEqual(uploaded, [])
        self.assertTrue(items[0].payload["images"][0]["location"].endswith(dry["image_download_plan"]["items"][0]["planned_filename"]))
        self.assertEqual(len(inventories), 1)
        fetch.assert_not_called()

    def test_unsafe_old_image_upload_resume_is_rejected_before_any_send(self):
        dry = prepared(*PAIRS[0][0], legacy=True)
        fetch = Mock(side_effect=AssertionError("must not download"))
        result, uploaded, items, inventories = self.run_listing(dry, http_get=fetch, resume_after_image_upload=True)
        self.assertEqual(result["execute_status"], "validation_failed")
        self.assertIn("旧方式", result["errors"][0])
        self.assertEqual((uploaded, items, inventories), ([], [], []))
        fetch.assert_not_called()

    def test_saved_shared_location_cannot_override_safe_filename_in_resume(self):
        dry = prepared(*PAIRS[0][0])
        dry["image_download_plan"]["items"][0]["item_location"] = "/folder/shared.jpg"
        result, uploaded, items, inventories = self.run_listing(dry, resume_after_image_upload=True)
        self.assertEqual(result["execute_status"], "validation_failed")
        self.assertEqual((uploaded, items, inventories), ([], [], []))

    def test_migrated_old_plan_retry_restores_confirmed_new_images(self):
        dry = prepared(*PAIRS[0][0], legacy=True)
        result, uploaded, _, inventories = self.run_listing(dry, fail_item=True)
        self.assertEqual(result["execute_status"], "item_failed")
        self.assertEqual(inventories, [])
        history = {key: dry[key] for key in ("asin", "store_code", "management_number")}
        history["response_summaries"] = {"uploaded_image_plan": result["uploaded_image_plan"]}
        for resume_flag in ("resume_after_image_upload", "resume_after_item_upsert"):
            retry = copy.deepcopy(dry)
            _restore_uploaded_image_plan(retry, history)
            resumed, reuploaded, _, _ = self.run_listing(retry, **{resume_flag: True})
            self.assertEqual(resumed["execute_status"], "completed")
            self.assertEqual(reuploaded, [])
            self.assertEqual(resumed["rakuten_image_urls_after"], [uploaded[0][0].metadata["item_location"]])
        for field, value in (("asin", "B000OTHER1"), ("store_code", "rakuten_1"), ("management_number", "other")):
            with self.subTest(field=field), self.assertRaises(ValueError):
                _restore_uploaded_image_plan(copy.deepcopy(dry), {**history, field: value})
        changed = copy.deepcopy(dry)
        changed["image_download_plan"]["items"][0]["source_url"] += "?changed=1"
        with self.assertRaises(ValueError):
            _restore_uploaded_image_plan(changed, history)

    def test_real_entry_blocks_old_resume_before_folder_creation_or_history_write(self):
        dry = prepared(*PAIRS[0][0], legacy=True)
        request = RealExecuteRequest(Path("readiness"), Path("dry"), Path("preflight"), Path("mock"),
            dry["asin"], dry["management_number"], "rakuten_2", resume_after_image_upload=True)
        module = "scripts.listing.real_execute_service."
        with patch(module + "load_json", side_effect=lambda path: dry if path == Path("dry") else {}), \
             patch(module + "_validate_readiness_inputs", return_value=[]), \
             patch(module + "_validate_execute_guards", return_value=[]), \
             patch(module + "_build_transport_ready_summary", side_effect=AssertionError("no transport")), \
             patch(module + "_write_history", side_effect=AssertionError("no history overwrite")):
            result = build_real_execute_result(request)
        self.assertEqual(result["final_status"], "blocked")
        self.assertIn("旧方式", result["blocking_reasons"][0])

    def test_legacy_inventory_only_resume_does_not_rewrite_images_or_item(self):
        dry = prepared(*PAIRS[0][0], legacy=True)
        result, uploaded, items, inventories = self.run_listing(dry, resume_after_item_upsert=True)
        self.assertEqual(result["execute_status"], "completed")
        self.assertEqual((uploaded, items), ([], []))
        self.assertEqual(len(inventories), 1)
        self.assertEqual(result["rakuten_image_urls_after"], [dry["image_download_plan"]["items"][0]["item_location"]])

    def test_disabled_plan_does_not_fetch_or_create_directory(self):
        plan = prepared(*PAIRS[0][0])["image_download_plan"]
        plan["execution_allowed"] = False
        root = self.root / "no-files"
        fetch = Mock(side_effect=AssertionError("must not download"))
        result = download_image_plan(plan, output_root=root, http_get=fetch)
        self.assertEqual(result["items"][0].download_status, "skipped")
        self.assertFalse(root.exists())
        fetch.assert_not_called()

    def test_overlay_keeps_original_and_destination_identity(self):
        import base64
        dry = prepared(*PAIRS[0][0])
        plan = normalize_image_download_plan(dry["image_download_plan"], asin=dry["asin"], image_base_name=dry["management_number"])
        wrapped = overlay_downloader(download_image_plan, store_code="rakuten_2", shop_url="lifeforest",
                                     item_payload=dry["item_payload"], settings={"enabled": True,
                                     "logo_base64": base64.b64encode(self.blue).decode("ascii")})
        result = wrapped(plan, output_root=self.root, http_get=self.fetch(self.red))
        self.assertEqual(result["failed_count"], 0)
        self.assertEqual(result["items"][0].planned_filename, plan["items"][0]["planned_filename"])
        self.assertEqual(Path(result["image_overlay"][0]["original_path"]).read_bytes(), self.red)
        self.assertNotEqual(Path(result["items"][0].local_path).read_bytes(), self.red)


if __name__ == "__main__":
    unittest.main()
