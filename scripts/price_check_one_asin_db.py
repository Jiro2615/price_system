import argparse
import asyncio
import builtins
import importlib.util
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from playwright.async_api import async_playwright

from db_config import connect_db
from db_retry import run_with_db_retry


def configure_output() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None or not hasattr(stream, "reconfigure"):
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def safe_print(*args, **kwargs) -> None:
    try:
        builtins.print(*args, **kwargs)
    except UnicodeEncodeError:
        sep = kwargs.get("sep", " ")
        end = kwargs.get("end", "\n")
        file = kwargs.get("file", sys.stdout)
        flush = kwargs.get("flush", False)
        text = sep.join(str(arg) for arg in args)
        encoding = getattr(file, "encoding", None) or "utf-8"
        safe_text = text.encode(encoding, errors="replace").decode(encoding, errors="replace")
        builtins.print(safe_text, end=end, file=file, flush=flush)


configure_output()
print = safe_print


def now_dt() -> datetime:
    return datetime.now()


def parse_price(text: str) -> int:
    s = str(text or "")
    s = s.replace("￥", "").replace("\\", "").replace(",", "").replace("円", "").replace("税込", "")
    s = re.sub(r"\s+", "", s)
    m = re.search(r"\d+(?:\.\d+)?", s)
    return int(float(m.group(0))) if m else 0


def parse_yen_price(text: str) -> int:
    """Extract a price after ￥/¥, not a leading discount percentage."""
    matches = re.findall(r"[￥¥]\s*([0-9][0-9,]*)", str(text or ""))
    try:
        return int(matches[-1].replace(",", "")) if matches else 0
    except ValueError:
        return 0


_NON_NEW_CONDITION_MARKERS = ("中古", "整備済み", "再生品", "アウトレット", "展示品", "コレクター")
_OFFER_CONDITION_PATTERN = re.compile(
    r"新品同様|中古|整備済み|再生品|アウトレット|展示品|コレクター|新品"
)


def is_explicit_new_offer_text(in_text: str) -> bool:
    """Accept an Amazon offer only when its condition is explicitly ``新品``."""
    normalized = re.sub(r"\s+", " ", str(in_text or "")).strip()
    # A trailing used-offer teaser belongs to a different offer.  The first
    # condition in the primary BuyBox/offer block decides eligibility.
    match = _OFFER_CONDITION_PATTERN.search(normalized)
    return bool(match and match.group(0) == "新品")


def extract_asin(url: str) -> str:
    m = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", url, re.I)
    return m.group(1).upper() if m else ""


def build_amazon_product_url(asin: str) -> str:
    return f"https://www.amazon.co.jp/dp/{asin.strip().upper()}?th=1&psc=1"


def calc_diff_days(month_num: int, day_num: int) -> Optional[int]:
    if not (1 <= month_num <= 12):
        return None
    if not (1 <= day_num <= 31):
        return None

    today = date.today()

    try:
        target = date(today.year, month_num, day_num)
    except ValueError:
        return None

    if target < today:
        try:
            target = date(today.year + 1, month_num, day_num)
        except ValueError:
            return None

    return (target - today).days


def is_prime_amazon_official_offer_text(in_text: str) -> bool:
    normalized = re.sub(r"\s+", " ", str(in_text or "")).strip()
    if "prime" not in normalized.lower():
        return False
    direct_amazon = bool(re.search(r"出荷元\s*/\s*販売元\s*Amazon\.co\.jp", normalized, re.I))
    separate_amazon = bool(re.search(r"出荷元\s*Amazon\.co\.jp", normalized, re.I)) and bool(
        re.search(r"販売元\s*Amazon\.co\.jp", normalized, re.I)
    )
    customer_service_amazon = bool(re.search(r"カスタマーサービス\s*Amazon\.co\.jp", normalized, re.I))
    return (direct_amazon or separate_amazon) and customer_service_amazon


def is_amazon_delivery_origin_offer_text(in_text: str) -> bool:
    """``配送元`` / ``発送元`` Amazon is not an eligible ``出荷元`` offer."""
    normalized = re.sub(r"\s+", "", str(in_text or ""))
    return bool(re.search(r"(?:配送元|発送元)[\s:：]*Amazon(?:\.co\.jp)?", normalized, re.I))


def judge_basic_ng(in_text: str) -> str:
    if "在庫切れ" in in_text:
        return "在庫切れ"
    if is_amazon_delivery_origin_offer_text(in_text):
        return "配送元Amazonは対象外（出荷元Amazonのみ採用）"
    if "ギフト" not in in_text and not is_prime_amazon_official_offer_text(in_text):
        return "ギフト不可"
    return ""


def parse_shipping_status(in_text: str) -> tuple[str, str]:
    text = re.sub(r"\s+", "", in_text or "")

    if "通常1~2か月以内に発送します" in text:
        return "NG", "発送遅い"

    if re.search(r"(お届け|配送|配達|到着).{0,30}(明日|翌日|本日|今日)", text):
        return "OK", "配送OK"

    if re.search(r"(明日|翌日|本日|今日).{0,30}(お届け|配送|配達|到着)", text):
        return "OK", "配送OK"

    send_week: Optional[int] = None
    diff_days: Optional[int] = None

    m = re.search(r"(\d+)日以内.*?(お届け|配送|配達|到着)", text)
    if not m:
        m = re.search(r"(お届け|配送|配達|到着).{0,20}?(\d+)日以内", text)
        if m:
            send_week = int(m.group(2))
    if m:
        send_week = send_week or int(m.group(1))

    date_match = re.search(
        r"(?:お届け|配送|配達|到着).{0,20}?([0-9]{1,2})月([0-9]{1,2})日",
        text,
    )
    if not date_match:
        date_match = re.search(
            r"([0-9]{1,2})月([0-9]{1,2})日.{0,20}?(?:お届け|配送|配達|到着)",
            text,
        )
    if date_match:
        diff_days = calc_diff_days(int(date_match.group(1)), int(date_match.group(2)))

    if send_week == 1:
        return "OK", "配送OK"

    if diff_days is not None and 0 <= diff_days < 7:
        return "OK", "配送OK"

    if send_week is None and diff_days is None:
        return "NG", "発送日情報なし"

    return "NG", "発送遅い"


async def safe_inner_text(locator) -> str:
    try:
        return (await locator.inner_text(timeout=2000)).strip()
    except Exception:
        return ""


async def get_first_text(page, selector: str) -> str:
    loc = page.locator(selector)
    for i in range(await loc.count()):
        text = await safe_inner_text(loc.nth(i))
        if text:
            return text
    return ""


async def get_page_asin(page) -> str:
    candidates = [extract_asin(getattr(page, "url", ""))]

    for selector in ("input[name=\"ASIN\"]", "#ASIN", "input[name=\"ASIN.0\"]"):
        try:
            loc = page.locator(selector)
            if await loc.count() == 0:
                continue
            value = (await loc.first.get_attribute("value")) or ""
            if value:
                candidates.append(value.strip())
        except Exception:
            continue

    for candidate in candidates:
        normalized = (candidate or "").strip().upper()
        if re.fullmatch(r"[A-Z0-9]{10}", normalized):
            return normalized

    try:
        canonical_href = await page.locator('link[rel="canonical"]').first.get_attribute("href")
        if canonical_href:
            candidates.append(extract_asin(canonical_href))
    except Exception:
        pass

    for selector in ("[data-asin]", "#dp", "[data-defaultasin]", "[data-current-asin]"):
        try:
            loc = page.locator(selector)
            if await loc.count() == 0:
                continue
            for attr_name in ("data-asin", "data-defaultasin", "data-current-asin"):
                value = (await loc.first.get_attribute(attr_name)) or ""
                normalized = value.strip().upper()
                if re.fullmatch(r"[A-Z0-9]{10}", normalized):
                    return normalized
        except Exception:
            continue

    return ""


async def detect_high_price_warning(page, body_text: str = "") -> bool:
    targets = [body_text or ""]
    for selector in (
        "#fod-cx-message-with-learn-more",
        "#fod-cx-box",
        "#fodcx_feature_div",
    ):
        text = await get_first_text(page, selector)
        if text:
            targets.append(text)

    return any("一般的な価格より高い価格です" in text for text in targets)


