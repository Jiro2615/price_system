import argparse
import asyncio
import builtins
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from playwright.async_api import async_playwright

try:
    from scripts.db_config import connect_db
except ModuleNotFoundError:
    from db_config import connect_db


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
    """Read the price following a yen mark, never a discount percentage.

    Amazon's AOD accessibility label can be rendered as, for example,
    ``6パーセントの割引で￥2,500``.  The generic parser would select the
    leading ``6``.  In AOD we require an explicit yen mark and use its last
    amount, which is the price-to-pay when the label includes a promotion.
    """
    matches = re.findall(r"[￥¥]\s*([0-9][0-9,]*)", str(text or ""))
    if not matches:
        return 0
    try:
        return int(matches[-1].replace(",", ""))
    except ValueError:
        return 0


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


def judge_basic_ng(in_text: str, page_text: str = "") -> str:
    if "在庫切れ" in in_text:
        return "在庫切れ"
    if is_amazon_delivery_origin_offer_text(in_text):
        return "配送元Amazonは対象外（出荷元Amazonのみ採用）"
    if "ギフト" not in in_text and not is_amazon_official_offer_text(in_text) and not is_amazon_official_offer_text(page_text):
        return "ギフト不可（Amazon.co.jp直販例外の未確認: 出荷元・販売元 Amazon.co.jp）"
    return ""


def is_amazon_official_offer_text(in_text: str) -> bool:
    normalized = re.sub(r"\s+", "", in_text or "")
    direct_amazon = bool(re.search(r"出荷元\s*/\s*販売元\s*Amazon\.co\.jp", normalized, re.I))
    separate_amazon = bool(re.search(r"出荷元\s*Amazon\.co\.jp", normalized, re.I)) and bool(
        re.search(r"販売元\s*Amazon\.co\.jp", normalized, re.I)
    )
    return direct_amazon or separate_amazon


def is_amazon_fulfilled_offer_text(in_text: str) -> bool:
    """Return whether Amazon, rather than the seller, will ship the offer."""
    if is_amazon_official_offer_text(in_text):
        return True
    normalized = re.sub(r"\s+", "", in_text or "")
    return bool(re.search(r"出荷元\s*Amazon(?:\.co\.jp)?", normalized, re.I))


def is_amazon_delivery_origin_offer_text(in_text: str) -> bool:
    """Reject BuyBox labels that are not the explicit ``出荷元`` field."""
    normalized = re.sub(r"\s+", "", in_text or "")
    return bool(re.search(r"(?:配送元|発送元)[\s:：]*Amazon(?:\.co\.jp)?", normalized, re.I))


_NON_NEW_CONDITION_MARKERS = ("中古", "整備済み", "再生品", "アウトレット", "展示品", "コレクター")
_OFFER_CONDITION_PATTERN = re.compile(
    r"新品同様|中古|整備済み|再生品|アウトレット|展示品|コレクター|新品"
)


def is_explicit_new_offer_text(in_text: str) -> bool:
    """Accept an Amazon offer only when its condition is explicitly ``新品``.

    Do not infer ``新品`` from the absence of a used label.  Offer cards can
    contain seller descriptions such as ``新品同様``; the token boundary keeps
    that text from being mistaken for Amazon's actual condition label.
    """
    normalized = re.sub(r"\s+", " ", str(in_text or "")).strip()
    # BuyBox text can include a separate used-offer teaser after the primary
    # purchase block.  Judge the first displayed condition only: a trailing
    # ``中古`` must not invalidate a BuyBox that begins with ``新品``.
    match = _OFFER_CONDITION_PATTERN.search(normalized)
    return bool(match and match.group(0) == "新品")


def is_eligible_buybox_condition_text(in_text: str) -> bool:
    """Allow an unmarked standard Amazon.co.jp BuyBox but never a used one.

    Amazon's standard direct-sale template can show ``出荷元 / 販売元`` followed
    by ``Amazon.co.jp`` without a visible ``新品`` condition label.  This form is
    accepted only when the primary BuyBox has no non-new marker; unlabelled
    third-party offers remain ineligible.
    """
    primary_text = re.split(r"Amazonの他の出品者|すべての出品", str(in_text or ""), maxsplit=1)[0]
    if is_explicit_new_offer_text(primary_text):
        return True
    if any(marker in primary_text for marker in _NON_NEW_CONDITION_MARKERS):
        return False
    return is_amazon_official_offer_text(primary_text)


