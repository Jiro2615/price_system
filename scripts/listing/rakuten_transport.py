from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from scripts.listing.models import sanitize_for_output


BASE_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = BASE_DIR / ".env"
USER_AGENT = "price-system-listing-real-execute/1.0"

SECRET_ENV_NAMES = (
    "RAKUTEN_SERVICE_SECRET",
    "RAKUTEN_ITEM_SERVICE_SECRET",
    "RAKUTEN_API_SERVICE_SECRET",
    "RAKUTEN_RMS_SERVICE_SECRET",
    "RAKUTEN_IMAGE_SERVICE_SECRET",
)
LICENSE_ENV_NAMES = (
    "RAKUTEN_LICENSE_KEY",
    "RAKUTEN_ITEM_LICENSE_KEY",
    "RAKUTEN_API_LICENSE_KEY",
    "RAKUTEN_RMS_LICENSE_KEY",
    "RAKUTEN_IMAGE_LICENSE_KEY",
)


def _load_env_once() -> None:
    load_dotenv(ENV_PATH)


def _first_env(names: tuple[str, ...]) -> str:
    _load_env_once()
    for name in names:
        value = os.getenv(name)
        if value and str(value).strip():
            return str(value).strip()
    return ""


def build_authorization_header(service_secret: str, license_key: str) -> str:
    token_src = f"{service_secret}:{license_key}".encode("utf-8")
    token = base64.b64encode(token_src).decode("ascii")
    return f"ESA {token}"


def build_rakuten_auth_headers(
    *,
    accept: str = "application/json",
    content_type: str | None = "application/json",
    extra_headers: dict[str, str] | None = None,
) -> dict[str, str]:
    service_secret = _first_env(SECRET_ENV_NAMES)
    license_key = _first_env(LICENSE_ENV_NAMES)
    if not service_secret:
        raise RuntimeError(f"RAKUTEN_SERVICE_SECRET が空です: {ENV_PATH}")
    if not license_key:
        raise RuntimeError(f"RAKUTEN_LICENSE_KEY が空です: {ENV_PATH}")

    headers = {
        "Authorization": build_authorization_header(service_secret, license_key),
        "Accept": accept,
        "User-Agent": USER_AGENT,
    }
    if content_type:
        headers["Content-Type"] = content_type
    headers.update(dict(extra_headers or {}))
    return headers


def create_requests_session() -> Any:
    import requests

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def summarize_response(response: Any) -> dict[str, Any]:
    try:
        body_summary = response.json()
    except Exception:
        body_summary = {"text": str(getattr(response, "text", "") or "")[:500]}
    return sanitize_for_output(
        {
            "status_code": getattr(response, "status_code", None),
            "headers": dict(getattr(response, "headers", {}) or {}),
            "body_summary": body_summary,
        }
    )