async def detect_black_curtain_restriction(page, current_url: str, body_text: str = "") -> tuple[str, str]:
    body_text = body_text or ""
    warning_text = await get_first_text(page, "#black-curtain-warning")
    statement_text = await get_first_text(page, "#black-curtain-statement")
    page_title = ""
    try:
        page_title = await page.title()
    except Exception:
        page_title = ""

    if (
        "/black-curtain/black-curtain" in current_url
        or "年齢確認" in warning_text
        or "18歳未満" in statement_text
        or "18歳以上ですか" in body_text
    ):
        return ("adult", "閲覧制限（成人向け年齢確認）")

    if (
        "/black-curtain/medical-black-curtain" in current_url
        or "専門医療機器" in page_title
        or "医療従事者のみ" in statement_text
        or "あなたは医療専門家ですか" in body_text
    ):
        return ("medical", "購入資格制限（医療従事者限定）")

    return ("", "")


async def detect_404_or_region_restriction(page, current_url: str, body_text: str = "") -> bool:
    body_text = body_text or ""
    page_title = ""
    try:
        page_title = await page.title()
    except Exception:
        page_title = ""

    link_hit = False
    image_hit = False
    try:
        link_hit = await page.locator("a[href*='ref=cs_404_logo'], a[href*='ref=cs_404_link']").count() > 0
    except Exception:
        link_hit = False
    try:
        image_hit = await page.locator("img[src*='kailey-kitty']").count() > 0
    except Exception:
        image_hit = False

    signals = (
        "何かお探しですか？" in body_text
        or "入力されたウェブアドレスは当社サイトの有効なページではない" in body_text
        or "お客様の所在地からは表示されない可能性があります" in body_text
        or "何かお探しですか？" in page_title
        or "有効なページではない" in page_title
        or image_hit
        or link_hit
        or "/ref=cs_404_logo" in current_url
        or "/ref=cs_404_link" in current_url
    )
    return signals


async def detect_used_only_buybox(page, body_text: str = "") -> tuple[bool, Optional[int]]:
    body_text = body_text or ""
    used_section_text = await get_first_text(page, "#usedBuySection")
    used_buybox_text = await get_first_text(page, "#usedbuyBox")
    used_merchant_text = await get_first_text(page, "#usedMerchantID")
    add_to_cart_ubb_text = await get_first_text(page, "#add-to-cart-button-ubb")
    merchant_info_text = await get_first_text(page, "#merchant-info")

    used_selectors_present = False
    for selector in ("#usedBuySection", "#usedbuyBox", "#usedMerchantID", "#add-to-cart-button-ubb"):
        try:
            if await page.locator(selector).count() > 0:
                used_selectors_present = True
                break
        except Exception:
            continue

    combined_used_text = "\n".join(
        filter(
            None,
            [
                body_text,
                used_section_text,
                used_buybox_text,
                used_merchant_text,
                add_to_cart_ubb_text,
            ],
        )
    )
    has_used_signal = used_selectors_present or "中古商品:" in combined_used_text or "中古商品" in combined_used_text

    new_add_to_cart_text = await get_first_text(page, "#add-to-cart-button")
    submit_add_to_cart_text = await get_first_text(page, "input[name=\"submit.add-to-cart\"]")

    try:
        new_add_to_cart_count = await page.locator("#add-to-cart-button").count()
    except Exception:
        new_add_to_cart_count = 0
    try:
        submit_add_to_cart_count = await page.locator("input[name=\"submit.add-to-cart\"]").count()
    except Exception:
        submit_add_to_cart_count = 0
    try:
        buy_now_count = await page.locator("#buy-now-button").count()
    except Exception:
        buy_now_count = 0

    has_real_add_to_cart_button = (
        new_add_to_cart_count > 0
        and has_actual_purchase_button_text(new_add_to_cart_text)
    ) or (
        submit_add_to_cart_count > 0
        and has_actual_purchase_button_text(submit_add_to_cart_text)
    )
    has_new_purchase_button = buy_now_count > 0 or has_real_add_to_cart_button
    has_new_price_block = await get_price_from_selector(page, "#corePriceDisplay_desktop_feature_div") > 0
    has_new_offer_signal = bool(merchant_info_text.strip())

    used_price = 0
    for selector in (
        "#usedbuyBox .a-offscreen",
        "#usedbuyBox .a-price-whole",
        "#usedBuySection .a-offscreen",
        "#usedBuySection .a-price-whole",
        "#apex-pricetopay-accessibility-label",
        ".priceToPay .a-offscreen",
        ".priceToPay .a-price-whole",
    ):
        price = await get_price_from_selector(page, selector) if selector.endswith(".a-offscreen") or selector.endswith(".a-price-whole") else 0
        if price <= 0:
            text = await get_first_text(page, selector)
            price = parse_price(text)
        if price > 0:
            used_price = price
            break

    has_new_buybox = has_new_purchase_button or has_new_price_block or has_new_offer_signal
    return (has_used_signal and not has_new_buybox, used_price or None)


def log_result_summary(
    requested_asin: str,
    page_asin: str,
    current_url: str,
    result: dict[str, Any],
) -> None:
    status = "system_error" if result.get("system_error") else (
        "business_ng" if result.get("business_ng") else "ok"
    )
    print(
        "amazon_result_summary "
        f"requested_asin={requested_asin} "
        f"page_asin={page_asin or '-'} "
        f"current_url={current_url} "
        f"status={status} "
        f"ng_reason={result.get('ng_reason', '')}"
    )


async def detect_page_state(page) -> dict[str, bool]:
    body_text = await get_first_text(page, "body")
    availability_text = await get_first_text(page, "#availability")
    out_of_stock_text = await get_first_text(page, "#outOfStock")
    buybox_text = await get_first_text(page, "#buybox")
    desktop_buybox_text = await get_first_text(page, "#desktop_buybox")
    merchant_info_text = await get_first_text(page, "#merchant-info")
    add_to_cart_text = await get_first_text(page, "#addToCart")

    price_visible = False
    for selector in (
        "#corePriceDisplay_desktop_feature_div .a-price-whole",
        "#corePriceDisplay_desktop_feature_div .a-offscreen",
        "#priceToPay .a-price-whole",
        "#priceToPay .a-offscreen",
        ".a-price-whole",
        ".a-offscreen",
    ):
        try:
            loc = page.locator(selector)
            if await loc.count() > 0:
                text = await safe_inner_text(loc.first)
                if parse_price(text) > 0:
                    price_visible = True
                    break
        except Exception:
            continue

    text_blob = "\n".join(
        filter(
            None,
            [
                body_text,
                availability_text,
                out_of_stock_text,
                buybox_text,
                desktop_buybox_text,
                merchant_info_text,
                add_to_cart_text,
            ],
        )
    )

    explicit_unavailable = bool(
        out_of_stock_text.strip()
        or await detect_buybox_unavailable_reason(page, body_text)
    )
    explicit_buybox_missing = "縺吶∋縺ｦ縺ｮ蜃ｺ蜩√ｒ隕九ｋ" in text_blob

    return {
        "price_visible": price_visible,
        "explicit_unavailable": explicit_unavailable,
        "explicit_buybox_missing": explicit_buybox_missing,
    }


async def wait_for_meaningful_page_state(
    page,
    timeout_ms: int,
    poll_ms: int = 250,
) -> dict[str, bool]:
    deadline = asyncio.get_running_loop().time() + max(timeout_ms, 0) / 1000.0
    last_state = {
        "price_visible": False,
        "explicit_unavailable": False,
        "explicit_buybox_missing": False,
    }

    while True:
        last_state = await detect_page_state(page)
        if (
            last_state["price_visible"]
            or last_state["explicit_unavailable"]
            or last_state["explicit_buybox_missing"]
        ):
            return last_state

        if asyncio.get_running_loop().time() >= deadline:
            return last_state

        await page.wait_for_timeout(poll_ms)