def is_gift_or_amazon_official(in_text: str, page_text: str = "") -> bool:
    if is_amazon_delivery_origin_offer_text(in_text):
        return False
    return "ギフト" in (in_text or "") or is_amazon_official_offer_text(in_text) or is_amazon_official_offer_text(page_text)


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
    """Return Amazon's maximum quantity and any explicit minimum order quantity."""
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


def max_quantity_from_dropdown_options(values: list[str]) -> Optional[int]:
    """Compatibility helper for callers with only numeric option values."""
    maximum, _ = quantity_dropdown_details([(value, value) for value in values])
    return maximum


async def get_quantity_dropdown_details(page, root=None) -> tuple[Optional[int], Optional[int]]:
    """Read quantity constraints without changing Amazon's selected value."""
    roots = [root] if root is not None else []
    roots.append(page)
    selectors = (
        "#quantity select",
        "#quantityRelocateFeature select",
        "select[name='quantity']",
        "select#quantity",
    )

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


async def has_used_only_buybox(page) -> bool:
    """Return whether the visible purchase box is a used-item BuyBox.

    Recent Amazon product pages can render a used BuyBox outside the
    ``.a-box-group`` structure.  In that layout ``read_buybox_info`` has no
    primary group, while the generic core-price selector still exposes the
    used price.  That price must never be used as a new-item sourcing price.
    """
    used_text = "\n".join(
        filter(
            None,
            [
                await get_first_text(page, "#usedBuySection"),
                await get_first_text(page, "#usedbuyBox"),
            ],
        )
    )
    if "中古" in used_text:
        return True

    buybox_text = "\n".join(
        filter(
            None,
            [
                await get_first_text(page, "#buybox"),
                await get_first_text(page, "#desktop_buybox"),
            ],
        )
    )
    return "中古商品" in buybox_text and not is_explicit_new_offer_text(buybox_text)


def delivery_within_one_week(text: str) -> bool:
    """Return whether Amazon's displayed delivery promise is no later than 7 days."""
    normalized = re.sub(r"\s+", "", text or "")
    if any(word in normalized for word in ("本日", "今日", "明日", "翌日")):
        return True

    match = re.search(r"(\d{1,2})月(\d{1,2})日", normalized)
    if not match:
        return False

    diff_days = calc_diff_days(int(match.group(1)), int(match.group(2)))
    return diff_days is not None and 0 <= diff_days <= 7


async def open_all_offers(page) -> None:
    """Open Amazon's all-offers panel and load its currently available pages."""
    ingress = page.locator("#aod-ingress-link")
    if await ingress.count() == 0:
        # Products without a BuyBox use a normal offer-listing link instead
        # of the dynamic AOD ingress.  It redirects to the same AOD layout.
        ingress = page.locator("a[href*='/gp/offer-listing/']").first
    if await ingress.count() == 0:
        return

    try:
        await ingress.first.click(timeout=5000)
        offers = page.locator("#aod-offer-list #aod-offer")
        await offers.first.wait_for(state="visible", timeout=10000)
    except Exception:
        return

    # The first panel may not contain every seller.  Load a bounded number of
    # follow-up pages so a hidden late offer is not silently ignored.
    for _ in range(10):
        more = page.locator("#aod-show-more-offers")
        try:
            if await more.count() == 0 or not await more.first.is_visible(timeout=500):
                break
            before = await offers.count()
            await more.first.click(timeout=5000)
            await page.wait_for_timeout(700)
            if await offers.count() <= before:
                break
        except Exception:
            break


