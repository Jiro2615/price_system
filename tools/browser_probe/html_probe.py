"""HTML feasibility probe, never a production price/stock decision path."""
import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from asin_plan import CONTROLS, from_db
from probe_support import Meter, atomic_json, challenge


def price_number(value):
    # Accessibility labels may begin with a discount percentage, not price.
    match = re.search(r"[￥¥]\s*([\d,]+)", value or "")
    if match:
        return int(match[1].replace(",", ""))
    if re.fullmatch(r"[\d,]+", (value or "").strip()):
        return int(value.strip().replace(",", ""))
    return None


def extract(html, asin):
    soup = BeautifulSoup(html, "html.parser")
    def text(selector):
        element = soup.select_one(selector)
        return element.get_text(" ", strip=True) if element else None
    title = text("#productTitle")
    price = text("#corePriceDisplay_desktop_feature_div .a-price:not(.a-text-price) .a-offscreen")
    if not price:
        price = text("#corePriceDisplay_desktop_feature_div #apex-pricetopay-accessibility-label") or text(
            "#corePriceDisplay_desktop_feature_div .priceToPay .a-price-whole")
    availability = text("#availability")
    stock_match = re.search(r"残り\s*([\d,]+)\s*点", availability or "")
    points = text("#loyalty-points_feature_div") or text("#points_feature_div") or text("#pointsInsideBuyBox_feature_div")
    point_match = re.search(r"([\d,]+)\s*(?:ポイント|pt)", points or "", re.I)
    # No value is fabricated when absent; dropdown limits are not stock.
    values = {
        "title": title, "amazon_price": price_number(price),
        "amazon_point": int(point_match[1].replace(",", "")) if point_match else None,
        "available_qty": int(stock_match[1].replace(",", "")) if stock_match else None,
        "gift_available": None,
    }
    actual = soup.select_one('input#ASIN')
    identity = actual.get("value") if actual else None
    return {"requested_asin": asin, "html_asin": identity,
            "identity_verified": identity == asin, "candidates": values,
            "evidence": {"price": price, "points": points, "availability": availability,
                "merchant": text("#merchant-info"),
                "seller": text("#sellerProfileTriggerId"),
                "ships_from": text("#fulfillerInfoFeature_feature_div"),
                "delivery": text("#deliveryBlockMessage"),
                "destination": text("#glow-ingress-line2"),
                "gift": text("#gift-wrap, #giftOptions, #gift-wrap-message")},
            "requires_shell": True,
            "reason": "Candidate extraction only; offer, destination, and gift eligibility not certified"}


def fetch(session, asin):
    url = f"https://www.amazon.co.jp/dp/{asin}?th=1&psc=1"
    for _ in range(4):
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in {"www.amazon.co.jp", "amazon.co.jp"}:
            raise RuntimeError("Unsafe redirect; stopped")
        if any(part in parsed.path.lower() for part in ("captcha", "/ap/", "/cart", "/buy", "/checkout")):
            raise RuntimeError("Authentication/challenge redirect; stopped without bypass")
        response = session.get(url, timeout=(10, 25), allow_redirects=False)
        if response.status_code in {301, 302, 303, 307, 308}:
            url = urljoin(url, response.headers.get("Location", ""))
            continue
        response.raise_for_status()
        html = response.content.decode(response.encoding or "utf-8", errors="replace")
        has_title = BeautifulSoup(html, "html.parser").select_one("#productTitle") is not None
        if challenge(url, html) or "validateCaptcha" in html or (not has_title and any(
                token in html for token in ("api-services-support@amazon", "ショッピングを続ける", "Continue shopping"))):
            raise RuntimeError("Challenge/confirmation response; stopped without bypass")
        return html, url, len(response.content)
    raise RuntimeError("Too many redirects")


def compare(candidate, baseline):
    if not candidate.get("identity_verified") or not baseline or baseline.get("system_error"):
        return {"status": "not_comparable", "fields": {}}
    fields = {}
    for key, value in candidate["candidates"].items():
        reference = baseline.get(key)
        fields[key] = "unknown" if value is None or reference is None else (
            "candidate_match" if value == reference else "candidate_difference")
    return {"status": "candidate_comparison_only", "fields": fields,
            "conditions_verified": False,
            "note": "Separate anonymous sessions; destination and selected offer equivalence not established"}


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-limit", type=int, default=10)
    parser.add_argument("--hours", type=int, default=6)
    parser.add_argument("--use-stats", action="store_true")
    parser.add_argument("--html-only", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 0 <= args.db_limit <= 100:
        parser.error("db-limit must be between 0 and 100")
    args.output.mkdir(parents=True, exist_ok=False)
    result = {"started_utc": datetime.now(timezone.utc).isoformat(), "cases": [],
              "scope": "No Keepa, no credentials/cookie reuse, no DB writes, no cart or checkout",
              "production_adoption": False, "all_complete": False}
    summary = args.output / "summary.json"
    atomic_json(summary, result)
    try:
        selected = from_db(args.db_limit, args.hours, args.use_stats) if args.db_limit else []
        plan = list(dict.fromkeys(CONTROLS + selected))
        result["plan"] = plan
        meter = Meter()
        meter.start()
        try:
            with requests.Session() as session:
                session.headers["Accept-Language"] = "ja-JP,ja;q=0.9"
                for asin in plan:
                    if (args.output / "STOP").exists():
                        raise RuntimeError("Operator STOP")
                    started = time.monotonic()
                    html, url, size = fetch(session, asin)
                    case = extract(html, asin)
                    case.update(url=url, bytes=size, seconds=round(time.monotonic()-started, 3))
                    result["cases"].append(case)
                    atomic_json(summary, result)
                    print(f"HTML {len(result['cases'])}/{len(plan)} {asin}: identity={case['identity_verified']}", flush=True)
                    # Missing product identity can be an unrecognized confirmation page.
                    if not case["identity_verified"] or not case["candidates"]["title"]:
                        raise RuntimeError("Product identity/title not confirmed; stopped")
                    await asyncio.sleep(1)
        finally:
            result["html_metrics"] = meter.finish()
        if not args.html_only:
            from interaction_probe import run
            baseline_path = args.output / "shell.json"
            await run("shell", baseline_path, plan=plan, case_limit=len(plan))
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            for index, case in enumerate(result["cases"]):
                case["candidates"]["amazon_price"] = price_number(case["evidence"]["price"])
                cases = baseline.get("cases", [])
                reference = cases[index].get("baseline") if index < len(cases) and cases[index].get("asin") == case["requested_asin"] else None
                case["comparison"] = compare(case, reference)
            result["shell_complete"] = len(baseline.get("cases", [])) == len(plan) and not baseline.get("error") and not baseline.get("stopped")
            result["all_complete"] = bool(result["shell_complete"])
        else:
            result["html_complete"] = True
        result["mandatory_controls"] = CONTROLS
        result["fallback_count"] = len(result["cases"])
    except Exception as exc:
        result["error"] = str(exc)
        print("Probe stopped: " + str(exc), flush=True)
    finally:
        atomic_json(summary, result)
        print(str(summary.resolve()), flush=True)
    return int(bool(result.get("error")))


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
