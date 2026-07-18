from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable

from scripts.listing.rakuten_transport import create_requests_session


@dataclass
class HttpFetchResponse:
    status_code: int
    headers: dict[str, str]
    content: bytes
    final_url: str = ""


@dataclass
class DownloadedImageResult:
    role: str
    order: int
    source_url: str
    planned_filename: str
    relative_path: str
    local_path: str
    local_exists: bool
    download_status: str
    http_status: int | None
    content_type: str | None
    file_size: int | None
    width: int | None = None
    height: int | None = None
    sha256: str | None = None
    validation_status: str = "not_checked"
    validation_errors: list[str] | None = None
    upload_status: str = "not_uploaded"
    rakuten_image_url: str | None = None
    error_type: str | None = None
    error_message: str | None = None


def requests_http_get(url: str, timeout_seconds: float, allow_redirects: bool) -> HttpFetchResponse:
    session = create_requests_session()
    response = session.get(url, timeout=timeout_seconds, allow_redirects=allow_redirects)
    return HttpFetchResponse(
        status_code=int(response.status_code),
        headers=dict(response.headers),
        content=bytes(response.content),
        final_url=str(response.url),
    )


def _relative_output_path(planned_relative_path: str) -> Path:
    posix_path = PurePosixPath(str(planned_relative_path or "").strip())
    return Path(*posix_path.parts)


def download_image_plan(
    plan: dict[str, Any] | None,
    *,
    output_root: Path,
    http_get: Callable[[str, float, bool], HttpFetchResponse] | None,
    timeout_seconds: float = 20.0,
    allow_redirects: bool = True,
) -> dict[str, Any]:
    execution_allowed = bool((plan or {}).get("execution_allowed"))
    blocked_reason = (plan or {}).get("blocked_reason")
    items = list((plan or {}).get("items") or [])

    results: list[DownloadedImageResult] = []
    for item in items:
        source_url = str(item.get("source_url") or "").strip()
        relative_path = str(item.get("planned_relative_path") or "").strip()
        local_path = output_root / _relative_output_path(relative_path)
        base = DownloadedImageResult(
            role=str(item.get("role") or ""),
            order=int(item.get("order") or 0),
            source_url=source_url,
            planned_filename=str(item.get("planned_filename") or ""),
            relative_path=relative_path,
            local_path=str(local_path),
            local_exists=local_path.exists(),
            download_status="not_started",
            http_status=None,
            content_type=None,
            file_size=None,
            validation_errors=[],
            upload_status=str(item.get("upload_status") or "not_uploaded"),
            rakuten_image_url=item.get("rakuten_image_url"),
        )

        if not execution_allowed or not item.get("download_required", False):
            base.download_status = "skipped"
            results.append(base)
            continue

        if local_path.exists() and local_path.is_file():
            base.download_status = "reused"
            base.local_exists = True
            try:
                base.file_size = local_path.stat().st_size
            except OSError as exc:
                base.download_status = "failed"
                base.error_type = "filesystem_error"
                base.error_message = str(exc)
            results.append(base)
            continue

        if http_get is None:
            base.download_status = "failed"
            base.error_type = "http_client_not_configured"
            base.error_message = "HTTP client is required for image download"
            results.append(base)
            continue

        try:
            response = http_get(source_url, timeout_seconds, allow_redirects)
        except Exception as exc:
            base.download_status = "failed"
            base.error_type = "http_error"
            base.error_message = str(exc) or exc.__class__.__name__
            results.append(base)
            continue

        base.http_status = int(response.status_code)
        content_type = response.headers.get("Content-Type") or response.headers.get("content-type")
        base.content_type = str(content_type) if content_type else None
        if response.status_code < 200 or response.status_code >= 300:
            base.download_status = "failed"
            base.error_type = "http_status_error"
            base.error_message = f"unexpected status: {response.status_code}"
            results.append(base)
            continue

        try:
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_bytes(response.content)
            base.local_exists = True
            base.file_size = len(response.content)
            base.download_status = "downloaded"
        except OSError as exc:
            base.download_status = "failed"
            base.error_type = "filesystem_error"
            base.error_message = str(exc)

        results.append(base)

    return {
        "execution_allowed": execution_allowed,
        "blocked_reason": blocked_reason,
        "output_root": str(output_root),
        "items": results,
        "downloaded_count": sum(1 for item in results if item.download_status in {"downloaded", "reused"}),
        "failed_count": sum(1 for item in results if item.download_status == "failed"),
    }
