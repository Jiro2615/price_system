from __future__ import annotations

import unittest
from datetime import datetime, timezone, timedelta

from scripts.listing.cabinet_rotation import resolve_cabinet_upload_folder


JST = timezone(timedelta(hours=9))


class FakeResponse:
    def __init__(self, text: str, status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code


def folder_list_xml(folders: list[tuple[int, str, int]]) -> str:
    entries = "".join(
        "<folder>"
        f"<FolderId>{folder_id}</FolderId><FolderName>{path.rsplit('/', 1)[-1]}</FolderName>"
        f"<FolderPath>{path}</FolderPath><FolderNode>2</FolderNode><FileCount>{count}</FileCount>"
        "</folder>"
        for folder_id, path, count in folders
    )
    return (
        "<result><status><systemStatus>OK</systemStatus></status>"
        f"<cabinetFoldersGetResult><resultCode>0</resultCode><folderAllCount>{len(folders)}</folderAllCount>"
        f"<folders>{entries}</folders></cabinetFoldersGetResult></result>"
    )


class CabinetRotationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = {
            "folder_id": 10,
            "folder_name": "listing_test",
            "folder_path": "r_2025042547/listing_test",
            "folder_node": 2,
            "shop_url": "lifeforest",
        }
        self.now = datetime(2026, 8, 17, 12, 0, tzinfo=JST)

    def test_uses_root_until_2000_file_limit_is_reached(self) -> None:
        result = resolve_cabinet_upload_folder(
            self.root,
            store_code="rakuten_2",
            planned_image_count=1,
            now=self.now,
            headers={"Authorization": "test"},
            http_get=lambda *_, **__: FakeResponse(folder_list_xml([(10, self.root["folder_path"], 1999)])),
            http_post=lambda *_, **__: self.fail("child folder must not be created"),
        )
        self.assertEqual(result["folder_id"], 10)
        self.assertTrue(result["rotation"]["used_root"])

    def test_creates_date_sequence_child_when_root_would_exceed_limit(self) -> None:
        posted: list[dict] = []

        def post(*_, **kwargs):
            posted.append(kwargs)
            return FakeResponse(
                "<result><status><systemStatus>OK</systemStatus></status>"
                "<cabinetFolderInsertResult><resultCode>0</resultCode><FolderId>99</FolderId>"
                "</cabinetFolderInsertResult></result>"
            )

        result = resolve_cabinet_upload_folder(
            self.root,
            store_code="rakuten_2",
            planned_image_count=1,
            now=self.now,
            headers={"Authorization": "test"},
            http_get=lambda *_, **__: FakeResponse(folder_list_xml([(10, self.root["folder_path"], 2000)])),
            http_post=post,
        )
        self.assertEqual(result["folder_id"], 99)
        self.assertEqual(result["folder_path"], "r_2025042547/listing_test/2026081701")
        self.assertTrue(result["rotation"]["created"])
        self.assertIn("<upperFolderId>10</upperFolderId>", posted[0]["data"])

    def test_reuses_same_day_child_before_it_reaches_limit(self) -> None:
        result = resolve_cabinet_upload_folder(
            self.root,
            store_code="rakuten_2",
            planned_image_count=1,
            now=self.now,
            headers={"Authorization": "test"},
            http_get=lambda *_, **__: FakeResponse(folder_list_xml([
                (10, self.root["folder_path"], 2000),
                (12, "r_2025042547/listing_test/2026081701", 1999),
            ])),
            http_post=lambda *_, **__: self.fail("existing child folder must be reused"),
        )
        self.assertEqual(result["folder_id"], 12)
        self.assertFalse(result["rotation"]["created"])
        self.assertEqual(result["folder_path"], "r_2025042547/listing_test/2026081701")

    def test_reuses_newest_prior_day_child_before_creating_another(self) -> None:
        result = resolve_cabinet_upload_folder(
            self.root,
            store_code="rakuten_2",
            planned_image_count=3,
            now=datetime(2026, 8, 18, 12, 0, tzinfo=JST),
            headers={"Authorization": "test"},
            http_get=lambda *_, **__: FakeResponse(folder_list_xml([
                (10, self.root["folder_path"], 2000),
                (11, "r_2025042547/listing_test/2026081601", 1999),
                (12, "r_2025042547/listing_test/2026081701", 1996),
            ])),
            http_post=lambda *_, **__: self.fail("existing child folder must be reused"),
        )
        self.assertEqual(result["folder_id"], 12)
        self.assertEqual(result["folder_path"], "r_2025042547/listing_test/2026081701")
        self.assertFalse(result["rotation"]["created"])


if __name__ == "__main__":
    unittest.main()
