"""Deterministic listing overlays. Originals are never overwritten."""
from __future__ import annotations

import hashlib
import base64
import io
import math
import os
import tempfile
from dataclasses import replace
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[2] / "assets" / "listing_overlay"
VERSION = "store-logo-v4-opt-in"


def free_shipping(payload: dict) -> bool:
    variants = payload.get("variants")
    return isinstance(variants, dict) and bool(variants) and all(
        isinstance(v, dict) and isinstance(v.get("shipping"), dict)
        and v["shipping"].get("postageIncluded") is True
        for v in variants.values()
    )


def render_overlay(source: Path, output_root: Path, *, postage_included: bool,
                   logo_bytes: bytes | None = None, logo_width_percent: float = 27) -> Path:
    from PIL import Image, ImageOps

    source = Path(source).resolve()
    if "_listing_overlay" in source.parts:
        raise ValueError("Use the original image, not an already processed image")
    logo_path = ASSETS / "lifeforest_circle.png"
    badge_path = ASSETS / "free_shipping.png"
    original = source.read_bytes()
    if not math.isfinite(logo_width_percent) or not 5 <= logo_width_percent <= 50:
        raise ValueError("Logo width must be between 5 and 50 percent")
    logo_bytes = logo_path.read_bytes() if logo_bytes is None else logo_bytes
    digest = hashlib.sha256(original + logo_bytes
                            + (badge_path.read_bytes() if postage_included else b"")
                            + VERSION.encode() + str(logo_width_percent).encode()).hexdigest()
    target = Path(output_root) / "_listing_overlay" / digest / source.with_suffix(".jpg").name
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as opened:
        oriented = ImageOps.exif_transpose(opened).convert("RGBA")
        canvas = Image.new("RGB", oriented.size, "white")
        canvas.paste(oriented, mask=oriented.getchannel("A"))
    width, height = canvas.size
    margin = max(1, round(min(width, height) * .005))
    for asset, ratio, height_ratio, bottom in [(io.BytesIO(logo_bytes), logo_width_percent / 100, .99, False)] + (
        [(badge_path, .40, .12, True)] if postage_included else []
    ):
        with Image.open(asset) as opened:
            stamp = opened.convert("RGBA")
        # Resize both up and down: large originals must retain the same proportions.
        stamp = ImageOps.contain(stamp, (max(1, round(width * ratio)),
                                       max(1, round(height * height_ratio))), Image.Resampling.LANCZOS)
        xy = (max(0, width-margin-stamp.width), max(0, height-margin-stamp.height)) if bottom else (margin, margin)
        if bottom:
            # Preserve product pixels outside the badge's rounded silhouette.
            canvas.paste(stamp, xy, mask=stamp.getchannel("A"))
        else:
            # The user explicitly wants the logo's white background retained.
            backing = Image.new("RGB", stamp.size, "white")
            backing.paste(stamp, mask=stamp.getchannel("A"))
            canvas.paste(backing, xy)
    fd, temporary = tempfile.mkstemp(suffix=".jpg", dir=target.parent)
    os.close(fd)
    try:
        canvas.save(temporary, "JPEG", quality=95, subsampling=0)
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return target


def overlay_downloader(downloader, *, store_code: str, shop_url: str, item_payload: dict, settings: dict | None = None):
    """Wrap real downloads, leaving mocks, other stores and sub-images alone."""
    def download(*args, **kwargs):
        result = downloader(*args, **kwargs)
        config = settings or {}
        if config.get("enabled") is not True or os.environ.get("LISTING_IMAGE_OVERLAY", "1") == "0":
            return result
        processed = []
        report = []
        for item in result.get("items", []):
            if item.role != "main" or item.download_status not in {"downloaded", "reused"}:
                processed.append(item)
                continue
            try:
                encoded = config.get("logo_base64")
                if not isinstance(encoded, str) or not encoded or len(encoded) > 2800000:
                    raise ValueError("Upload a store logo before enabling image overlays")
                logo_bytes = base64.b64decode(encoded, validate=True)
                show_shipping = config.get("free_shipping") is True and free_shipping(item_payload)
                output = render_overlay(Path(item.local_path), kwargs["output_root"],
                                        postage_included=show_shipping, logo_bytes=logo_bytes,
                                        logo_width_percent=float(config.get("logo_width_percent", 27)))
                report.append({"original_path": item.local_path, "processed_path": str(output),
                               "profile": VERSION, "store_code": store_code, "free_shipping": show_shipping})
                processed.append(replace(item, local_path=str(output), file_size=output.stat().st_size,
                                         content_type="image/jpeg", sha256=None))
            except Exception as exc:
                processed.append(replace(item, download_status="failed", error_type="image_overlay_failed",
                                         error_message=str(exc)))
                result["failed_count"] = result.get("failed_count", 0) + 1
        return {**result, "items": processed, "image_overlay": report}
    return download
