from __future__ import annotations

import base64
import hashlib
import json
from pathlib import PurePosixPath
from typing import Any


def _normalize_image_base_name(value: str) -> str:
    return str(value or "").strip()


def _extract_source_image_id(source_url: str) -> str:
    return str(source_url or "").rstrip("/").rsplit("/", 1)[-1]


IMAGE_FILENAME_POLICY = "product-source-v2"


def product_image_filename(*, asin: str, image_base_name: str, order: int, source_url: str) -> str:
    """Keep the full product identity within Cabinet's 20-byte filename limit."""
    identity = json.dumps(
        [IMAGE_FILENAME_POLICY, str(asin).strip().upper(), str(image_base_name).strip().lower(),
         int(order), str(source_url).strip()], ensure_ascii=False, separators=(",", ":"),
    )
    # 80 bits, encoded as 16 lowercase ASCII characters, plus the extension.
    token = base64.b32encode(hashlib.sha256(identity.encode("utf-8")).digest()[:10]).decode("ascii").lower()
    return f"{token}.jpg"


def normalize_image_download_plan(plan: dict[str, Any] | None, *, asin: str, image_base_name: str) -> dict[str, Any]:
    """Also migrate saved, not-yet-uploaded plans without touching their source URLs."""
    result = dict(plan or {})
    items = []
    for source in result.get("items") or []:
        item = dict(source)
        filename = product_image_filename(asin=asin, image_base_name=image_base_name,
                                          order=int(item.get("order") or 0), source_url=item.get("source_url") or "")
        item.update(planned_filename=filename,
                    planned_relative_path=str(PurePosixPath("images") / filename))
        # Locations in a saved plan may still point at a shared legacy filename.
        item.pop("item_location", None)
        item["rakuten_image_url"] = None
        items.append(item)
    result.update(items=items, filename_policy=IMAGE_FILENAME_POLICY)
    return result


def image_upload_resume_error(dry_run_result: dict[str, Any]) -> str | None:
    """Legacy uploaded images cannot be assumed to belong to this product."""
    plan = dry_run_result.get("image_download_plan") or {}
    expected = normalize_image_download_plan(
        plan, asin=dry_run_result.get("asin") or "",
        image_base_name=dry_run_result.get("management_number") or dry_run_result.get("asin") or "",
    )
    items = list(plan.get("items") or [])
    if (plan.get("filename_policy") != IMAGE_FILENAME_POLICY or not items
            or any(item.get("planned_filename") != safe["planned_filename"]
                   or (item.get("item_location") and PurePosixPath(item["item_location"]).name != safe["planned_filename"])
                   for item, safe in zip(items, expected["items"]))):
        return "旧方式のアップロード画像は商品一致を保証できません。画像を再取得・アップロードする通常実行から再開してください。"
    return None


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
        filename = product_image_filename(asin=asin, image_base_name=normalized_base_name,
                                          order=index + 1, source_url=source_url)
        items.append(
            {
                "role": "main" if index == 0 else "sub",
                "order": index + 1,
                "source_url": source_url,
                "source": image_source or "none",
                "source_image_id": _extract_source_image_id(source_url),
                "planned_filename": filename,
                "planned_relative_path": str(PurePosixPath("images") / filename),
                "download_required": execution_allowed,
                "validation_status": "not_checked",
                "upload_status": "not_uploaded",
                "rakuten_image_url": None,
            }
        )

    return {
        "filename_policy": IMAGE_FILENAME_POLICY,
        "execution_allowed": execution_allowed,
        "blocked_reason": blocked_reason,
        "items": items,
    }