async def click_force(locator) -> None:
    try:
        await locator.scroll_into_view_if_needed(timeout=5000)
    except Exception:
        pass

    try:
        await locator.click(timeout=5000)
    except Exception:
        await locator.evaluate("el => el.click()")


async def expand_see_more(locator, page) -> None:
    try:
        see_more = locator.locator(
            "xpath=.//a[contains(@data-action,'a-expander-toggle') and .//span[contains(text(),'すべて見る')]]"
        )
        if await see_more.count() > 0:
            target = see_more.first
            if await target.is_visible(timeout=500):
                await click_force(target)
                await page.wait_for_timeout(500)
    except Exception:
        pass


async def get_price_from_locator(locator) -> int:
    for css in [".a-price-whole", ".a-offscreen"]:
        loc = locator.locator(css)
        for i in range(await loc.count()):
            price = parse_price(await safe_inner_text(loc.nth(i)))
            if price > 0:
                return price
    return 0


async def get_alt_price_from_buybox(page) -> int:
    buybox = page.locator("#buybox")
    root = buybox if await buybox.count() > 0 else page
    loc = root.locator(".a-price.a-text-price.a-size-medium")

    for i in range(await loc.count()):
        price = parse_price(await safe_inner_text(loc.nth(i)))
        if price > 0:
            return price

    return 0


async def get_price_from_selector(page, selector: str) -> int:
    loc = page.locator(selector)
    if await loc.count() == 0:
        return 0
    return await get_price_from_locator(loc.first)


async def collect_selector_diagnostics(page) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    selectors = (
        "#buybox",
        "#desktop_buybox",
        "#corePriceDisplay_desktop_feature_div",
        "#availability",
        "#outOfStock",
        "#merchant-info",
        "#addToCart",
        "#add-to-cart-button",
        "input[name=\"submit.add-to-cart\"]",
        "#buy-now-button",
    )

    for selector in selectors:
        count = 0
        text = ""
        try:
            loc = page.locator(selector)
            count = await loc.count()
            if count > 0:
                text = await safe_inner_text(loc.first)
        except Exception as e:
            text = f"[selector_error] {e}"
        diagnostics.append({"selector": selector, "count": count, "text": text})

    return diagnostics


async def save_debug_html(page, asin: str) -> Optional[Path]:
    try:
        output_dir = Path(__file__).resolve().parent.parent / "output" / "amazon_debug"
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = output_dir / f"{asin}_{timestamp}.html"
        html = await page.content()
        output_path.write_text(html, encoding="utf-8")
        return output_path
    except Exception as e:
        print(f"debug_html save error: {e}")
        return None


def parse_available_qty(text: str) -> Optional[int]:
    try:
        normalized = re.sub(r"\s+", "", text or "")
        if not normalized:
            return None

        patterns = (
            r"残り(\d+)点",
            r"残り(\d+)個",
            r"在庫(\d+)点",
            r"在庫(\d+)個",
            r"(\d+)点在庫あり",
            r"(\d+)個在庫あり",
            r"利用可能な出品数(\d+)",
        )
        for pattern in patterns:
            match = re.search(pattern, normalized)
            if match:
                return int(match.group(1))

        if "在庫あり" in normalized:
            return 1

        return None
    except Exception:
        return None


def quantity_dropdown_details(options: list[tuple[str, str]]) -> tuple[Optional[int], Optional[int]]:
    quantities: list[int] = []
    minimum_order_quantity: Optional[int] = None
    for raw_value, raw_text in options:
        value = re.sub(r"\s+", "", str(raw_value or ""))
        text = re.sub(r"\s+", "", str(raw_text or ""))
        match = re.fullmatch(r"[1-9]\d*", value) or re.match(r"([1-9]\d*)", text)
        if not match:
            continue
        quantity = int(match.group(1) if match.lastindex else match.group(0))
        quantities.append(quantity)
        if "最小注文個数" in text:
            minimum_order_quantity = quantity
    return (max(quantities) if quantities else None, minimum_order_quantity)


def minimum_order_quantity_from_offer_text(*texts: object) -> Optional[int]:
    """Read Amazon AOD's visible ``最小注文数: 2`` style constraint."""
    for raw_text in texts:
        normalized = re.sub(r"\s+", "", str(raw_text or ""))
        match = re.search(r"最小注文(?:個数|数)[:：]?([1-9]\d*)", normalized)
        if match:
            return int(match.group(1))
        match = re.search(r'"minQty"\s*:\s*([1-9]\d*)', str(raw_text or ""))
        if match:
            return int(match.group(1))
    return None


async def get_quantity_dropdown_details(page, root=None) -> tuple[Optional[int], Optional[int]]:
    roots = [root] if root is not None else []
    roots.append(page)
    selectors = ("#quantity select", "#quantityRelocateFeature select", "select[name='quantity']", "select#quantity")
    for candidate_root in roots:
        if candidate_root is None:
            continue
        for selector in selectors:
            try:
                select = candidate_root.locator(selector).first
                if await select.count() == 0:
                    continue
                options = select.locator("option")
                option_values: list[tuple[str, str]] = []
                for index in range(await options.count()):
                    option = options.nth(index)
                    option_values.append(((await option.get_attribute("value")) or "", await safe_inner_text(option)))
                maximum, minimum_order_quantity = quantity_dropdown_details(option_values)
                if maximum is not None:
                    return maximum, minimum_order_quantity
            except Exception:
                continue
    return None, None


def apply_minimum_order_block(result: dict[str, Any], minimum_order_quantity: Optional[int]) -> None:
    result["minimum_order_quantity"] = minimum_order_quantity
    if minimum_order_quantity and minimum_order_quantity > 1:
        result["business_ng"] = True
        result["ng_reason"] = f"最小注文個数が{minimum_order_quantity}個です"


async def parse_point(page) -> int:
    loc = page.locator("#pointsInsideBuyBox_feature_div")
    if await loc.count() == 0:
        return 0

    text = await safe_inner_text(loc.first)
    m = re.search(r"(\d+)pt", text)
    return int(m.group(1)) if m else 0


async def get_title(page) -> str:
    loc = page.locator("#productTitle")
    if await loc.count() == 0:
        return ""
    return (await safe_inner_text(loc.first)).strip()


async def detect_buybox_unavailable_reason(page, body_text: str) -> str:
    parts = [body_text or ""]

    for selector in (
        "#outOfStock",
        "#availability",
        "#availabilityInsideBuyBox_feature_div",
    ):
        text = await get_first_text(page, selector)
        if text:
            parts.append(text)

    combined_text = "\n".join(parts)

    patterns = (
        "現在在庫切れです",
        "一時的に在庫切れ",
        "入荷時期は未定です",
        "この商品は現在お取り扱いできません",
        "この商品は、現在お取り扱いできません",
        "現在お取り扱いできません",
        "再入荷予定は立っておりません",
    )
    for pattern in patterns:
        if pattern in combined_text:
            return "BuyBoxなし"

    return ""


def has_actual_purchase_button_text(text: str) -> bool:
    normalized = re.sub(r"\s+", "", text or "")
    if not normalized:
        return False

    labels = (
        "繧ｫ繝ｼ繝医↓蜈･繧後ｋ",
        "今すぐ買う",
        "購入する",
    )
    return any(label in normalized for label in labels)


def is_generic_availability_text(text: str) -> bool:
    normalized = re.sub(r"\s+", "", text or "")
    return normalized in {"在庫状況について", "在庫状況"}


