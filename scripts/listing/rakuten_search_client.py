"""Backend-only, rate-limited RWS reads with safe and actionable errors."""
from __future__ import annotations

import ipaddress
import json
import math
import os
from pathlib import Path
import random
import re
import threading
import time
from datetime import timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote, quote_plus

import requests
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
ENDPOINT = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701"
MAX_SEARCH_ATTEMPTS = 6  # Initial request plus at most five retries.
MAX_RETRY_WAIT_SECONDS = 90.0
MAX_SINGLE_RETRY_WAIT_SECONDS = 60.0
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


def _wait_for_slot(*, max_wait_seconds: float = MAX_RETRY_WAIT_SECONDS) -> float:
    """Reserve one local request slot, observing cooldowns from other threads."""
    global _next_request_at
    started = time.monotonic()
    while True:
        with _slot_lock:
            now = time.monotonic()
            delay = _next_request_at - now
            waited = max(0.0, now - started)
            if delay <= 0:
                _next_request_at = now + 1.0
                return waited
            budget_exceeded = waited + delay > max_wait_seconds
        # Do not sleep while holding the lock: another thread receiving 429
        # must be able to extend the shared deadline before this thread sends.
        if budget_exceeded:
            _raise_error(RakutenSearchError("rate_limit_cooldown", "楽天検索の待機上限に達しました。時間を置いて再判定してください", 429))
        time.sleep(min(delay, 30.0))


def _defer_requests(delay: float) -> None:
    global _next_request_at
    with _slot_lock:
        _next_request_at = max(_next_request_at, time.monotonic() + max(1.0, delay))


def _error_details(payload: object) -> dict:
    details = payload.get("errors", payload) if isinstance(payload, dict) else {}
    if isinstance(details, list):
        details = details[0] if details else {}
    return details if isinstance(details, dict) else {}


def _retry_after_seconds(header: object, details: dict) -> float:
    """Respect server delays in Retry-After (seconds/date) or its error text."""
    delays = [0.0]
    value = str(header or "").strip()
    if value:
        try:
            seconds = float(value)
        except ValueError:
            try:
                date = parsedate_to_datetime(value)
                if date.tzinfo is None:
                    date = date.replace(tzinfo=timezone.utc)
                seconds = date.timestamp() - time.time()
            except (ValueError, TypeError, OverflowError):
                seconds = 0.0
        if math.isfinite(seconds):
            delays.append(max(0.0, seconds))
    message = str(details.get("errorMessage") or details.get("error_description") or details.get("message") or "")
    match = re.search(r"try\s+again\s+in\s+(\d+(?:\.\d+)?)\s*(?:seconds?|secs?)\b", message, flags=re.IGNORECASE)
    if match:
        seconds = float(match.group(1))
        if math.isfinite(seconds):
            delays.append(seconds)
    return max(delays)


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
    waited_seconds = 0.0
    for attempt in range(MAX_SEARCH_ATTEMPTS):
        waited_seconds += _wait_for_slot(max_wait_seconds=max(0.0, MAX_RETRY_WAIT_SECONDS - waited_seconds))
        try:
            response = requests.get(ENDPOINT, params=params, headers={"accessKey": key},
                                    timeout=timeout, allow_redirects=False)
        except requests.RequestException as exc:
            _raise_error(RakutenSearchError(type(exc).__name__, "楽天検索への通信に失敗しました"))
        try:
            payload = response.json()
        except ValueError:
            if response.status_code != 429:
                _raise_error(RakutenSearchError("invalid_response", "JSON応答を取得できません", response.status_code))
            payload = {}
        details = _error_details(payload)
        if response.status_code == 429:
            server_delay = _retry_after_seconds(response.headers.get("Retry-After"), details)
            delay = max(float(2 ** (attempt + 1)), server_delay) + random.uniform(0.0, 1.0)
            retry_allowed = (attempt + 1 < MAX_SEARCH_ATTEMPTS and delay <= MAX_SINGLE_RETRY_WAIT_SECONDS
                             and waited_seconds + delay <= MAX_RETRY_WAIT_SECONDS)
            _defer_requests(delay if retry_allowed else max(1.0, server_delay))
            if retry_allowed:
                print("RAKUTEN_SEARCH_RETRY " + json.dumps({"status": 429, "retry": attempt + 1,
                    "max_retries": MAX_SEARCH_ATTEMPTS - 1, "wait_seconds": round(delay, 2)}, ensure_ascii=False), flush=True)
                time.sleep(delay)
                waited_seconds += delay
                continue
        if not 200 <= response.status_code < 300:
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
