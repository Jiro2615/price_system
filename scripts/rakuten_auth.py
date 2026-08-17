import base64
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BASE_DIR.parent / ".env"


def _normalize_store_env_prefix(store_code: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", str(store_code or "").strip()).strip("_")
    if not normalized:
        raise RuntimeError("store_code is empty")
    return normalized.upper()


def _first_non_empty_env(names: list[str]) -> tuple[str | None, str | None]:
    for name in names:
        value = os.getenv(name)
        if value is not None and str(value).strip() != "":
            return name, str(value).strip()
    return None, None


def resolve_rakuten_store_code(store_code: str | None, rows: list[dict[str, Any]] | None = None) -> str:
    explicit = str(store_code or "").strip()
    if explicit:
        return explicit

    row_store_codes = {
        str(row.get("store_code") or "").strip()
        for row in (rows or [])
        if str(row.get("store_code") or "").strip()
    }

    if len(row_store_codes) == 1:
        return next(iter(row_store_codes))

    if len(row_store_codes) > 1:
        raise RuntimeError("multiple Rakuten stores found in targets. Specify --store explicitly")

    raise RuntimeError("store_code is empty")


def load_rakuten_auth(store_code: str) -> dict[str, str]:
    load_dotenv(ENV_PATH)

    env_prefix = _normalize_store_env_prefix(store_code)
    service_names = [f"{env_prefix}_SERVICE_SECRET"]
    license_names = [f"{env_prefix}_LICENSE_KEY"]

    service_name, service_secret = _first_non_empty_env(service_names)
    license_name, license_key = _first_non_empty_env(license_names)

    if not service_secret:
        expected = " / ".join(service_names)
        raise RuntimeError(
            f"Rakuten service secret is not configured for store_code={store_code}: {ENV_PATH} "
            f"(set one of {expected})"
        )

    if not license_key:
        expected = " / ".join(license_names)
        raise RuntimeError(
            f"Rakuten license key is not configured for store_code={store_code}: {ENV_PATH} "
            f"(set one of {expected})"
        )

    return {
        "store_code": store_code,
        "env_prefix": env_prefix,
        "service_secret_env": str(service_name or ""),
        "license_key_env": str(license_name or ""),
        "service_secret": service_secret,
        "license_key": license_key,
    }


def build_rakuten_auth_header(store_code: str) -> dict[str, str]:
    auth = load_rakuten_auth(store_code)
    token_src = f"{auth['service_secret']}:{auth['license_key']}".encode("utf-8")
    token = base64.b64encode(token_src).decode("ascii")

    return {
        "Authorization": f"ESA {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