async def read_lowest_amazon_fulfilled_offer(page) -> Optional[dict[str, Any]]:
    """Read a real price-to-pay from the all-offers panel when BuyBox is absent."""
    ingress = page.locator("#aod-ingress-link")
    if await ingress.count() == 0:
        ingress = page.locator("a[href*='/gp/offer-listing/']").first
    if await ingress.count() == 0:
        return None
    try:
        await ingress.first.click(timeout=5000)
        offers = page.locator("#aod-offer-list #aod-offer")
        await offers.first.wait_for(state="visible", timeout=10000)
    except Exception:
        return None
    candidates: list[dict[str, Any]] = []
    for index in range(await offers.count()):
        offer = offers.nth(index)
        try:
            ships_from = re.sub(r"\s+", " ", await safe_inner_text(offer.locator("#aod-offer-shipsFrom").first)).strip()
            if is_amazon_delivery_origin_offer_text(ships_from) or not re.match(r"^出荷元\s*Amazon(?:\.co\.jp)?\s*$", ships_from, re.I):
                continue
            price = parse_price(await safe_inner_text(offer.locator(".apex-pricetopay-value .a-price-whole").first))
            if price <= 0:
                price = parse_yen_price(await safe_inner_text(offer.locator(".apex-pricetopay-accessibility-label").first))
            delivery = offer.locator("[data-csa-c-delivery-price]").first
            delivery_price = await delivery.get_attribute("data-csa-c-delivery-price") if await delivery.count() else ""
            offer_text = await safe_inner_text(offer)
            if not is_explicit_new_offer_text(offer_text) or price <= 0 or delivery_price != "無料":
                continue
            candidates.append({
                "price": price,
                "offer_index": index,
                "offer_text": offer_text,
                "minimum_order_quantity": minimum_order_quantity_from_offer_text(offer_text),
            })
        except Exception:
            continue
    return min(candidates, key=lambda item: item["price"]) if candidates else None


async def read_buybox_info(page) -> dict[str, Any]:
    result = {
        "in_text": "",
        "price": 0,
    }

    buybox = page.locator("#buybox")
    root = buybox if await buybox.count() > 0 else page

    groups = root.locator(".a-box-group")
    if await groups.count() == 0:
        groups = page.locator(".a-box-group")

    if await groups.count() == 0:
        return result

    group = groups.first
    await expand_see_more(group, page)

    result["in_text"] = await safe_inner_text(group)
    result["price"] = await get_price_from_locator(group)

    return result


async def create_amazon_page() -> tuple[Any, Any, Any, Any]:
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(
        channel="chrome",
        headless=False,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check",
        ],
    )

    context = await browser.new_context(
        viewport={"width": 1280, "height": 900},
        locale="ja-JP",
    )

    page = await context.new_page()
    return playwright, browser, context, page


async def close_amazon_page(playwright, browser, context, page) -> None:
    try:
        if page is not None:
            await page.close()
    except Exception:
        pass

    try:
        if context is not None:
            await context.close()
    except Exception:
        pass

    try:
        if browser is not None:
            await browser.close()
    except Exception:
        pass

    try:
        if playwright is not None:
            await playwright.stop()
    except Exception:
        pass


async def check_amazon_one(
    asin: str,
    page=None,
    page_timeout_ms: int = 60000,
    settle_timeout_ms: int = 1000,
    debug_html: bool = False,
) -> dict[str, Any]:
    asin = asin.strip().upper()

    result = {
        "asin": asin,
        "title": "",
        "amazon_price": None,
        "amazon_point": 0,
        "available_qty": None,
        "gift_available": None,
        "shipping_status": "",
        "business_ng": False,
        "system_error": False,
        "ng_reason": "",
        "checked_at": now_dt(),
        "page_needs_reset": False,
    }

    own_page = page is None
    playwright = None
    browser = None
    context = None

    try:
        if own_page:
            playwright, browser, context, page = await create_amazon_page()

        try:
            url = build_amazon_product_url(asin)
            print(f"Amazon確認開始: {url}")

            await page.goto(url, wait_until="domcontentloaded", timeout=page_timeout_ms)
            await page.wait_for_timeout(settle_timeout_ms)

            body = await get_first_text(page, "body")
            if "下に表示されている文字を入力してください" in body:
                result["system_error"] = True
                result["ng_reason"] = "画像認証"
                return result

            current_asin = extract_asin(page.url)
            if current_asin and current_asin != asin:
                result["system_error"] = True
                result["ng_reason"] = f"ASIN不一致 current={current_asin}"
                return result

            result["title"] = await get_title(page)

            out_of_stock_text = await get_first_text(page, "#outOfStock")
            if out_of_stock_text.strip():
                result["business_ng"] = True
                result["ng_reason"] = "在庫切れ"
                result["shipping_status"] = "NG"
                return result

            buy_info = await read_buybox_info(page)

            if not buy_info["in_text"]:
                selector_diagnostics = await collect_selector_diagnostics(page)
                diagnostics_map = {
                    item["selector"]: item for item in selector_diagnostics
                }
                print("BuyBox取得失敗 diagnostics:")
                for item in selector_diagnostics:
                    preview = re.sub(r"\s+", " ", item["text"] or "")[:120]
                    print(
                        f"  {item['selector']}: count={item['count']} text={preview}"
                    )

                if debug_html:
                    debug_path = await save_debug_html(page, asin)
                    if debug_path is not None:
                        print(f"debug_html saved: {debug_path}")

                availability_text = diagnostics_map.get("#availability", {}).get(
                    "text", ""
                )
                merchant_info_text = diagnostics_map.get("#merchant-info", {}).get(
                    "text", ""
                )
                buybox_text = diagnostics_map.get("#buybox", {}).get("text", "")
                desktop_buybox_text = diagnostics_map.get("#desktop_buybox", {}).get(
                    "text", ""
                )
                add_to_cart_text = diagnostics_map.get("#addToCart", {}).get("text", "")
                add_to_cart_count = diagnostics_map.get("#addToCart", {}).get(
                    "count", 0
                )
                add_to_cart_button_text = diagnostics_map.get(
                    "#add-to-cart-button", {}
                ).get("text", "")
                add_to_cart_button_count = diagnostics_map.get(
                    "#add-to-cart-button", {}
                ).get("count", 0)
                submit_add_to_cart_text = diagnostics_map.get(
                    "input[name=\"submit.add-to-cart\"]", {}
                ).get("text", "")
                submit_add_to_cart_count = diagnostics_map.get(
                    "input[name=\"submit.add-to-cart\"]", {}
                ).get("count", 0)
                buy_now_count = diagnostics_map.get("#buy-now-button", {}).get(
                    "count", 0
                )
                add_to_cart_is_offer_link = "すべての出品を見る" in add_to_cart_text
                has_real_add_to_cart_button = (
                    add_to_cart_button_count > 0
                    and has_actual_purchase_button_text(add_to_cart_button_text)
                ) or (
                    submit_add_to_cart_count > 0
                    and has_actual_purchase_button_text(submit_add_to_cart_text)
                )
                has_purchase_button = buy_now_count > 0 or has_real_add_to_cart_button
                fallback_text = "\n".join(
                    filter(
                        None,
                        [
                            body,
                            out_of_stock_text,
                            availability_text,
                            merchant_info_text,
                            buybox_text,
                            desktop_buybox_text,
                            add_to_cart_text,
                            add_to_cart_button_text,
                            submit_add_to_cart_text,
                        ],
                    )
                )
                fallback_price = int(buy_info["price"] or 0)
                if fallback_price <= 0:
                    fallback_price = await get_alt_price_from_buybox(page)
                if fallback_price <= 0:
                    fallback_price = await get_price_from_selector(
                        page, "#corePriceDisplay_desktop_feature_div"
                    )
                fallback_qty = parse_available_qty(fallback_text)
                fallback_point = await parse_point(page)
                availability_has_stock_signal = bool(availability_text) and not is_generic_availability_text(
                    availability_text
                )
                offer_listing_only = (
                    "すべての出品を見る" in buybox_text
                    or "すべての出品を見る" in desktop_buybox_text
                    or add_to_cart_is_offer_link
                )
                missing_core_purchase_info = (
                    fallback_price <= 0
                    and not availability_has_stock_signal
                    and not merchant_info_text
                    and buy_now_count <= 0
                )
                unavailable_reason = await detect_buybox_unavailable_reason(page, body)
                if unavailable_reason:
                    result["business_ng"] = True
                    result["ng_reason"] = unavailable_reason
                    result["shipping_status"] = "NG"
                    result["amazon_price"] = fallback_price if fallback_price > 0 else None
                    result["amazon_point"] = fallback_point
                    result["available_qty"] = fallback_qty
                    result["gift_available"] = "ギフト" in fallback_text if fallback_text else None
                elif offer_listing_only and missing_core_purchase_info:
                    result["business_ng"] = True
                    result["system_error"] = False
                    result["ng_reason"] = "BuyBoxなし"
                    result["shipping_status"] = "NG"
                    result["amazon_price"] = None
                    result["amazon_point"] = fallback_point
                    result["available_qty"] = None
                    result["gift_available"] = False
                elif has_purchase_button or fallback_price > 0:
                    result["amazon_price"] = fallback_price if fallback_price > 0 else None
                    result["amazon_point"] = fallback_point
                    result["available_qty"] = fallback_qty
                    result["gift_available"] = "ギフト" in fallback_text if fallback_text else None
                    if availability_has_stock_signal:
                        result["shipping_status"] = availability_text or result["shipping_status"]
                elif result["title"] and fallback_price <= 0 and not has_purchase_button and offer_listing_only:
                    result["business_ng"] = True
                    result["system_error"] = False
                    result["ng_reason"] = "BuyBoxなし"
                    result["shipping_status"] = "NG"
                    result["amazon_price"] = None
                    result["amazon_point"] = fallback_point
                    result["available_qty"] = None
                    result["gift_available"] = False
                else:
                    result["system_error"] = True
                    result["ng_reason"] = "BuyBox取得失敗"
                return result

            in_text = buy_info["in_text"]
            price = int(buy_info["price"] or 0)

            status_error = judge_basic_ng(in_text)
            if status_error:
                result["business_ng"] = True
                result["ng_reason"] = status_error

            qty = parse_available_qty(in_text)
            shipping_status, shipping_message = parse_shipping_status(in_text)

            if shipping_status != "OK":
                result["business_ng"] = True
                result["ng_reason"] = result["ng_reason"] or shipping_message

            point = await parse_point(page)

            alt_price = await get_alt_price_from_buybox(page)
            if alt_price > 0:
                price = alt_price

            if price <= 0:
                result["system_error"] = True
                result["ng_reason"] = result["ng_reason"] or "価格取得失敗"

            result["amazon_price"] = price if price > 0 else None
            result["amazon_point"] = point
            result["available_qty"] = qty
            result["gift_available"] = "ギフト" in in_text
            result["shipping_status"] = shipping_message

            return result

        except Exception as e:
            result["system_error"] = True
            result["ng_reason"] = str(e)
            if not own_page:
                result["page_needs_reset"] = True
            return result

    finally:
        if own_page:
            await close_amazon_page(playwright, browser, context, page)


