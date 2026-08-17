from __future__ import annotations

import base64
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from scripts.listing.models import sanitize_for_output


BASE_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = BASE_DIR.parent / ".env"
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


def _normalize_store_env_prefix(store_code: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", str(store_code or "").strip()).strip("_").upper()


def _store_scoped_names(store_code: str, base_names: tuple[str, ...]) -> tuple[str, ...]:
    prefix = _normalize_store_env_prefix(store_code) or "RAKUTEN_1"
    scoped: list[str] = []
    for name in base_names:
        if name.startswith("RAKUTEN_"):
            scoped.append(f"{prefix}_{name.removeprefix('RAKUTEN_')}")
    return tuple(dict.fromkeys(scoped))


def _load_env_once() -> None:
    # The orchestrator loads its own listing .env first.  Its intentionally
    # blank store-2 placeholders must not mask the active credentials in the
    # shared workspace .env used by the real listing transport.
    load_dotenv(ENV_PATH, override=True)


def _first_env(names: tuple[str, ...]) -> str:
    _load_env_once()
    for name in names:
        value = os.getenv(name)
        if value and str(value).strip():
            return str(value).strip()
    return ""


def rakuten_auth_env_status(store_code: str = "") -> dict[str, Any]:
    service_names = _store_scoped_names(store_code, SECRET_ENV_NAMES)
    license_names = _store_scoped_names(store_code, LICENSE_ENV_NAMES)
    service_configured = bool(_first_env(service_names))
    license_configured = bool(_first_env(license_names))
    return {
        "store_code": store_code,
        "service_names": service_names,
        "license_names": license_names,
        "service_configured": service_configured,
        "license_configured": license_configured,
        "configured": service_configured and license_configured,
        "missing_keys": ([] if service_configured else list(service_names)) + ([] if license_configured else list(license_names)),
    }


def build_authorization_header(service_secret: str, license_key: str) -> str:
    token_src = f"{service_secret}:{license_key}".encode("utf-8")
    token = base64.b64encode(token_src).decode("ascii")
    return f"ESA {token}"


def build_rakuten_auth_headers(
    *,
    store_code: str = "",
    accept: str = "application/json",
    content_type: str | None = "application/json",
    extra_headers: dict[str, str] | None = None,
) -> dict[str, str]:
    service_names = _store_scoped_names(store_code, SECRET_ENV_NAMES)
    license_names = _store_scoped_names(store_code, LICENSE_ENV_NAMES)
    service_secret = _first_env(service_names)
    license_key = _first_env(license_names)
    if not service_secret:
        expected = " / ".join(service_names)
        raise RuntimeError(f"Rakuten service secret is empty for store_code={store_code or 'default'}: {ENV_PATH} (set one of {expected})")
    if not license_key:
        expected = " / ".join(license_names)
        raise RuntimeError(f"Rakuten license key is empty for store_code={store_code or 'default'}: {ENV_PATH} (set one of {expected})")

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
