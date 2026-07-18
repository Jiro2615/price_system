from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from scripts.listing.image_downloader import DownloadedImageResult


@dataclass
class ValidatedImageResult:
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
    width: int | None
    height: int | None
    sha256: str | None
    validation_status: str
    validation_errors: list[str]
    upload_status: str
    rakuten_image_url: str | None
    error_type: str | None
    error_message: str | None


def _default_dimension_reader(path: Path) -> tuple[int | None, int | None]:
    try:
        from PIL import Image  # type: ignore
    except Exception:
        return (None, None)

    with Image.open(path) as image:
        return (int(image.width), int(image.height))


def validate_downloaded_images(
    items: list[DownloadedImageResult] | list[dict[str, Any]],
    *,
    dimension_reader: Callable[[Path], tuple[int | None, int | None]] | None = None,
    integrity_checker: Callable[[Path], bool] | None = None,
) -> dict[str, Any]:
    reader = dimension_reader or _default_dimension_reader
    checker = integrity_checker or (lambda path: True)

    results: list[ValidatedImageResult] = []
    for item in items:
        source = item if isinstance(item, DownloadedImageResult) else DownloadedImageResult(**item)
        path = Path(source.local_path)
        errors: list[str] = list(source.validation_errors or [])
        width: int | None = None
        height: int | None = None
        sha256: str | None = None
        file_size = source.file_size
        local_exists = path.exists()
        status = "not_checked"
        error_type = source.error_type
        error_message = source.error_message

        if source.download_status not in {"downloaded", "reused"}:
            status = "failed" if source.download_status == "failed" else "not_checked"
        elif not local_exists:
            status = "invalid"
            errors.append("file_not_found")
        else:
            try:
                if file_size is None:
                    file_size = path.stat().st_size
                sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
                if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
                    errors.append("unsupported_extension")
                width, height = reader(path)
                if not checker(path):
                    errors.append("corruption_detected")
            except Exception as exc:
                status = "failed"
                error_type = "validation_error"
                error_message = str(exc) or exc.__class__.__name__

            if status != "failed":
                status = "valid" if not errors else "invalid"

        results.append(
            ValidatedImageResult(
                role=source.role,
                order=source.order,
                source_url=source.source_url,
                planned_filename=source.planned_filename,
                relative_path=source.relative_path,
                local_path=source.local_path,
                local_exists=local_exists,
                download_status=source.download_status,
                http_status=source.http_status,
                content_type=source.content_type,
                file_size=file_size,
                width=width,
                height=height,
                sha256=sha256,
                validation_status=status,
                validation_errors=errors,
                upload_status=source.upload_status,
                rakuten_image_url=source.rakuten_image_url,
                error_type=error_type,
                error_message=error_message,
            )
        )

    return {
        "items": results,
        "valid_count": sum(1 for item in results if item.validation_status == "valid"),
        "invalid_count": sum(1 for item in results if item.validation_status == "invalid"),
        "failed_count": sum(1 for item in results if item.validation_status == "failed"),
    }
