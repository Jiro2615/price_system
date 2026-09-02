"""楽天の競合店舗から商品を拾い、Amazon.co.jp のASINへ照合する。

外部サイトは読み取り専用で扱う。楽天・Amazonへのログイン、カート操作、
API送信、出品、共有DB更新は行わない。結果はジョブ単位のJSONへ保存する。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote_plus, urlencode, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup


MAX_STORE_URLS = 300
MAX_PRODUCTS_PER_STORE = 100
MAX_CANDIDATE_SAMPLES = 500
MAX_FETCH_ATTEMPTS = 5
ASIN_RE = re.compile(r"^[A-Z0-9]{10}$")
AMAZON_WORD_RE = re.compile(r"amazon|アマゾン|(?<![A-Za-z0-9])fba(?![A-Za-z0-9])", re.IGNORECASE)
RAKUTEN_STORE_HOST = "search.rakuten.co.jp"
RAKUTEN_ITEM_HOST = "item.rakuten.co.jp"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--store", required=True, help="ASIN一括判定へ渡す自店舗コード")
    parser.add_argument("--store-url-file", type=Path, required=True)
    parser.add_argument("--products-per-store", type=int, default=20)
    parser.add_argument("--request-interval", type=float, default=0.5)
    parser.add_argument("--amazon-wait", type=float, default=1.0)
    parser.add_argument("--page-timeout", type=int, default=30000)
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.products_per_store <= MAX_PRODUCTS_PER_STORE:
        parser.error(f"--products-per-store は1〜{MAX_PRODUCTS_PER_STORE}で指定してください。")
    if not 0 <= args.request_interval <= 30:
        parser.error("--request-interval は0〜30秒で指定してください。")
    if not 0 <= args.amazon_wait <= 30:
        parser.error("--amazon-wait は0〜30秒で指定してください。")
    if not 5000 <= args.page_timeout <= 120000:
        parser.error("--page-timeout は5000〜120000ミリ秒で指定してください。")
    return args


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_store_url(value: str) -> tuple[str, str]:
    raw = str(value or "").strip()
    parsed = urlsplit(raw)
    if parsed.scheme.lower() != "https" or (parsed.hostname or "").lower() != RAKUTEN_STORE_HOST:
        raise ValueError("店舗URLは https://search.rakuten.co.jp/search/mall/?sid=... の形式で入力してください。")
    if parsed.path.rstrip("/") != "/search/mall":
        raise ValueError("楽天市場の店舗検索URLではありません。")
    sid_values = parse_qs(parsed.query).get("sid", [])
    sid = str(sid_values[0] if sid_values else "").strip()
    if not sid.isdecimal():
        raise ValueError("店舗URLに数値の sid がありません。")
    return f"https://{RAKUTEN_STORE_HOST}/search/mall/?sid={sid}", sid


def load_store_urls(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise ValueError("店舗URL入力ファイルが見つかりません。")
    raw_urls = [line.strip() for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    if not raw_urls:
        raise ValueError("店舗URLを1件以上入力してください。")
    if len(raw_urls) > MAX_STORE_URLS:
        raise ValueError(f"店舗URLは最大{MAX_STORE_URLS}件です。")
    stores: list[dict[str, str]] = []
    seen: set[str] = set()
    errors: list[str] = []
    for index, raw_url in enumerate(raw_urls, start=1):
        try:
            url, sid = normalize_store_url(raw_url)
        except ValueError as exc:
            errors.append(f"{index}行目: {exc}")
            continue
        if sid in seen:
            continue
        seen.add(sid)
        stores.append({"store_url": url, "sid": sid})
    if errors:
        raise ValueError(" ".join(errors[:10]))
    return stores


def decode_response(response: requests.Response) -> str:
    content_type = str(response.headers.get("content-type") or "")
    charset_match = re.search(r"charset\s*=\s*['\"]?([^;'\"\s]+)", content_type, re.I)
    candidates = [charset_match.group(1) if charset_match else "", response.encoding or "", "utf-8", "euc-jp", "cp932"]
    for encoding in dict.fromkeys(item for item in candidates if item):
        try:
            return response.content.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return response.content.decode("utf-8", errors="replace")


def canonical_item_url(value: str) -> tuple[str, str]:
    parsed = urlsplit(str(value or ""))
    if parsed.scheme not in {"http", "https"} or (parsed.hostname or "").lower() != RAKUTEN_ITEM_HOST:
        return "", ""
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2 or parts[1].lower() in {"c", "info", "shop"}:
        return "", ""
    item_code = parts[1]
    return f"https://{RAKUTEN_ITEM_HOST}/{parts[0]}/{item_code}/", item_code


def parse_store_products(html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    products: list[dict[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.select('a[href*="item.rakuten.co.jp"]'):
        item_url, item_code = canonical_item_url(str(anchor.get("href") or ""))
        if not item_url or item_url in seen:
            continue
        seen.add(item_url)
        image = anchor.find("img")
        title = normalize_space(
            str(anchor.get("title") or "")
            or (str(image.get("alt") or "") if image else "")
            or anchor.get_text(" ", strip=True)
        )
        products.append({"rakuten_url": item_url, "rakuten_title": title, "item_code": item_code})
    return products


def with_page_number(store_url: str, page_number: int) -> str:
    parsed = urlsplit(store_url)
    query = parse_qs(parsed.query)
    query["p"] = [str(page_number)]
    flat_query = [(key, item) for key, values in query.items() for item in values]
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(flat_query), ""))


def fetch_html(session: requests.Session, url: str, timeout_seconds: float = 30) -> str:
    response: requests.Response | None = None
    for attempt in range(MAX_FETCH_ATTEMPTS):
        response = session.get(url, timeout=timeout_seconds)
        if response.status_code not in {429, 500, 502, 503, 504}:
            response.raise_for_status()
            return decode_response(response)
        if attempt + 1 < MAX_FETCH_ATTEMPTS:
            retry_after = str(response.headers.get("retry-after") or "").strip()
            delay = float(retry_after) if retry_after.isdecimal() else min(2 ** (attempt + 1), 16)
            time.sleep(delay)
    assert response is not None
    response.raise_for_status()
    return decode_response(response)


def fetch_store_products(
    session: requests.Session,
    store_url: str,
    limit: int,
    request_interval: float,
) -> list[dict[str, str]]:
    products: list[dict[str, str]] = []
    seen: set[str] = set()
    for page_number in range(1, 101):
        page_url = with_page_number(store_url, page_number)
        html = fetch_html(session, page_url)
        page_products = parse_store_products(html)
        fresh = [item for item in page_products if item["rakuten_url"] not in seen]
        for item in fresh:
            seen.add(item["rakuten_url"])
            products.append(item)
            if len(products) >= limit:
                return products
        if not page_products or not fresh:
            break
        if request_interval:
            time.sleep(request_interval)
    return products


def amazon_keyword_context(html: str) -> tuple[bool, str]:
    soup = BeautifulSoup(html, "html.parser")
    # 楽天の商品ページは、選択肢など画面表示される商品固有の文言を
    # item-page-app-data のJSONからクライアント側で描画することがある。
    # 通常の script は誤検知を避けて除外し、この商品データJSONだけは
    # 可視本文と合わせて判定する。
    item_data_text = " ".join(
        element.get_text(" ", strip=True)
        for element in soup.select('script#item-page-app-data[type="application/json"]')
    )
    for element in soup(["script", "style", "noscript"]):
        element.decompose()
    searchable_text = unicodedata.normalize(
        "NFKC",
        f"{soup.get_text(' ', strip=True)} {item_data_text}",
    )
    match = AMAZON_WORD_RE.search(searchable_text)
    if not match:
        return False, ""
    start = max(0, match.start() - 60)
    end = min(len(searchable_text), match.end() + 100)
    return True, normalize_space(searchable_text[start:end])[:240]


def load_create_amazon_page():
    """Load the shared Amazon browser factory in package and script modes."""
    script_dir = str(Path(__file__).resolve().parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    from price_check_one_asin_db import create_amazon_page
    return create_amazon_page


def hinted_asin(item_code: str) -> str:
    value = str(item_code or "").strip().upper()
    return value if ASIN_RE.fullmatch(value) else ""


def comparable_title(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).lower()
    normalized = re.sub(r"【[^】]{0,40}】|\[[^\]]{0,40}\]", " ", normalized)
    normalized = re.sub(r"amazon|楽天市場|送料無料|あす楽|ポイント\d+倍", " ", normalized, flags=re.I)
    return re.sub(r"[^0-9a-z\u3040-\u30ff\u3400-\u9fff]+", "", normalized)


def title_similarity(left: str, right: str) -> float:
    a = comparable_title(left)
    b = comparable_title(right)
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a[:300], b[:300]).ratio()


def choose_amazon_candidate(
    rakuten_title: str,
    candidates: list[dict[str, str]],
    preferred_asin: str = "",
) -> dict[str, Any] | None:
    preferred = preferred_asin.upper()
    valid = [item for item in candidates if ASIN_RE.fullmatch(str(item.get("asin") or "").upper())]
    for item in valid:
        if preferred and str(item["asin"]).upper() == preferred:
            return {**item, "match_score": round(title_similarity(rakuten_title, item.get("title", "")), 4), "match_method": "item_code_confirmed_in_amazon_search"}
    scored = sorted(
        ((title_similarity(rakuten_title, item.get("title", "")), item) for item in valid),
        key=lambda entry: entry[0],
        reverse=True,
    )
    if not scored or scored[0][0] < 0.45:
        return None
    score, item = scored[0]
    return {**item, "match_score": round(score, 4), "match_method": "amazon_title_search"}


async def amazon_search_candidates(page, query: str, page_timeout_ms: int, wait_seconds: float) -> list[dict[str, str]]:
    url = f"https://www.amazon.co.jp/s?k={quote_plus(query[:400])}"
    await page.goto(url, wait_until="domcontentloaded", timeout=page_timeout_ms)
    if wait_seconds:
        await page.wait_for_timeout(int(wait_seconds * 1000))
    body_text = await page.locator("body").inner_text(timeout=5000)
    lowered = body_text.lower()
    if any(marker in lowered for marker in ("文字を入力してください", "ロボットではないことを証明", "captcha")):
        raise RuntimeError("Amazonで画像認証が表示されました。ブラウザで認証を解決してから再実行してください。")
    rows = await page.locator('[data-component-type="s-search-result"][data-asin]').evaluate_all(
        """els => els.slice(0, 10).map(el => ({
            asin: (el.getAttribute('data-asin') || '').trim().toUpperCase(),
            title: (el.querySelector('h2')?.innerText || el.querySelector('h2 span')?.textContent || '').trim(),
            url: el.querySelector('a[href*="/dp/"]')?.href || ''
        }))"""
    )
    return [dict(item) for item in rows if isinstance(item, dict)]


def result_template(args: argparse.Namespace, stores: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "run_id": args.run_id,
        "store": args.store,
        "started_at": utc_now(),
        "finished_at": "",
        "status": "running",
        "requested_store_count": len(stores),
        "products_per_store": args.products_per_store,
        "processed_store_count": 0,
        "eligible_store_count": 0,
        "store_not_found_count": 0,
        "not_amazon_source_count": 0,
        "searched_product_count": 0,
        "matched_product_count": 0,
        "unique_asin_count": 0,
        "asins": [],
        "candidate_samples": [],
        "store_results": [],
    }


def write_result(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def print_progress(result: dict[str, Any], current_sid: str = "") -> None:
    summary = {
        "processed_stores": result["processed_store_count"],
        "total_stores": result["requested_store_count"],
        "eligible_stores": result["eligible_store_count"],
        "searched_products": result["searched_product_count"],
        "matched_products": result["matched_product_count"],
        "unique_asins": result["unique_asin_count"],
        "sid": current_sid,
    }
    print("COMPETITOR_RESEARCH_PROGRESS " + json.dumps(summary, ensure_ascii=False), flush=True)


async def run(args: argparse.Namespace) -> int:
    stores = load_store_urls(args.store_url_file)
    result = result_template(args, stores)
    write_result(args.output_json, result)
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36",
        "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
    })
    playwright = browser = context = page = None
    asins: list[str] = []
    seen_asins: set[str] = set()

    try:
        for store in stores:
            store_result: dict[str, Any] = {
                **store,
                "status": "checking",
                "first_product_url": "",
                "amazon_keyword_context": "",
                "extracted_product_count": 0,
                "searched_product_count": 0,
                "matched_product_count": 0,
                "error": "",
            }
            result["store_results"].append(store_result)
            try:
                products = await asyncio.to_thread(
                    fetch_store_products,
                    session,
                    store["store_url"],
                    args.products_per_store,
                    args.request_interval,
                )
                store_result["extracted_product_count"] = len(products)
                if not products:
                    store_result["status"] = "store_not_found"
                    result["store_not_found_count"] += 1
                    continue

                first_product = products[0]
                store_result["first_product_url"] = first_product["rakuten_url"]
                first_html = await asyncio.to_thread(fetch_html, session, first_product["rakuten_url"])
                has_amazon, context_text = amazon_keyword_context(first_html)
                store_result["amazon_keyword_context"] = context_text
                if not has_amazon:
                    store_result["status"] = "not_amazon_source"
                    result["not_amazon_source_count"] += 1
                    continue

                store_result["status"] = "eligible"
                result["eligible_store_count"] += 1
                if page is None:
                    create_amazon_page = load_create_amazon_page()
                    playwright, browser, context, page = await create_amazon_page(start_minimized=True)

                for product in products:
                    title = product["rakuten_title"]
                    if not title:
                        product_html = await asyncio.to_thread(fetch_html, session, product["rakuten_url"])
                        product_soup = BeautifulSoup(product_html, "html.parser")
                        title_node = product_soup.select_one('meta[property="og:title"]')
                        title = normalize_space(str(title_node.get("content") or "")) if title_node else ""
                    store_result["searched_product_count"] += 1
                    result["searched_product_count"] += 1
                    candidates = await amazon_search_candidates(page, title, args.page_timeout, args.amazon_wait)
                    chosen = choose_amazon_candidate(title, candidates, hinted_asin(product["item_code"]))
                    if chosen is not None:
                        asin = str(chosen["asin"]).upper()
                        store_result["matched_product_count"] += 1
                        result["matched_product_count"] += 1
                        if asin not in seen_asins:
                            seen_asins.add(asin)
                            asins.append(asin)
                        if len(result["candidate_samples"]) < MAX_CANDIDATE_SAMPLES:
                            result["candidate_samples"].append({
                                "asin": asin,
                                "rakuten_title": title[:300],
                                "rakuten_url": product["rakuten_url"],
                                "amazon_title": str(chosen.get("title") or "")[:300],
                                "amazon_url": f"https://www.amazon.co.jp/dp/{asin}",
                                "match_score": chosen.get("match_score"),
                                "match_method": chosen.get("match_method"),
                                "source_sid": store["sid"],
                            })
                    result["asins"] = asins
                    result["unique_asin_count"] = len(asins)
                    write_result(args.output_json, result)
                    print_progress(result, store["sid"])
            except Exception as exc:
                store_result["status"] = "error"
                store_result["error"] = str(exc)
            finally:
                result["processed_store_count"] += 1
                result["asins"] = asins
                result["unique_asin_count"] = len(asins)
                write_result(args.output_json, result)
                print_progress(result, store["sid"])
                if args.request_interval:
                    await asyncio.sleep(args.request_interval)

        result["status"] = "succeeded"
        return 0
    finally:
        result["finished_at"] = utc_now()
        if result["status"] == "running":
            result["status"] = "partial"
        write_result(args.output_json, result)
        try:
            if page is not None:
                await page.close()
            if context is not None:
                await context.close()
            if browser is not None:
                await browser.close()
            if playwright is not None:
                await playwright.stop()
        except Exception:
            pass


def main() -> int:
    args = parse_args()
    try:
        return asyncio.run(run(args))
    except Exception as exc:
        print(f"COMPETITOR_RESEARCH_FATAL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
