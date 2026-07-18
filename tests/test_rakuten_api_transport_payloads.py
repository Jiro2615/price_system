from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock
import tempfile

from scripts.listing.rakuten_image_client import RakutenImageUploadRequest, upload_image_via_requests
from scripts.listing.rakuten_inventory_client import build_inventory_request
from scripts.listing.rakuten_item_client import build_item_request


class RakutenApiTransportPayloadTests(unittest.TestCase):
    def test_build_item_request_sanitizes_payload_for_api(self) -> None:
        payload = {
            "itemNumber": "20260711105704_187_46e3",
            "title": "test title",
            "itemType": "NORMAL",
            "genreId": 213661,
            "payment": {"taxRate": 0.1},
            "variants": {
                "20260711105704_187_46e3": {
                    "standardPrice": 1948,
                    "articleNumber": {"exemptionReason": 5},
                    "attributes": [
                        {"name": "ブランド名", "value": "ビバリー(BEVERLY)"},
                        {"name": "代表カラー", "values": ["ブルー"]},
                    ],
                }
            },
        }

        request = build_item_request("20260711105704_187_46e3", payload, {})
        variant = request.payload["variants"]["20260711105704_187_46e3"]

        self.assertEqual(request.payload["genreId"], "213661")
        self.assertEqual(request.payload["payment"]["taxRate"], "0.1")
        self.assertEqual(variant["standardPrice"], "1948")
        self.assertEqual(variant["articleNumber"], {"exemptionReason": 5})
        self.assertEqual(
            variant["attributes"],
            [
                {"name": "ブランド名", "values": ["ビバリー(BEVERLY)"]},
                {"name": "代表カラー", "values": ["ブルー"]},
            ],
        )

    def test_build_inventory_request_uses_variant_path_and_omits_internal_fields(self) -> None:
        payload = {
            "mode": "ABSOLUTE",
            "quantity": 4,
            "shipFromIds": ["1"],
            "operationLeadTime": {
                "normalDeliveryTimeId": 1,
                "backOrderDeliveryTimeId": 2,
            },
            "variantPath": {
                "managementNumber": "MANAGE-1",
                "variantKey": "SKU-1",
            },
        }

        request = build_inventory_request("FALLBACK", payload, {})

        self.assertEqual(request.management_number, "MANAGE-1")
        self.assertEqual(request.variant_id, "SKU-1")
        self.assertTrue(request.url.endswith("/manage-numbers/MANAGE-1/variants/SKU-1"))
        self.assertNotIn("variantPath", request.payload)
        self.assertEqual(request.payload["shipFromIds"], [1])

    def test_upload_image_via_requests_uses_xml_and_file_only(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as tmpdir:
            image_path = Path(tmpdir) / "local.jpg"
            image_path.write_bytes(b"fake-image")

            captured: dict[str, object] = {}

            class FakeResponse:
                status_code = 200
                headers = {"Content-Type": "text/xml"}
                text = """<?xml version="1.0" encoding="UTF-8"?>
<result>
  <status>
    <interfaceId>cabinet.file.insert</interfaceId>
    <systemStatus>OK</systemStatus>
    <message>OK</message>
    <requestId>req-1</requestId>
  </status>
  <cabinetFileInsertResult>
    <resultCode>0</resultCode>
    <FileId>123</FileId>
  </cabinetFileInsertResult>
</result>"""

            class FakeSession:
                def post(self, endpoint, headers=None, data=None, files=None, timeout=None):
                    captured["endpoint"] = endpoint
                    captured["headers"] = dict(headers or {})
                    captured["data_keys"] = sorted((data or {}).keys())
                    captured["file_tuple_name"] = files["file"][0]
                    return FakeResponse()

            request = RakutenImageUploadRequest(
                local_path=str(image_path),
                filename="20260711105704_187_1.jpg",
                metadata={
                    "upload_endpoint": "https://api.rms.rakuten.co.jp/es/1.0/cabinet/file/insert",
                    "cabinet_folder_id": 13584708,
                    "cabinet_folder_path": "r_2025042547/listing_test",
                    "item_location": "/r_2025042547/listing_test/20260711105704_187_1.jpg",
                    "file_name": "20260711105704_187_1.jpg",
                    "file_path": "20260711105704_187_1.jpg",
                },
            )

            with mock.patch("scripts.listing.rakuten_image_client.create_requests_session", return_value=FakeSession()):
                with mock.patch(
                    "scripts.listing.rakuten_image_client.build_rakuten_auth_headers",
                    return_value={"Authorization": "ESA dummy", "Accept": "text/xml"},
                ):
                    result = upload_image_via_requests(request)

        self.assertEqual(result.upload_status, "uploaded")
        self.assertEqual(captured["data_keys"], ["xml"])
        self.assertEqual(captured["file_tuple_name"], "20260711105704_187_1.jpg")
        self.assertEqual(result.rakuten_image_url, "/r_2025042547/listing_test/20260711105704_187_1.jpg")


if __name__ == "__main__":
    unittest.main()
