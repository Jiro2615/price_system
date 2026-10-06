"""Read-only Rakuten marketplace API probe; never print credentials or response item data.

Run directly from any working directory. This makes one search request and
does not import DB clients, run a listing, stop workers, or change settings.
"""
from __future__ import annotations

import argparse
from collections.abc import Mapping
import hashlib
import html
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import quote, quote_plus

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.listing.rakuten_marketplace_policy import ENDPOINT, ENV_PATH


def redact(value: object, secrets: tuple[str, ...]) -> str:
    text = str(value)
    for secret in secrets:
        if secret:
            for variant in (secret, quote(secret, safe=""), quote_plus(secret), html.escape(secret)):
                text = text.replace(variant, "[REDACTED]")
    text = re.sub(r"https?://\S+", "[URL omitted]", text)
    return re.sub(r"[A-Za-z0-9_+=/\-]{24,}", "[TOKEN omitted]", text)[:800]


def scrub_error_body(value: object, secrets: tuple[str, ...], depth: int = 0) -> object:
    """Remove named secrets even when the API uses an unfamiliar error shape."""
    if depth > 3:
        return "[nested content omitted]"
    if isinstance(value, dict):
        result = {}
        for key, item in list(value.items())[:20]:
            normalized_key = re.sub(r"[^a-z]", "", str(key).lower())
            sensitive = any(word in normalized_key for word in
                            ("password", "secret", "token", "authorization", "cookie", "accesskey", "apikey", "applicationid"))
            result[redact(key, secrets)] = "[REDACTED]" if sensitive else scrub_error_body(item, secrets, depth + 1)
        return result
    if isinstance(value, list):
        return [scrub_error_body(item, secrets, depth + 1) for item in value[:5]]
    return redact(value, secrets)


def diagnose(keyword: str = "シャープペン", timeout: float = 15.0) -> list[dict]:
    load_dotenv(ENV_PATH)
    application_id = os.getenv("RAKUTEN_WEB_SERVICE_APPLICATION_ID", "").strip()
    access_key = os.getenv("RAKUTEN_WEB_SERVICE_ACCESS_KEY", "").strip()
    records = [{"stage": "settings", "diagnostic_version": 2, "application_id_present": bool(application_id),
                "access_key_present": bool(access_key)}]
    if not application_id or not access_key:
        records.append({"stage": "result", "error": "credentials_missing"})
        return records
    # A short one-way marker allows cross-PC comparison without sharing keys.
    records[0]["credentials_marker"] = hashlib.sha256(
        ("rakuten-marketplace-credentials:v1\n" + application_id + "\n" + access_key).encode("utf-8")
    ).hexdigest()[:16]
    try:
        # Same endpoint, credentials, and filters as the production search.
        # Do not follow redirects with a credential-bearing header.
        response = requests.get(ENDPOINT, params={
            "applicationId": application_id, "keyword": keyword,
            "postageFlag": 1, "availability": 1, "hits": 30,
            "format": "json", "formatVersion": 2,
        }, headers={"accessKey": access_key}, timeout=timeout, allow_redirects=False)
    except requests.RequestException as exc:
        # Exception strings can contain a request URL and its applicationId.
        records.append({"stage": "transport_error", "exception_type": type(exc).__name__})
        return records
    result = {"stage": "response", "status": response.status_code}
    if not response.ok and isinstance(response.headers, Mapping):
        result["response_headers"] = {name: redact(response.headers[name], (application_id, access_key))
                                      for name in ("Content-Type", "Server", "X-Amzn-ErrorType", "X-Cache")
                                      if name in response.headers}
    try:
        body = response.json()
    except ValueError:
        result["error"] = "non_json_response"
        if not response.ok:
            result["error_body_excerpt"] = redact(response.text, (application_id, access_key))
        records.append(result)
        return records
    if not isinstance(body, dict):
        result["error"] = "unexpected_json_shape"
        if not response.ok:
            result["error_body_excerpt"] = redact(json.dumps(scrub_error_body(body, (application_id, access_key)), ensure_ascii=False), (application_id, access_key))
        records.append(result)
        return records
    for name in ("error", "error_description", "message", "code"):
        if name in body:
            result[name] = redact(body[name], (application_id, access_key))
    if not response.ok:
        result["error_body_fields"] = [redact(name, (application_id, access_key)) for name in list(body)[:20]]
        result["error_body_excerpt"] = redact(json.dumps(scrub_error_body(body, (application_id, access_key)), ensure_ascii=False), (application_id, access_key))
    if response.ok:
        count = body.get("count")
        result["search_count"] = count if isinstance(count, int) and not isinstance(count, bool) else None
        items = body.get("items") or body.get("Items") or []
        result["returned_items"] = len(items) if isinstance(items, list) else None
    records.append(result)
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keyword", default="シャープペン")
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args()
    if not args.keyword.strip() or not 0 < args.timeout <= 60:
        parser.error("keyword is required and timeout must be between 0 and 60 seconds")
    for record in diagnose(args.keyword, args.timeout):
        print(json.dumps(record, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
