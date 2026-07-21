from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from xml.etree import ElementTree as ET

from scripts.listing.models import sanitize_for_output
from scripts.listing.rakuten_transport import build_rakuten_auth_headers, create_requests_session, summarize_response


@dataclass
class RakutenImageUploadRequest:
    local_path: str
    filename: str
    store_code: str = ""
    timeout_seconds: float = 30.0
    headers: dict[str, str] | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class RakutenImageUploadResult:
    upload_status: str
    rakuten_image_url: str | None
    request_summary: dict[str, Any]
    response_status: int | None
    error_type: str | None = None
    error_message: str | None = None


def build_image_request_summary(request: RakutenImageUploadRequest) -> dict[str, Any]:
    return sanitize_for_output(
        {
            "local_path": request.local_path,
            "filename": request.filename,
            "store_code": request.store_code,
            "timeout_seconds": request.timeout_seconds,
            "headers": request.headers or {},
            "metadata": request.metadata or {},
        }
    )


class RakutenImageClient:
    def __init__(
        self,
        *,
        uploader: Callable[[RakutenImageUploadRequest], RakutenImageUploadResult] | None = None,
    ) -> None:
        self._uploader = uploader

    def upload_image(self, request: RakutenImageUploadRequest) -> RakutenImageUploadResult:
        if self._uploader is None:
            return upload_image_via_requests(request)
        return self._uploader(request)


def build_upload_request_from_validation(item: Any, *, store_code: str = "", headers: dict[str, str] | None = None) -> RakutenImageUploadRequest:
    return RakutenImageUploadRequest(
        local_path=str(getattr(item, "local_path", "")),
        filename=Path(str(getattr(item, "local_path", ""))).name,
        store_code=store_code,
        headers=dict(headers or {}),
        metadata={
            "order": getattr(item, "order", None),
            "role": getattr(item, "role", None),
            "sha256": getattr(item, "sha256", None),
        },
    )


def _parse_cabinet_insert_response(response_text: str) -> dict[str, Any]:
    parsed: dict[str, Any] = {
        "interface_id": None,
        "system_status": None,
        "message": None,
        "request_id": None,
        "result_code": None,
        "file_id": None,
        "xml_parse_error": None,
    }
    try:
        root = ET.fromstring(response_text or "")
    except Exception as exc:
        parsed["xml_parse_error"] = str(exc)
        return parsed

    parsed["interface_id"] = root.findtext(".//status/interfaceId")
    parsed["system_status"] = root.findtext(".//status/systemStatus")
    parsed["message"] = root.findtext(".//status/message")
    parsed["request_id"] = root.findtext(".//status/requestId")
    parsed["result_code"] = root.findtext(".//cabinetFileInsertResult/resultCode")
    parsed["file_id"] = root.findtext(".//cabinetFileInsertResult/FileId")
    return parsed


def build_cabinet_file_insert_xml(
    *,
    file_name: str,
    folder_id: str | int,
    file_path: str,
    overwrite: bool = True,
) -> str:
    display_name = str(file_name or "").strip()
    overwrite_text = "true" if overwrite else "false"
    return (
        "<request>"
        "<fileInsertRequest>"
        "<file>"
        f"<fileName>{display_name}</fileName>"
        f"<folderId>{folder_id}</folderId>"
        f"<filePath>{file_path}</filePath>"
        f"<overWrite>{overwrite_text}</overWrite>"
        "</file>"
        "</fileInsertRequest>"
        "</request>"
    )


def upload_image_via_requests(request: RakutenImageUploadRequest) -> RakutenImageUploadResult:
    local_path = Path(request.local_path)
    if not local_path.exists():
        return RakutenImageUploadResult(
            upload_status="failed",
            rakuten_image_url=None,
            request_summary=build_image_request_summary(request),
            response_status=None,
            error_type="missing_local_file",
            error_message=f"local image file not found: {local_path}",
        )

    session = create_requests_session()
    metadata = dict(request.metadata or {})
    endpoint = str(metadata.get("upload_endpoint") or "https://api.rms.rakuten.co.jp/es/1.0/cabinet/file/insert")
    shop_url = str(metadata.get("shop_url") or "").strip()
    cabinet_folder_id = str(metadata.get("cabinet_folder_id") or "").strip()
    cabinet_folder_path = str(metadata.get("cabinet_folder_path") or "").replace("\\", "/").strip().strip("/")
    item_location = str(metadata.get("item_location") or "").strip()
    destination_file_name = str(metadata.get("file_name") or request.filename or local_path.name).strip()
    file_path = str(metadata.get("file_path") or destination_file_name).strip()
    xml_body = build_cabinet_file_insert_xml(
        file_name=destination_file_name,
        folder_id=cabinet_folder_id,
        file_path=file_path,
        overwrite=True,
    )
    headers = build_rakuten_auth_headers(store_code=request.store_code, accept="text/xml", content_type=None, extra_headers=request.headers or {})
    data: dict[str, str] = {"xml": xml_body}

    with local_path.open("rb") as fh:
        response = session.post(
            endpoint,
            headers=headers,
            data=data,
            files={"file": (destination_file_name, fh, "image/jpeg")},
            timeout=request.timeout_seconds,
        )

    response_text = str(getattr(response, "text", "") or "")
    response_xml_summary = _parse_cabinet_insert_response(response_text)
    success = (
        200 <= int(response.status_code) < 300
        and not response_xml_summary.get("xml_parse_error")
        and str(response_xml_summary.get("system_status") or "").upper() == "OK"
        and str(response_xml_summary.get("result_code") or "") == "0"
    )
    return RakutenImageUploadResult(
        upload_status="uploaded" if success else "failed",
        rakuten_image_url=(item_location or None) if success else None,
        request_summary=sanitize_for_output(
            {
                **build_image_request_summary(request),
                "endpoint": endpoint,
                "shop_url": shop_url,
                "cabinet_folder_id": cabinet_folder_id,
                "cabinet_folder_path": cabinet_folder_path,
                "item_location": item_location,
                "file_name": destination_file_name,
                "file_path": file_path,
                "xml_preview": xml_body,
                "multipart_field_names": ["xml", "file"],
                "response_xml_summary": response_xml_summary,
            }
        ),
        response_status=int(response.status_code),
        error_type=None if success else "http_error",
        error_message=None if success else str(response_xml_summary if response_text else summarize_response(response)),
    )