async def check_amazon_one_v2(
    asin: str,
    page=None,
    page_timeout_ms: int = 60000,
    settle_timeout_ms: int = 1000,
    debug_html: bool = False,
) -> dict[str, Any]:
    asin = asin.strip().upper()

    result = {
        "asin": asin,
        "title": "",
        "amazon_price": None,
        "amazon_point": 0,
        "available_qty": None,
        "gift_available": None,
        "shipping_status": "",
        "business_ng": False,
        "system_error": False,
        "ng_reason": "",
        "checked_at": now_dt(),
        "page_needs_reset": False,
    }

    own_page = page is None
    playwright = None
    browser = None
    context = None

    try:
        if own_page:
            playwright, browser, context, page = await create_amazon_page()

        try:
            url = build_amazon_product_url(asin)
            print(f"amazon_check_start url={url}")

            page_state = None
            body = ""
            buy_info = {"in_text": "", "price": 0}

            for attempt in range(2):
                if attempt > 0:
                    print(f"amazon_retry asin={asin} attempt={attempt + 1} url={url}")

                await page.goto(url, wait_until="domcontentloaded", timeout=page_timeout_ms)
                await page.wait_for_timeout(settle_timeout_ms)
                page_state = await wait_for_meaningful_page_state(
                    page,
                    timeout_ms=min(page_timeout_ms, 5000),
                )
                body = await get_first_text(page, "body")

                if "荳九↓陦ｨ遉ｺ縺輔ｌ縺ｦ縺・ｋ譁・ｭ励ｒ蜈･蜉帙＠縺ｦ縺上□縺輔＞" in body:
                    result["system_error"] = True
                    result["ng_reason"] = "逕ｻ蜒剰ｪ崎ｨｼ"
                    return result

                page_asin = await get_page_asin(page)
                if page_asin:
                    print(f"amazon_page_asin requested={asin} current={page_asin}")
                if page_asin and page_asin != asin:
                    result["system_error"] = True
                    result["ng_reason"] = f"ASIN mismatch current={page_asin}"
                    return result

                buy_info = await read_buybox_info(page)
                visible_price = int(buy_info["price"] or 0)
                if visible_price <= 0:
                    visible_price = await get_alt_price_from_buybox(page)
                if visible_price <= 0:
                    visible_price = await get_price_from_selector(
                        page, "#corePriceDisplay_desktop_feature_div"
                    )

                if (
                    page_state["price_visible"]
                    or visible_price > 0
                    or page_state["explicit_unavailable"]
                    or page_state["explicit_buybox_missing"]
                ):
                    break

            result["title"] = await get_title(page)

            out_of_stock_text = await get_first_text(page, "#outOfStock")
            if out_of_stock_text.strip():
                result["business_ng"] = True
                result["ng_reason"] = "out_of_stock"
                result["shipping_status"] = "NG"
                return result

            if not buy_info["in_text"]:
                selector_diagnostics = await collect_selector_diagnostics(page)
                diagnostics_map = {item["selector"]: item for item in selector_diagnostics}
                print("buybox_diagnostics_start")
                for item in selector_diagnostics:
                    preview = re.sub(r"\s+", " ", item["text"] or "")[:120]
                    print(f"  {item['selector']}: count={item['count']} text={preview}")

                if debug_html:
                    debug_path = await save_debug_html(page, asin)
                    if debug_path is not None:
                        print(f"debug_html saved: {debug_path}")

                availability_text = diagnostics_map.get("#availability", {}).get("text", "")
                merchant_info_text = diagnostics_map.get("#merchant-info", {}).get("text", "")
                buybox_text = diagnostics_map.get("#buybox", {}).get("text", "")
                desktop_buybox_text = diagnostics_map.get("#desktop_buybox", {}).get("text", "")
                add_to_cart_text = diagnostics_map.get("#addToCart", {}).get("text", "")
                add_to_cart_button_text = diagnostics_map.get("#add-to-cart-button", {}).get("text", "")
                add_to_cart_button_count = diagnostics_map.get("#add-to-cart-button", {}).get("count", 0)
                submit_add_to_cart_text = diagnostics_map.get("input[name=\"submit.add-to-cart\"]", {}).get("text", "")
                submit_add_to_cart_count = diagnostics_map.get("input[name=\"submit.add-to-cart\"]", {}).get("count", 0)
                buy_now_count = diagnostics_map.get("#buy-now-button", {}).get("count", 0)

                add_to_cart_is_offer_link = "縺吶∋縺ｦ縺ｮ蜃ｺ蜩√ｒ隕九ｋ" in add_to_cart_text
                has_real_add_to_cart_button = (
                    add_to_cart_button_count > 0
                    and has_actual_purchase_button_text(add_to_cart_button_text)
                ) or (
                    submit_add_to_cart_count > 0
                    and has_actual_purchase_button_text(submit_add_to_cart_text)
                )
                has_purchase_button = buy_now_count > 0 or has_real_add_to_cart_button

                fallback_text = "\n".join(
                    filter(
                        None,
                        [
                            body,
                            out_of_stock_text,
                            availability_text,
                            merchant_info_text,
                            buybox_text,
                            desktop_buybox_text,
                            add_to_cart_text,
                            add_to_cart_button_text,
                            submit_add_to_cart_text,
                        ],
                    )
                )
                fallback_price = int(buy_info["price"] or 0)
                if fallback_price <= 0:
                    fallback_price = await get_alt_price_from_buybox(page)
                if fallback_price <= 0:
                    fallback_price = await get_price_from_selector(
                        page, "#corePriceDisplay_desktop_feature_div"
                    )
                fallback_qty = parse_available_qty(fallback_text)
                fallback_point = await parse_point(page)
                availability_has_stock_signal = bool(availability_text) and not is_generic_availability_text(
                    availability_text
                )
                offer_listing_only = (
                    "縺吶∋縺ｦ縺ｮ蜃ｺ蜩√ｒ隕九ｋ" in buybox_text
                    or "縺吶∋縺ｦ縺ｮ蜃ｺ蜩√ｒ隕九ｋ" in desktop_buybox_text
                    or add_to_cart_is_offer_link
                )
                missing_core_purchase_info = (
                    fallback_price <= 0
                    and not availability_has_stock_signal
                    and not merchant_info_text
                    and buy_now_count <= 0
                )
                unavailable_reason = await detect_buybox_unavailable_reason(page, body)

                if unavailable_reason:
                    result["business_ng"] = True
                    result["ng_reason"] = unavailable_reason
                    result["shipping_status"] = "NG"
                    result["amazon_price"] = fallback_price if fallback_price > 0 else None
                    result["amazon_point"] = fallback_point
                    result["available_qty"] = fallback_qty
                    result["gift_available"] = "繧ｮ繝輔ヨ" in fallback_text if fallback_text else None
                elif (page_state and page_state["explicit_buybox_missing"]) or (
                    offer_listing_only and missing_core_purchase_info
                ):
                    result["business_ng"] = True
                    result["ng_reason"] = "BuyBox??"
                    result["shipping_status"] = "NG"
                    result["amazon_price"] = None
                    result["amazon_point"] = fallback_point
                    result["available_qty"] = None
                    result["gift_available"] = False
                elif has_purchase_button or fallback_price > 0:
                    result["amazon_price"] = fallback_price if fallback_price > 0 else None
                    result["amazon_point"] = fallback_point
                    result["available_qty"] = fallback_qty
                    result["gift_available"] = "繧ｮ繝輔ヨ" in fallback_text if fallback_text else None
                    if availability_has_stock_signal:
                        result["shipping_status"] = availability_text or result["shipping_status"]
                else:
                    result["system_error"] = True
                    result["ng_reason"] = "BuyBox????"
                return result

            in_text = buy_info["in_text"]
            price = int(buy_info["price"] or 0)

            status_error = judge_basic_ng(in_text)
            if status_error:
                result["business_ng"] = True
                result["ng_reason"] = status_error

            qty = parse_available_qty(in_text)
            shipping_status, shipping_message = parse_shipping_status(in_text)

            if shipping_status != "OK":
                result["business_ng"] = True
                result["ng_reason"] = result["ng_reason"] or shipping_message

            point = await parse_point(page)

            alt_price = await get_alt_price_from_buybox(page)
            if alt_price > 0:
                price = alt_price

            if price <= 0:
                unavailable_reason = await detect_buybox_unavailable_reason(page, body)
                if unavailable_reason:
                    result["business_ng"] = True
                    result["ng_reason"] = result["ng_reason"] or unavailable_reason
                elif page_state and page_state["explicit_buybox_missing"]:
                    result["business_ng"] = True
                    result["ng_reason"] = result["ng_reason"] or "BuyBox??"
                else:
                    result["system_error"] = True
                    result["ng_reason"] = result["ng_reason"] or "??????"

            result["amazon_price"] = price if price > 0 else None
            result["amazon_point"] = point
            result["available_qty"] = qty
            result["gift_available"] = "繧ｮ繝輔ヨ" in in_text
            result["shipping_status"] = shipping_message
            return result

        except Exception as e:
            result["system_error"] = True
            result["ng_reason"] = str(e)
            if not own_page:
                result["page_needs_reset"] = True
            return result

    finally:
        if own_page:
            await close_amazon_page(playwright, browser, context, page)