async def read_lowest_amazon_fulfilled_offer(page, quantity: int = 1) -> Optional[dict[str, Any]]:
    """Find the lowest-priced AOD offer Amazon can ship free within one week.

    The offer panel is used because the BuyBox can be a merchant-fulfilled
    seller even though an orderable Amazon-fulfilled offer exists below it.
    """
    await open_all_offers(page)
    offers = page.locator("#aod-offer-list #aod-offer")
    candidates: list[dict[str, Any]] = []

    for position in range(await offers.count()):
        offer = offers.nth(position)
        try:
            ships_from = re.sub(r"\s+", " ", await safe_inner_text(offer.locator("#aod-offer-shipsFrom").first)).strip()
            if is_amazon_delivery_origin_offer_text(ships_from) or not re.match(r"^出荷元\s*", ships_from):
                continue
            ships_from = re.sub(r"^出荷元\s*", "", ships_from)
            if ships_from not in {"Amazon", "Amazon.co.jp"}:
                continue

            # Prefer the dedicated visible price-to-pay element.  Its
            # accessibility label may begin with a discount percentage, e.g.
            # "6パーセントの割引で￥2,500", so it must be parsed by yen mark
            # rather than by its first number.
            price = parse_price(await safe_inner_text(offer.locator(".apex-pricetopay-value .a-price-whole").first))
            if price <= 0:
                price = parse_yen_price(
                    await safe_inner_text(offer.locator(".apex-pricetopay-accessibility-label").first)
                )
            if price <= 0:
                price = parse_yen_price(await safe_inner_text(offer.locator("#aod-offer-price").first))
            delivery_node = offer.locator("[data-csa-c-delivery-price]").first
            delivery_price = await delivery_node.get_attribute("data-csa-c-delivery-price") if await delivery_node.count() else ""
            delivery_time = await delivery_node.get_attribute("data-csa-c-delivery-time") if await delivery_node.count() else ""
            offer_text = await safe_inner_text(offer)
            if (
                not is_explicit_new_offer_text(offer_text)
                or price <= 0
                or delivery_price != "無料"
                or not delivery_within_one_week(delivery_time or offer_text)
            ):
                continue

            add_button = offer.locator("input[name='submit.addToCart']").first
            if await add_button.count() == 0:
                continue
            action = await add_button.locator("xpath=ancestor::*[@data-aod-atc-action][1]").get_attribute("data-aod-atc-action")
            index_match = re.search(r'"offerIndex"\s*:\s*(\d+)', action or "")
            max_qty_match = re.search(r'"maxQty"\s*:\s*(\d+)', action or "")
            max_qty = int(max_qty_match.group(1)) if max_qty_match else 1
            minimum_order_quantity = minimum_order_quantity_from_offer_text(offer_text, action)
            if max_qty < quantity:
                continue

            seller = re.sub(r"\s+", " ", await safe_inner_text(offer.locator("#aod-offer-soldBy").first)).strip()
            candidates.append({
                "price": price,
                "offer_index": int(index_match.group(1)) if index_match else position,
                "max_qty": max_qty,
                "minimum_order_quantity": minimum_order_quantity,
                "ships_from": ships_from,
                "seller": re.sub(r"^販売元\s*", "", seller),
                "delivery": delivery_time or offer_text,
            })
        except Exception:
            continue

    return min(candidates, key=lambda item: item["price"]) if candidates else None


