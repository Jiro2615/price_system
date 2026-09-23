import tempfile
import base64
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from scripts.listing.image_downloader import DownloadedImageResult
from scripts.listing.image_overlay import ASSETS, free_shipping, overlay_downloader, render_overlay


class OverlayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "original.jpg"
        Image.new("RGB", (1000, 1000), "white").save(self.source)
        self.item = DownloadedImageResult("main", 1, "https://example.invalid/image", "original.jpg",
                                          "original.jpg", str(self.source), True, "downloaded", 200,
                                          "image/jpeg", self.source.stat().st_size)
        self.payload = {"variants": {"sku": {"shipping": {"postageIncluded": True}}}}
        self.settings = {"enabled": True, "free_shipping": True, "logo_width_percent": 27,
                         "logo_base64": base64.b64encode((ASSETS / "lifeforest_circle.png").read_bytes()).decode()}

    def run_download(self, store="rakuten_2", shop="lifeforest", payload=None):
        wrapped = overlay_downloader(lambda *a, **k: {"items": [self.item], "failed_count": 0},
                                     store_code=store, shop_url=shop, item_payload=payload or self.payload,
                                     settings=self.settings)
        with patch.dict("os.environ", {"LISTING_IMAGE_OVERLAY": "1"}):
            return wrapped({}, output_root=self.root)

    def test_original_preserved_and_deterministic(self):
        before = self.source.read_bytes()
        output = render_overlay(self.source, self.root, postage_included=True)
        first = output.read_bytes()
        self.assertEqual(output, render_overlay(self.source, self.root, postage_included=True))
        self.assertEqual(first, output.read_bytes())
        self.assertEqual(before, self.source.read_bytes())
        with Image.open(output) as image:
            self.assertEqual(image.size, (1000, 1000))
        with self.assertRaises(ValueError):
            render_overlay(output, self.root, postage_included=True)

    def test_requires_all_variants_explicitly_free(self):
        self.assertTrue(free_shipping(self.payload))
        for payload in ({}, {"variants": {}}, {"variants": {"x": {}}},
                        {"variants": {"x": {"shipping": {"postageIncluded": "true"}}}}):
            self.assertFalse(free_shipping(payload))
        self.payload["variants"]["paid"] = {"shipping": {"postageIncluded": False}}
        self.assertFalse(free_shipping(self.payload))

    def test_wrapper_changes_upload_source(self):
        result = self.run_download()
        self.assertNotEqual(result["items"][0].local_path, self.item.local_path)
        self.assertEqual(result["items"][0].planned_filename, self.item.planned_filename)
        self.assertEqual(result["failed_count"], 0)
        self.assertTrue(result["image_overlay"][0]["free_shipping"])

    def test_any_store_can_opt_in_but_sub_image_untouched(self):
        self.assertNotEqual(self.run_download(store="rakuten_1")["items"][0].local_path, self.item.local_path)
        self.item.role = "sub"
        self.assertEqual(self.run_download()["items"][0], self.item)

    def test_enabled_without_uploaded_logo_fails_closed(self):
        self.settings["logo_base64"] = ""
        self.assertEqual(self.run_download()["items"][0].download_status, "failed")

    def test_default_disabled(self):
        wrapped = overlay_downloader(lambda *a, **k: {"items": [self.item]},
                                     store_code="rakuten_2", shop_url="lifeforest", item_payload=self.payload)
        self.assertEqual(wrapped({}, output_root=self.root)["items"][0], self.item)

    def test_missing_assets_fails_closed(self):
        with patch("scripts.listing.image_overlay.ASSETS", self.root / "missing"):
            self.assertEqual(self.run_download()["failed_count"], 1)

    def test_badge_omitted_when_paid(self):
        with_badge = render_overlay(self.source, self.root, postage_included=True)
        without = render_overlay(self.source, self.root, postage_included=False)
        self.assertNotEqual(with_badge, without)
        with Image.open(without) as image:
            self.assertEqual(image.getpixel((900, 950)), (255, 255, 255))

    def test_disable_switch(self):
        wrapped = overlay_downloader(lambda *a, **k: {"items": [self.item]},
                                     store_code="rakuten_2", shop_url="lifeforest", item_payload=self.payload,
                                     settings=self.settings)
        with patch.dict("os.environ", {"LISTING_IMAGE_OVERLAY": "0"}):
            self.assertEqual(wrapped({}, output_root=self.root)["items"][0], self.item)

    def test_badge_rounded_corners_are_transparent_over_product(self):
        with Image.open(ASSETS / "free_shipping.png") as badge:
            self.assertEqual(badge.mode, "RGBA")
            for xy in ((0, 0), (badge.width-1, 0), (0, badge.height-1),
                       (badge.width-1, badge.height-1)):
                self.assertEqual(badge.getpixel(xy)[3], 0)
            self.assertEqual(badge.getpixel((badge.width//2, 10))[3], 255)
        # Non-white product makes a mistakenly white-flattened corner detectable.
        Image.new("RGB", (1000, 1000), (180, 70, 90)).save(self.source)
        output = render_overlay(self.source, self.root, postage_included=True)
        with Image.open(output) as image:
            # 400 x 115 badge, margin 5: top-left at (595, 880).
            for xy in ((595, 880), (994, 880), (595, 994), (994, 994)):
                pixel = image.getpixel(xy)
                self.assertTrue(all(abs(a-b) < 20 for a, b in zip(pixel, (180, 70, 90))), pixel)

    def test_reference_layout_at_small_and_large_sizes(self):
        for size in (411, 2560):
            Image.new("RGB", (size, size), "white").save(self.source)
            output = render_overlay(self.source, self.root, postage_included=True)
            with Image.open(output) as image:
                # Badge starts at about 60% width, even above the stamp's native resolution.
                r, g, b = image.getpixel((round(size * .62), round(size * .94)))
                self.assertLess(b, 140)
                self.assertGreater(g, b)
                self.assertEqual(image.getpixel((round(size * .55), round(size * .94))), (255, 255, 255))
                # Circular logo occupies a square, no longer squashed to a 12% height cap.
                lower_logo = image.crop((round(size * .03), round(size * .16),
                                         round(size * .25), round(size * .25)))
                self.assertLess(lower_logo.getextrema()[2][0], 180)


if __name__ == "__main__":
    unittest.main()