async def detect_page_state_v2(page) -> dict[str, bool]:
    body_text = await get_first_text(page, "body")
    availability_text = await get_first_text(page, "#availability")
    out_of_stock_text = await get_first_text(page, "#outOfStock")
    buybox_text = await get_first_text(page, "#buybox")
    desktop_buybox_text = await get_first_text(page, "#desktop_buybox")
    merchant_info_text = await get_first_text(page, "#merchant-info")
    add_to_cart_text = await get_first_text(page, "#addToCart")
    high_price_warning = await detect_high_price_warning(page, body_text)

    price_visible = False
    for selector in (
        "#corePriceDisplay_desktop_feature_div .a-price-whole",
        "#corePriceDisplay_desktop_feature_div .a-offscreen",
        "#priceToPay .a-price-whole",
        "#priceToPay .a-offscreen",
        ".a-price-whole",
        ".a-offscreen",
    ):
        try:
            loc = page.locator(selector)
            if await loc.count() == 0:
                continue
            text = await safe_inner_text(loc.first)
            if parse_price(text) > 0:
                price_visible = True
                break
        except Exception:
            continue

    text_blob = "\n".join(
        filter(
            None,
            [
                body_text,
                availability_text,
                out_of_stock_text,
                buybox_text,
                desktop_buybox_text,
                merchant_info_text,
                add_to_cart_text,
            ],
        )
    )
    explicit_unavailable = bool(
        out_of_stock_text.strip() or await detect_buybox_unavailable_reason(page, body_text)
    )
    explicit_buybox_missing = "すべての出品を見る" in text_blob

    return {
        "price_visible": price_visible,
        "explicit_unavailable": explicit_unavailable,
        "explicit_buybox_missing": explicit_buybox_missing,
        "high_price_warning": high_price_warning,
    }


async def wait_for_meaningful_page_state_v2(page, timeout_ms: int, poll_ms: int = 250) -> dict[str, bool]:
    deadline = asyncio.get_running_loop().time() + max(timeout_ms, 0) / 1000.0
    last_state = {
        "price_visible": False,
        "explicit_unavailable": False,
        "explicit_buybox_missing": False,
        "high_price_warning": False,
    }

    while True:
        last_state = await detect_page_state_v2(page)
        if (
            last_state["price_visible"]
            or last_state["explicit_unavailable"]
            or last_state["explicit_buybox_missing"]
            or last_state["high_price_warning"]
        ):
            return last_state
        if asyncio.get_running_loop().time() >= deadline:
            return last_state
        await page.wait_for_timeout(poll_ms)


