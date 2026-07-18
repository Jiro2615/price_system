from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any


def _normalize_image_base_name(value: str) -> str:
    return str(value or "").strip()


def _extract_source_image_id(source_url: str) -> str:
    return str(source_url or "").rstrip("/").rsplit("/", 1)[-1]


def _build_filename(base_name: str, index: int) -> str:
    return f"{base_name}_{index + 1}.jpg"


def build_image_download_plan(
    *,
    asin: str,
    image_base_name: str | None = None,
    image_urls: list[str] | None,
    image_source: str,
    listing_status: str,
    max_images: int | None = None,
) -> dict[str, Any]:
    normalized_base_name = _normalize_image_base_name(image_base_name or asin).lower()
    normalized_urls = [str(url).strip() for url in (image_urls or []) if str(url).strip()]
    if max_images is not None and int(max_images) > 0:
        normalized_urls = normalized_urls[: int(max_images)]
    execution_allowed = listing_status == "eligible"
    blocked_reason = None if execution_allowed else f"listing_status is {listing_status}"

    items: list[dict[str, Any]] = []
    for index, source_url in enumerate(normalized_urls):
        filename = _build_filename(normalized_base_name, index)
        items.append(
            {
                "role": "main" if index == 0 else "sub",
                "order": index + 1,
                "source_url": source_url,
                "source": image_source or "none",
                "source_image_id": _extract_source_image_id(source_url),
                "planned_filename": filename,
                "planned_relative_path": str(PurePosixPath("images") / normalized_base_name / filename),
                "download_required": execution_allowed,
                "validation_status": "not_checked",
                "upload_status": "not_uploaded",
                "rakuten_image_url": None,
            }
        )

    return {
        "execution_allowed": execution_allowed,
        "blocked_reason": blocked_reason,
        "items": items,
    }
