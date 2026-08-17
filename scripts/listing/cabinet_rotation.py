from __future__ import annotations

import re
from datetime import datetime, timezone, timedelta
from typing import Any, Callable
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape as xml_escape

import requests

from scripts.listing.rakuten_transport import build_rakuten_auth_headers


CABINET_FOLDERS_GET_ENDPOINT = "https://api.rms.rakuten.co.jp/es/1.0/cabinet/folders/get"
CABINET_FOLDER_INSERT_ENDPOINT = "https://api.rms.rakuten.co.jp/es/1.0/cabinet/folder/insert"
CABINET_FOLDER_FILE_LIMIT = 2000
JST = timezone(timedelta(hours=9))


class CabinetRotationError(RuntimeError):
    pass


def _normalized_path(value: object) -> str:
    return str(value or "").replace("\\", "/").strip().strip("/")


def _int(value: object, default: int = 0) -> int:
    try:
        return int(str(value or "").strip())
    except (TypeError, ValueError):
        return default


def _xml_text(root: ET.Element, xpath: str) -> str:
    return str(root.findtext(xpath) or "").strip()


def _parse_folders(response_text: str) -> tuple[list[dict[str, Any]], int]:
    try:
        root = ET.fromstring(response_text or "")
    except ET.ParseError as exc:
        raise CabinetRotationError(f"R-Cabinet folder list XML parse failed: {exc}") from exc
    system_status = _xml_text(root, ".//status/systemStatus").upper()
    result_code = _xml_text(root, ".//cabinetFoldersGetResult/resultCode")
    if system_status != "OK" or result_code != "0":
        message = _xml_text(root, ".//status/message")
        raise CabinetRotationError(f"R-Cabinet folder list failed: {message or system_status or result_code}")
    folders = []
    for folder in root.findall(".//cabinetFoldersGetResult/folders/folder"):
        folders.append(
            {
                "folder_id": _int(_xml_text(folder, "FolderId")),
                "folder_name": _xml_text(folder, "FolderName"),
                "folder_path": _normalized_path(_xml_text(folder, "FolderPath")),
                "folder_node": _int(_xml_text(folder, "FolderNode")),
                "file_count": _int(_xml_text(folder, "FileCount")),
            }
        )
    return folders, _int(_xml_text(root, ".//cabinetFoldersGetResult/folderAllCount"))


def list_cabinet_folders(
    *,
    store_code: str,
    headers: dict[str, str] | None = None,
    http_get: Callable[..., Any] | None = None,
) -> list[dict[str, Any]]:
    request_headers = headers or build_rakuten_auth_headers(store_code=store_code, accept="text/xml")
    get = http_get or requests.get
    folders: list[dict[str, Any]] = []
    offset = 1
    while True:
        response = get(
            CABINET_FOLDERS_GET_ENDPOINT,
            headers=request_headers,
            params={"offset": offset, "limit": 100},
            timeout=30,
        )
        if not 200 <= int(response.status_code) < 300:
            raise CabinetRotationError(f"R-Cabinet folder list HTTP {response.status_code}: {str(response.text or '')[:300]}")
        page, total = _parse_folders(str(response.text or ""))
        folders.extend(page)
        if not page or len(folders) >= total:
            return folders
        offset += 1
        if offset > 100:
            raise CabinetRotationError("R-Cabinet folder list exceeded 100 pages")


def _folder_insert_xml(*, folder_name: str, directory_name: str, upper_folder_id: int) -> str:
    return (
        "<request><folderInsertRequest><folder>"
        f"<folderName>{xml_escape(folder_name)}</folderName>"
        f"<directoryName>{xml_escape(directory_name)}</directoryName>"
        f"<upperFolderId>{upper_folder_id}</upperFolderId>"
        "</folder></folderInsertRequest></request>"
    )