async def check_amazon_one_v3(
    asin: str,
    page=None,
    page_timeout_ms: int = 60000,
    settle_timeout_ms: int = 1000,
    debug_html: bool = False,
) -> dict[str, Any]:
    asin = asin.strip().upper()
    result = {
        "asin": asin,
        "title": "",
        "amazon_price": None,
        "amazon_point": 0,
        "available_qty": None,
        "gift_available": None,
        "shipping_status": "",
        "business_ng": False,
        "system_error": False,
        "ng_reason": "",
        "checked_at": now_dt(),
        "page_needs_reset": False,
    }

    own_page = page is None
    playwright = None
    browser = None
    context = None
    page_asin = ""
    current_url = ""

    try:
        if own_page:
            playwright, browser, context, page = await create_amazon_page()

        try:
            url = build_amazon_product_url(asin)
            print(f"amazon_check_start url={url}")
            body = ""
            page_state = None
            buy_info = {"in_text": "", "price": 0}

            for attempt in range(2):
                if attempt > 0:
                    print(f"amazon_retry asin={asin} attempt={attempt + 1} url={url}")

                await page.goto(url, wait_until="domcontentloaded", timeout=page_timeout_ms)
                await page.wait_for_timeout(settle_timeout_ms)
                page_state = await wait_for_meaningful_page_state_v2(
                    page,
                    timeout_ms=min(page_timeout_ms, 5000),
                )
                body = await get_first_text(page, "body")
                current_url = getattr(page, "url", "")

                if "表示されている文字を入力してください" in body:
                    result["system_error"] = True
                    result["ng_reason"] = "CAPTCHA"
                    log_result_summary(asin, page_asin, current_url, result)
                    return result

                restriction_type, restriction_reason = await detect_black_curtain_restriction(
                    page,
                    current_url,
                    body,
                )
                if restriction_type:
                    result["business_ng"] = True
                    result["system_error"] = False
                    result["ng_reason"] = restriction_reason
                    result["amazon_price"] = None
                    result["available_qty"] = None
                    print(
                        "amazon_restriction "
                        f"requested_asin={asin} "
                        f"current_url={current_url} "
                        f"restriction_type={restriction_type} "
                        f"ng_reason={restriction_reason}"
                    )
                    log_result_summary(asin, page_asin, current_url, result)
                    return result

                if await detect_404_or_region_restriction(page, current_url, body):
                    if attempt == 0:
                        print(
                            "amazon_retry_condition "
                            f"requested_asin={asin} "
                            f"current_url={current_url} "
                            "detected_condition=404_or_region"
                        )
                        continue
                    result["business_ng"] = True
                    result["system_error"] = False
                    result["ng_reason"] = "商品ページなし（404／地域制限）"
                    result["amazon_price"] = None
                    result["available_qty"] = None
                    print(
                        "amazon_restriction "
                        f"requested_asin={asin} "
                        f"current_url={current_url} "
                        "restriction_type=404_or_region "
                        f"ng_reason={result['ng_reason']}"
                    )
                    log_result_summary(asin, page_asin, current_url, result)
                    return result

                page_asin = await get_page_asin(page)
                print(f"amazon_page_context requested_asin={asin} page_asin={page_asin or '-'} current_url={current_url}")

                if page_asin and page_asin != asin:
                    result["business_ng"] = True
                    result["system_error"] = False
                    result["ng_reason"] = "ASIN不一致（別商品へ遷移）"
                    result["amazon_price"] = None
                    result["available_qty"] = None
                    log_result_summary(asin, page_asin, current_url, result)
                    return result

                if page_state["high_price_warning"]:
                    result["business_ng"] = True
                    result["system_error"] = False
                    result["ng_reason"] = "一般的な価格より高い価格"
                    result["amazon_price"] = None
                    result["available_qty"] = None
                    log_result_summary(asin, page_asin, current_url, result)
                    return result

                buy_info = await read_buybox_info(page)
                visible_price = int(buy_info["price"] or 0)
                if visible_price <= 0:
                    visible_price = await get_alt_price_from_buybox(page)
                if visible_price <= 0:
                    visible_price = await get_price_from_selector(page, "#corePriceDisplay_desktop_feature_div")

                if (
                    page_state["price_visible"]
                    or visible_price > 0
                    or page_state["explicit_unavailable"]
                    or page_state["explicit_buybox_missing"]
                ):
                    break

            result["title"] = await get_title(page)

            out_of_stock_text = await get_first_text(page, "#outOfStock")
            if out_of_stock_text.strip():
                result["business_ng"] = True
                result["ng_reason"] = "在庫切れ"
                result["shipping_status"] = "NG"
                log_result_summary(asin, page_asin, current_url, result)
                return result

            used_only, detected_used_price = await detect_used_only_buybox(page, body)
            if used_only:
                result["business_ng"] = True
                result["system_error"] = False
                result["ng_reason"] = "新品BuyBoxなし（中古品のみ）"
                result["amazon_price"] = None
                result["available_qty"] = None
                result["gift_available"] = False
                print(
                    "amazon_restriction "
                    f"requested_asin={asin} "
                    "detected_condition=used "
                    f"detected_used_price={detected_used_price or 0} "
                    f"current_url={current_url} "
                    f"ng_reason={result['ng_reason']}"
                )
                log_result_summary(asin, page_asin, current_url, result)
                return result

            if not buy_info["in_text"]:
                selector_diagnostics = await collect_selector_diagnostics(page)
                diagnostics_map = {item["selector"]: item for item in selector_diagnostics}
                print("buybox_diagnostics_start")
                for item in selector_diagnostics:
                    preview = re.sub(r"\s+", " ", item["text"] or "")[:120]
                    print(f"  {item['selector']}: count={item['count']} text={preview}")

                if debug_html:
                    debug_path = await save_debug_html(page, asin)
                    if debug_path is not None:
                        print(f"debug_html saved: {debug_path}")

                availability_text = diagnostics_map.get("#availability", {}).get("text", "")
                merchant_info_text = diagnostics_map.get("#merchant-info", {}).get("text", "")
                buybox_text = diagnostics_map.get("#buybox", {}).get("text", "")
                desktop_buybox_text = diagnostics_map.get("#desktop_buybox", {}).get("text", "")
                add_to_cart_text = diagnostics_map.get("#addToCart", {}).get("text", "")
                add_to_cart_button_text = diagnostics_map.get("#add-to-cart-button", {}).get("text", "")
                add_to_cart_button_count = diagnostics_map.get("#add-to-cart-button", {}).get("count", 0)
                submit_add_to_cart_text = diagnostics_map.get("input[name=\"submit.add-to-cart\"]", {}).get("text", "")
                submit_add_to_cart_count = diagnostics_map.get("input[name=\"submit.add-to-cart\"]", {}).get("count", 0)
                buy_now_count = diagnostics_map.get("#buy-now-button", {}).get("count", 0)

                add_to_cart_is_offer_link = "すべての出品を見る" in add_to_cart_text
                has_real_add_to_cart_button = (
                    add_to_cart_button_count > 0
                    and has_actual_purchase_button_text(add_to_cart_button_text)
                ) or (
                    submit_add_to_cart_count > 0
                    and has_actual_purchase_button_text(submit_add_to_cart_text)
                )
                has_purchase_button = buy_now_count > 0 or has_real_add_to_cart_button

                fallback_text = "\n".join(
                    filter(
                        None,
                        [
                            body,
                            out_of_stock_text,
                            availability_text,
                            merchant_info_text,
                            buybox_text,
                            desktop_buybox_text,
                            add_to_cart_text,
                            add_to_cart_button_text,
                            submit_add_to_cart_text,
                        ],
                    )
                )
                fallback_price = int(buy_info["price"] or 0)
                if fallback_price <= 0:
                    fallback_price = await get_alt_price_from_buybox(page)
                if fallback_price <= 0:
                    fallback_price = await get_price_from_selector(page, "#corePriceDisplay_desktop_feature_div")
                fallback_qty, minimum_order_quantity = await get_quantity_dropdown_details(page)

                if fallback_qty is None:

                    fallback_qty = parse_available_qty(fallback_text)

                apply_minimum_order_block(result, minimum_order_quantity)
                fallback_point = await parse_point(page)
                availability_has_stock_signal = bool(availability_text) and not is_generic_availability_text(availability_text)
                offer_listing_only = (
                    "すべての出品を見る" in buybox_text
                    or "すべての出品を見る" in desktop_buybox_text
                    or add_to_cart_is_offer_link
                )
                if offer_listing_only:
                    lowest_offer = await read_lowest_amazon_fulfilled_offer(page)
                    if lowest_offer is not None:
                        result["amazon_price"] = lowest_offer["price"]
                        result["amazon_point"] = fallback_point
                        result["available_qty"] = 1
                        apply_minimum_order_block(result, lowest_offer.get("minimum_order_quantity"))
                        result["gift_available"] = True
                        result["shipping_status"] = "Amazon発送最安"
                        return result

                missing_core_purchase_info = (
                    fallback_price <= 0
                    and not availability_has_stock_signal
                    and not merchant_info_text
                    and buy_now_count <= 0
                )
                unavailable_reason = await detect_buybox_unavailable_reason(page, body)

                if await detect_high_price_warning(page, body):
                    result["business_ng"] = True
                    result["ng_reason"] = "一般的な価格より高い価格"
                    result["amazon_price"] = None
                    result["available_qty"] = None
                elif unavailable_reason:
                    result["business_ng"] = True
                    result["ng_reason"] = unavailable_reason
                    result["shipping_status"] = "NG"
                    result["amazon_price"] = fallback_price if fallback_price > 0 else None
                    result["amazon_point"] = fallback_point
                    result["available_qty"] = fallback_qty
                    result["gift_available"] = "郢ｧ・ｮ郢晁ｼ斐Κ" in fallback_text if fallback_text else None
                elif (page_state and page_state["explicit_buybox_missing"]) or (offer_listing_only and missing_core_purchase_info):
                    result["business_ng"] = True
                    result["ng_reason"] = "BuyBoxなし"
                    result["shipping_status"] = "NG"
                    result["amazon_price"] = None
                    result["amazon_point"] = fallback_point
                    result["available_qty"] = None
                    result["gift_available"] = False
                elif has_purchase_button or fallback_price > 0:
                    result["amazon_price"] = fallback_price if fallback_price > 0 else None
                    result["amazon_point"] = fallback_point
                    result["available_qty"] = fallback_qty
                    result["gift_available"] = "郢ｧ・ｮ郢晁ｼ斐Κ" in fallback_text if fallback_text else None
                    if availability_has_stock_signal:
                        result["shipping_status"] = availability_text or result["shipping_status"]
                else:
                    result["system_error"] = True
                    result["ng_reason"] = "BuyBox取得失敗"

                log_result_summary(asin, page_asin, current_url, result)
                return result

            in_text = buy_info["in_text"]
            price = int(buy_info["price"] or 0)

            if not is_explicit_new_offer_text(in_text):
                # A used or condition-unknown Buy Box must never become a
                # price source. AOD remains usable only when it exposes a
                # separately labelled new Amazon-fulfilled offer.
                lowest_offer = await read_lowest_amazon_fulfilled_offer(page)
                if lowest_offer is not None:
                    result["amazon_price"] = lowest_offer["price"]
                    result["amazon_point"] = await parse_point(page)
                    result["available_qty"] = 1
                    apply_minimum_order_block(result, lowest_offer.get("minimum_order_quantity"))
                    result["gift_available"] = True
                    result["shipping_status"] = "Amazon発送（新品・全出品）"
                    result["selected_offer"] = lowest_offer
                    return result
                result["business_ng"] = True
                result["system_error"] = False
                result["ng_reason"] = "新品条件を確認できません"
                result["amazon_price"] = None
                result["available_qty"] = None
                result["gift_available"] = False
                result["shipping_status"] = "NG"
                return result

            status_error = judge_basic_ng(in_text)
            if status_error:
                result["business_ng"] = True
                result["ng_reason"] = status_error

            qty, minimum_order_quantity = await get_quantity_dropdown_details(page, root=page.locator("#buybox"))
            if qty is None:
                qty = parse_available_qty(in_text)
            apply_minimum_order_block(result, minimum_order_quantity)
            shipping_status, shipping_message = parse_shipping_status(in_text)
            if shipping_status != "OK":
                result["business_ng"] = True
                result["ng_reason"] = result["ng_reason"] or shipping_message

            point = await parse_point(page)
            alt_price = await get_alt_price_from_buybox(page)
            if alt_price > 0:
                price = alt_price

            if await detect_high_price_warning(page, body):
                result["business_ng"] = True
                result["system_error"] = False
                result["ng_reason"] = "一般的な価格より高い価格"
                result["amazon_price"] = None
                result["available_qty"] = None
                log_result_summary(asin, page_asin, current_url, result)
                return result

            if price <= 0:
                unavailable_reason = await detect_buybox_unavailable_reason(page, body)
                if unavailable_reason:
                    result["business_ng"] = True
                    result["ng_reason"] = result["ng_reason"] or unavailable_reason
                elif page_state and page_state["explicit_buybox_missing"]:
                    result["business_ng"] = True
                    result["ng_reason"] = result["ng_reason"] or "BuyBoxなし"
                else:
                    result["system_error"] = True
                    result["ng_reason"] = result["ng_reason"] or "価格取得失敗"

            result["amazon_price"] = price if price > 0 else None
            result["amazon_point"] = point
            result["available_qty"] = qty
            result["gift_available"] = "郢ｧ・ｮ郢晁ｼ斐Κ" in in_text
            result["shipping_status"] = shipping_message
            log_result_summary(asin, page_asin, current_url, result)
            return result

        except Exception as e:
            result["system_error"] = True
            result["ng_reason"] = str(e)
            if not own_page:
                result["page_needs_reset"] = True
            log_result_summary(asin, page_asin, current_url, result)
            return result
    finally:
        if own_page:
            await close_amazon_page(playwright, browser, context, page)