async def create_amazon_page(*, start_minimized: bool = False) -> tuple[Any, Any, Any, Any]:
    playwright = await async_playwright().start()
    launch_args = [
        "--disable-blink-features=AutomationControlled",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    if start_minimized:
        launch_args.append("--start-minimized")
    browser = await playwright.chromium.launch(
        channel="chrome",
        headless=False,
        args=launch_args,
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
        "minimum_order_quantity": None,
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
            if "この商品の再入荷予定は立っておりません" in out_of_stock_text:
                result["business_ng"] = True
                result["ng_reason"] = "再入荷予定なし"
                result["shipping_status"] = "NG"
                return result

            buy_info = await read_buybox_info(page)

            if not buy_info["in_text"]:
                # A product page can omit the BuyBox entirely while still
                # exposing an orderable Amazon-fulfilled offer in AOD.  Check
                # that panel before classifying this as a BuyBox fetch error.
                lowest_offer = await read_lowest_amazon_fulfilled_offer(page)
                if lowest_offer is not None:
                    result["amazon_price"] = lowest_offer["price"]
                    result["amazon_point"] = await parse_point(page)
                    result["available_qty"] = lowest_offer["max_qty"]
                    apply_minimum_order_block(result, lowest_offer.get("minimum_order_quantity"))
                    result["gift_available"] = True
                    result["shipping_status"] = f"Amazon発送最安: {lowest_offer['delivery']}"
                    result["selected_offer"] = lowest_offer
                    return result

                # ``#corePriceDisplay_desktop_feature_div`` is also present
                # for a used-only BuyBox.  Do this after the AOD lookup so a
                # separately labelled new Amazon-fulfilled offer can still be
                # selected, but before any generic price fallback runs.
                if await has_used_only_buybox(page):
                    result["business_ng"] = True
                    result["system_error"] = False
                    result["ng_reason"] = "新品BuyBoxなし（中古品のみ）"
                    result["shipping_status"] = "NG"
                    result["amazon_price"] = None
                    result["amazon_point"] = await parse_point(page)
                    result["available_qty"] = None
                    result["gift_available"] = False
                    return result

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
                buy_now_count = diagnostics_map.get("#buy-now-button", {}).get(
                    "count", 0
                )
                add_to_cart_is_offer_link = "すべての出品を見る" in add_to_cart_text
                has_purchase_button = buy_now_count > 0 or (
                    add_to_cart_count > 0 and not add_to_cart_is_offer_link
                )
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
                fallback_qty, minimum_order_quantity = await get_quantity_dropdown_details(page)
                if fallback_qty is None:
                    fallback_qty = parse_available_qty(fallback_text)
                apply_minimum_order_block(result, minimum_order_quantity)
                fallback_point = await parse_point(page)
                offer_listing_only = (
                    "すべての出品を見る" in buybox_text
                    or "すべての出品を見る" in desktop_buybox_text
                    or add_to_cart_is_offer_link
                )
                missing_core_purchase_info = (
                    fallback_price <= 0
                    and not availability_text
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
                    result["gift_available"] = is_gift_or_amazon_official(fallback_text) if fallback_text else None
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
                    result["gift_available"] = is_gift_or_amazon_official(fallback_text) if fallback_text else None
                    result["shipping_status"] = availability_text or result["shipping_status"]
                else:
                    result["system_error"] = True
                    result["ng_reason"] = "BuyBox取得失敗"
                return result

            in_text = buy_info["in_text"]
            price = int(buy_info["price"] or 0)

            # A merchant-fulfilled or non-gift BuyBox can hide a valid FBA
            # offer.  Only inspect the all-offers panel in that case; keep a
            # valid Amazon-fulfilled BuyBox as-is.
            needs_offer_fallback = (
                not is_eligible_buybox_condition_text(in_text)
                or "ギフト" not in in_text
                or not is_amazon_fulfilled_offer_text(in_text)
            )
            if needs_offer_fallback:
                lowest_offer = await read_lowest_amazon_fulfilled_offer(page)
                if lowest_offer is not None:
                    result["amazon_price"] = lowest_offer["price"]
                    result["amazon_point"] = await parse_point(page)
                    result["available_qty"] = lowest_offer["max_qty"]
                    apply_minimum_order_block(result, lowest_offer.get("minimum_order_quantity"))
                    # Amazon fulfillment is the approved fallback condition.
                    # gift_available is the existing downstream eligibility
                    # flag, not a literal assertion that the offer card shows
                    # the word "ギフト".
                    result["gift_available"] = True
                    result["shipping_status"] = f"Amazon発送最安: {lowest_offer['delivery']}"
                    result["selected_offer"] = lowest_offer
                    return result

            status_error = judge_basic_ng(in_text, body)
            if not is_eligible_buybox_condition_text(in_text):
                status_error = status_error or "新品条件を確認できません"
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

            if price <= 0:
                result["system_error"] = True
                result["ng_reason"] = result["ng_reason"] or "価格取得失敗"

            result["amazon_price"] = price if price > 0 else None
            result["amazon_point"] = point
            result["available_qty"] = qty
            result["gift_available"] = is_gift_or_amazon_official(in_text, body)
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


def save_to_db(data: dict[str, Any]) -> None:
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
                    checked_at = EXCLUDED.checked_at,
                    updated_at = CURRENT_TIMESTAMP
                ;
                """,
                data,
            )

        conn.commit()

    finally:
        conn.close()


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