def create_cabinet_child_folder(
    *,
    store_code: str,
    parent_folder_id: int,
    folder_name: str,
    headers: dict[str, str] | None = None,
    http_post: Callable[..., Any] | None = None,
) -> int:
    if not parent_folder_id:
        raise CabinetRotationError("R-Cabinet root folder ID is required")
    if not re.fullmatch(r"\d{10}", folder_name):
        raise CabinetRotationError("R-Cabinet rotation folder name must be YYYYMMDDNN")
    request_headers = headers or build_rakuten_auth_headers(
        store_code=store_code,
        accept="text/xml",
        content_type="application/xml; charset=utf-8",
    )
    post = http_post or requests.post
    response = post(
        CABINET_FOLDER_INSERT_ENDPOINT,
        headers=request_headers,
        data=_folder_insert_xml(folder_name=folder_name, directory_name=folder_name, upper_folder_id=parent_folder_id),
        timeout=30,
    )
    if not 200 <= int(response.status_code) < 300:
        raise CabinetRotationError(f"R-Cabinet folder create HTTP {response.status_code}: {str(response.text or '')[:300]}")
    try:
        root = ET.fromstring(str(response.text or ""))
    except ET.ParseError as exc:
        raise CabinetRotationError(f"R-Cabinet folder create XML parse failed: {exc}") from exc
    system_status = _xml_text(root, ".//status/systemStatus").upper()
    result_code = _xml_text(root, ".//cabinetFolderInsertResult/resultCode")
    folder_id = _int(_xml_text(root, ".//cabinetFolderInsertResult/FolderId"))
    if system_status != "OK" or result_code != "0" or not folder_id:
        message = _xml_text(root, ".//status/message")
        raise CabinetRotationError(f"R-Cabinet folder create failed: {message or system_status or result_code}")
    return folder_id


def resolve_cabinet_upload_folder(
    cabinet_config: dict[str, Any],
    *,
    store_code: str,
    planned_image_count: int,
    now: datetime | None = None,
    headers: dict[str, str] | None = None,
    http_get: Callable[..., Any] | None = None,
    http_post: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Select an upload folder without changing the saved root Cabinet setting."""
    root_folder_id = _int(cabinet_config.get("folder_id"))
    root_folder_path = _normalized_path(cabinet_config.get("folder_path"))
    if not root_folder_id or not root_folder_path:
        raise CabinetRotationError("R-Cabinet root folder ID and path are required")
    if planned_image_count < 1:
        return {**cabinet_config, "rotation": {"used_root": True, "reason": "no_images"}}
    if planned_image_count > CABINET_FOLDER_FILE_LIMIT:
        raise CabinetRotationError("planned image count exceeds the R-Cabinet 2,000-file folder limit")

    folders = list_cabinet_folders(store_code=store_code, headers=headers, http_get=http_get)
    root_folder = next((folder for folder in folders if int(folder["folder_id"]) == root_folder_id), None)
    if root_folder is None:
        raise CabinetRotationError(f"configured R-Cabinet root folder was not found: id={root_folder_id}")
    root_count = int(root_folder["file_count"])
    if root_count + planned_image_count <= CABINET_FOLDER_FILE_LIMIT:
        return {
            **cabinet_config,
            "rotation": {"used_root": True, "root_file_count": root_count, "planned_image_count": planned_image_count},
        }

    day_prefix = (now or datetime.now(JST)).astimezone(JST).strftime("%Y%m%d")
    child_pattern = re.compile(rf"^{re.escape(root_folder_path)}/{day_prefix}(\d{{2}})$")
    children: list[tuple[int, dict[str, Any]]] = []
    for folder in folders:
        match = child_pattern.fullmatch(str(folder.get("folder_path") or ""))
        if match:
            children.append((int(match.group(1)), folder))
    for _, child in sorted(children, reverse=True):
        if int(child["file_count"]) + planned_image_count <= CABINET_FOLDER_FILE_LIMIT:
            return {
                **cabinet_config,
                "folder_id": int(child["folder_id"]),
                "folder_name": str(child["folder_name"]),
                "folder_path": str(child["folder_path"]),
                "folder_node": int(child["folder_node"]) or cabinet_config.get("folder_node"),
                "rotation": {
                    "used_root": False,
                    "created": False,
                    "root_file_count": root_count,
                    "child_file_count": int(child["file_count"]),
                    "planned_image_count": planned_image_count,
                },
            }

    next_sequence = max((sequence for sequence, _ in children), default=0) + 1
    if next_sequence > 99:
        raise CabinetRotationError(f"R-Cabinet daily rotation exceeded 99 folders for {day_prefix}")
    folder_name = f"{day_prefix}{next_sequence:02d}"
    folder_id = create_cabinet_child_folder(
        store_code=store_code,
        parent_folder_id=root_folder_id,
        folder_name=folder_name,
        headers=headers,
        http_post=http_post,
    )
    return {
        **cabinet_config,
        "folder_id": folder_id,
        "folder_name": folder_name,
        "folder_path": f"{root_folder_path}/{folder_name}",
        "folder_node": cabinet_config.get("folder_node"),
        "rotation": {
            "used_root": False,
            "created": True,
            "root_file_count": root_count,
            "child_file_count": 0,
            "planned_image_count": planned_image_count,
        },
    }