check_amazon_one = check_amazon_one_v3


def save_to_db(data: dict[str, Any]) -> None:
    data = dict(data)
    jan_code = re.sub(r"\D", "", str(data.get("jan_code") or data.get("ean") or ""))
    check_total = sum(int(digit) * (3 if position % 2 else 1) for position, digit in enumerate(jan_code[-2::-1], start=1)) if jan_code.isdigit() else -1
    data["jan_code"] = jan_code if len(jan_code) in {8, 12, 13, 14} and (check_total + int(jan_code[-1])) % 10 == 0 else None
    conn = connect_db()

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO amazon_products (
                    asin,
                    title,
                    amazon_price,
                    amazon_point,
                    available_qty,
                    gift_available,
                    shipping_status,
                    business_ng,
                    system_error,
                    ng_reason,
                    jan_code,
                    checked_at,
                    updated_at
                )
                VALUES (
                    %(asin)s,
                    %(title)s,
                    %(amazon_price)s,
                    %(amazon_point)s,
                    %(available_qty)s,
                    %(gift_available)s,
                    %(shipping_status)s,
                    %(business_ng)s,
                    %(system_error)s,
                    %(ng_reason)s,
                    %(jan_code)s,
                    %(checked_at)s,
                    CURRENT_TIMESTAMP
                )
                ON CONFLICT (asin) DO UPDATE SET
                    title = EXCLUDED.title,
                    amazon_price = EXCLUDED.amazon_price,
                    amazon_point = EXCLUDED.amazon_point,
                    available_qty = EXCLUDED.available_qty,
                    gift_available = EXCLUDED.gift_available,
                    shipping_status = EXCLUDED.shipping_status,
                    business_ng = EXCLUDED.business_ng,
                    system_error = EXCLUDED.system_error,
                    ng_reason = EXCLUDED.ng_reason,
                    jan_code = COALESCE(EXCLUDED.jan_code, amazon_products.jan_code),
                    checked_at = EXCLUDED.checked_at,
                    updated_at = CURRENT_TIMESTAMP
                ;
                """,
                data,
            )

        conn.commit()

    finally:
        conn.close()


_save_to_db_without_retry = save_to_db


def save_to_db(data: dict[str, Any]) -> None:

    run_with_db_retry(
        lambda: _save_to_db_without_retry(data),
        description=f"save_to_db asin={data.get('asin')}",
        logger=print,
    )


def _load_shared_amazon_checker():
    """Load the canonical Amazon page checker used by the listing workflow."""
    shared_path = Path(__file__).resolve().parents[2] / "price_system_listing" / "scripts" / "price_check_one_asin_db.py"
    spec = importlib.util.spec_from_file_location("rakuten_shared_amazon_checker", shared_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"shared Amazon checker could not be loaded: {shared_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Amazon page inspection is owned by the listing worktree. Price/stock keeps
# its own DB persistence and target-calculation flow, but uses the same price,
# stock, gift, and Amazon-fulfilled-offer decision as listing.
_shared_amazon_checker = _load_shared_amazon_checker()
check_amazon_one = _shared_amazon_checker.check_amazon_one
create_amazon_page = _shared_amazon_checker.create_amazon_page
close_amazon_page = _shared_amazon_checker.close_amazon_page


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("asin")
    parser.add_argument("--debug-html", action="store_true")
    args = parser.parse_args()

    if not args.asin:
        print("ASINを指定してください。")
        print("例: py price_check_one_asin_db.py B0XXXXXXXX")
        return 2

    asin = args.asin.strip().upper()

    data = await check_amazon_one(asin, debug_html=args.debug_html)

    print("取得結果:")
    for k, v in data.items():
        print(f"{k}: {v}")

    save_to_db(data)

    print("DB保存完了")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
