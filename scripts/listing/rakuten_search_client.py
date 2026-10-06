"""Backend-only, rate-limited RWS reads with safe and actionable errors."""
from __future__ import annotations

import ipaddress
import json
import os
from pathlib import Path
import re
import threading
import time
from urllib.parse import quote, quote_plus

import requests
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
ENDPOINT = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701"
_slot_lock = threading.Lock()
_error_lock = threading.Lock()
_next_request_at = 0.0
_logged_errors: dict[tuple[int | None, str], float] = {}
_public_ip_cache: tuple[float, str | None] = (0.0, None)


def safe_error_text(value: object, secrets: tuple[str, ...] = ()) -> str:
    text = str(value)
    for secret in secrets:
        if secret:
            for variant in (secret, quote(secret, safe=""), quote_plus(secret)):
                text = text.replace(variant, "[REDACTED]")
    text = re.sub(r"https?://\S+", "[URL omitted]", text)
    return re.sub(r"[A-Za-z0-9_+=/\-]{24,}", "[TOKEN omitted]", text)[:400]


class RakutenSearchError(RuntimeError):
    def __init__(self, code: str, message: str, status: int | None = None):
        self.code, self.message, self.status = code, message, status
        hint = ""
        if code == "CLIENT_IP_NOT_ALLOWED":
            hint = " / 接続元IPが未許可です。楽天アプリの許可IP設定を確認してください"
        elif code == "credentials_missing":
            hint = " / Application IDとAccess Keyの設定を確認してください"
        elif status == 429:
            hint = " / リクエスト制限です。時間を置いて再判定してください"
        super().__init__(f"楽天検索APIの取得エラー: {('HTTP ' + str(status) + ' / ') if status else ''}{code}: {message}{hint}")


def _wait_for_slot() -> None:
    global _next_request_at
    with _slot_lock:
        delay = _next_request_at - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        _next_request_at = time.monotonic() + 1.0


def public_ipv4() -> str | None:
    """Diagnostic only; never forward RWS credentials to the IP service."""
    global _public_ip_cache
    now = time.monotonic()
    if _public_ip_cache[0] > 0 and now - _public_ip_cache[0] < 60:
        return _public_ip_cache[1]
    value = None
    try:
        response = requests.get("https://api.ipify.org?format=json", timeout=5, allow_redirects=False)
        if response.status_code == 200:
            address = ipaddress.ip_address(str(response.json().get("ip", "")))
            if address.version == 4 and address.is_global:
                value = str(address)
    except (requests.RequestException, ValueError, TypeError, AttributeError):
        pass
    _public_ip_cache = (now, value)
    return value


def _raise_error(error: RakutenSearchError) -> None:
    key, now = (error.status, error.code), time.monotonic()
    with _error_lock:
        emit = now - _logged_errors.get(key, -60.0) >= 60
        if emit:
            _logged_errors[key] = now
    if emit:
        record = {"status": error.status, "code": error.code, "message": error.message,
                  "classification": "system_error", "product_ng": False}
        if error.code == "CLIENT_IP_NOT_ALLOWED":
            record["public_ipv4_to_check"] = public_ipv4()
        print("RAKUTEN_SEARCH_ERROR " + json.dumps(record, ensure_ascii=False), flush=True)
    raise error from None


def normalize_items(payload: object) -> list[dict]:
    if not isinstance(payload, dict):
        raise RakutenSearchError("invalid_response", "検索応答がJSONオブジェクトではありません")
    entries = payload.get("items", payload.get("Items"))
    if not isinstance(entries, list):
        raise RakutenSearchError("invalid_response", "検索応答に商品配列がありません")
    result = []
    for entry in entries:
        if isinstance(entry, dict):
            item = entry.get("item", entry.get("Item", entry))
            if isinstance(item, dict):
                result.append(item)
    return result


def search_items(keyword: str, timeout: float = 15.0, *, postage_included: bool = True) -> list[dict]:
    keyword = str(keyword or "").strip()
    if not keyword:
        return []
    load_dotenv(ENV_PATH)
    app = os.getenv("RAKUTEN_WEB_SERVICE_APPLICATION_ID", "").strip()
    key = os.getenv("RAKUTEN_WEB_SERVICE_ACCESS_KEY", "").strip()
    if not app or not key:
        _raise_error(RakutenSearchError("credentials_missing", "楽天市場検索用のキーが未設定です"))
    params = {"applicationId": app, "keyword": keyword, "sort": "standard",
              "availability": 1, "hits": 30, "format": "json", "formatVersion": 2}
    if postage_included:
        params["postageFlag"] = 1
    for attempt in range(3):
        _wait_for_slot()
        try:
            response = requests.get(ENDPOINT, params=params, headers={"accessKey": key},
                                    timeout=timeout, allow_redirects=False)
        except requests.RequestException as exc:
            _raise_error(RakutenSearchError(type(exc).__name__, "楽天検索への通信に失敗しました"))
        if response.status_code == 429 and attempt < 2:
            try:
                delay = max(1.0, float(response.headers.get("Retry-After", "1")))
            except (ValueError, TypeError):
                delay = 1.0
            if delay <= 5:
                time.sleep(delay)
                continue
        try:
            payload = response.json()
        except ValueError:
            _raise_error(RakutenSearchError("invalid_response", "JSON応答を取得できません", response.status_code))
        if not 200 <= response.status_code < 300:
            details = payload.get("errors", payload) if isinstance(payload, dict) else {}
            if isinstance(details, list):
                details = details[0] if details else {}
            details = details if isinstance(details, dict) else {}
            # The official API defines this exact 404 payload as no data,
            # unlike an unknown-route/authentication 404 or a broken response.
            if response.status_code == 404 and details.get("error") == "not_found":
                return []
            message = safe_error_text(details.get("errorMessage") or details.get("error_description") or details.get("message") or "取得を拒否されました", (app, key))
            code = safe_error_text(details.get("errorCode") or details.get("error") or "http_error", (app, key))
            if "CLIENT_IP_NOT_ALLOWED" in message:
                code = "CLIENT_IP_NOT_ALLOWED"
            _raise_error(RakutenSearchError(code, message, response.status_code))
        try:
            return normalize_items(payload)
        except RakutenSearchError as exc:
            _raise_error(exc)
    raise AssertionError("unreachable")
