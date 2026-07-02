import asyncio
import re
import sys
from datetime import date, datetime
from typing import Any, Optional

from playwright.async_api import async_playwright

from db_config import connect_db


def now_dt() -> datetime:
    return datetime.now()


def parse_price(text: str) -> int:
    s = str(text or "")
    s = s.replace("￥", "").replace("\\", "").replace(",", "").replace("円", "").replace("税込", "")
    s = re.sub(r"\s+", "", s)
    m = re.search(r"\d+(?:\.\d+)?", s)
    return int(float(m.group(0))) if m else 0


def extract_asin(url: str) -> str:
    m = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", url, re.I)
    return m.group(1).upper() if m else ""


def calc_diff_days(month_num: int, day_num: int) -> int:
    today = date.today()
    target = date(today.year, month_num, day_num)
    if target < today:
        target = date(today.year + 1, month_num, day_num)
    return (target - today).days


def judge_basic_ng(in_text: str) -> str:
    if "最小注文個数" in in_text:
        return "複数注文"
    if "ギフト" not in in_text:
        return "ギフトなし"
    if "配送料 \\" in in_text or "配送料 ￥" in in_text:
        return "配送料あり"
    if "一時的に在庫切れ" in in_text:
        return "一時的に在庫切れ"
    return ""


def parse_available_qty(in_text: str) -> int:
    m = re.search(r"残り\s*(\d+)\s*点", in_text)
    if m:
        return min(4, int(m.group(1)))
    return 4


def parse_shipping_status(in_text: str) -> tuple[str, str]:
    text = re.sub(r"\s+", "", in_text or "")

    if "か月以内に発送します" in text:
        return "NG", "発送遅い"

    if re.search(r"(本日中?|今日|明日|翌日|明後日).{0,30}(お届け|配送|配達|到着)", text):
        return "OK", "発送OK"

    if re.search(r"(お届け|配送|配達|到着).{0,30}(本日中?|今日|明日|翌日|明後日)", text):
        return "OK", "発送OK"

    send_week: Optional[int] = None
    diff_days: Optional[int] = None

    m = re.search(r"(\d+)週間以内に発送します", text)
    if m:
        send_week = int(m.group(1))

    date_match = re.search(r"([0-9]{1,2})月([0-9]{1,2})日", text)
    if date_match:
        diff_days = calc_diff_days(int(date_match.group(1)), int(date_match.group(2)))

    if send_week == 1:
        return "OK", "発送OK"

    if diff_days is not None and 0 <= diff_days < 7:
        return "OK", "発送OK"

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


async def check_amazon_one(asin: str, page=None) -> dict[str, Any]:
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
            url = f"https://www.amazon.co.jp/dp/{asin}"
            print(f"Amazon確認開始: {url}")

            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(1000)

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
                result["system_error"] = True
                result["ng_reason"] = "BuyBoxなし"
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
    if len(sys.argv) < 2:
        print("ASINを指定してください。")
        print("例: py price_check_one_asin_db.py B0XXXXXXXX")
        return 2

    asin = sys.argv[1].strip().upper()

    data = await check_amazon_one(asin)

    print("取得結果:")
    for k, v in data.items():
        print(f"{k}: {v}")

    save_to_db(data)

    print("DB保存完了")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
