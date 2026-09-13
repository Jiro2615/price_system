"""Read-only live interaction comparison. Separate from all production workers."""
import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import urlparse

from probe_support import ROOT, REPO, ASIN, FIELDS, Meter, no_db, challenge, FatalProbeError, atomic_json
from asin_plan import load_asins, make_plan, wait_turn, from_db

ASINS = [ASIN, "B019SKZXV8", "B0F2HTH5H9"]


async def stop_watcher(owner, paths):
    while True:
        if any(p.exists() for p in paths):
            owner.cancel()
            return
        await asyncio.sleep(0.2)


def child_exit_code(data):
    # Product errors are observations, not a reason to abort the next round.
    return int(bool(data.get("error") or data.get("stopped") or not data.get("cases")))


async def run(mode, out, seconds=900, offer_limit=20, plan=None, sync=None, first="chrome"):
    plan = plan or ASINS
    sys.path.insert(0, str(REPO))
    import scripts.db_config as db
    db.connect_db = no_db
    import psycopg
    psycopg.connect = no_db
    import scripts.price_check_one_asin_db as checker
    checker.connect_db = checker.save_to_db = no_db
    from playwright.async_api import async_playwright
    result = {"mode": mode, "utc": datetime.now(timezone.utc).isoformat(), "asins": list(dict.fromkeys(plan)), "plan": plan, "cases": [],
              "scope": "anonymous; same browser/context reused; navigation, offer panel, purchase-option selection only; no cart/purchase/DB/Keepa/RMS"}
    result["requested_seconds"] = seconds
    deadline = time.monotonic() + seconds
    atomic_json(out, result)
    meter = Meter(out.with_suffix(".resources.json"))
    meter.start()
    stop_paths = [out.parent / "STOP"] + ([sync / "STOP"] if sync else [])
    watcher = asyncio.create_task(stop_watcher(asyncio.current_task(), stop_paths))
    try:
        async with async_playwright() as p:
            options = {"headless": mode == "shell"}
            if mode == "chrome":
                options.update(channel="chrome", args=["--start-minimized", "--no-first-run", "--no-default-browser-check"])
            browser = await p.chromium.launch(**options)
            result["version"] = browser.version
            try:
                ctx = await browser.new_context(viewport={"width": 1280, "height": 900}, locale="ja-JP", service_workers="block")
                blocked = []
                async def guard(route):
                    req = route.request
                    path = urlparse(req.url).path.lower()
                    if req.method not in {"GET", "HEAD", "OPTIONS"} or any(
                        x in path for x in ("/cart/", "add-to-cart", "validatecaptcha", "/checkout", "/buy/", "/hz/wishlist/")):
                        blocked.append({"method": req.method, "path": path})
                        await route.abort()
                    else:
                        await route.continue_()
                await ctx.route("**/*", guard)
                page = await ctx.new_page()
                page.set_default_timeout(3500)
                await page.add_init_script("""window.__probeClicks=[];
                  document.addEventListener('click', e=>{
                    const el=e.target.closest('a,button,input,[role="button"],.a-accordion-row-a11y');
                    if(el)window.__probeClicks.push({tag:el.tagName,id:el.id,
                      text:(el.innerText||el.getAttribute('aria-label')||'').slice(0,150)});
                  },true);""")
                goto = page.goto
                safety_latched = False
                async def check_safety():
                    nonlocal safety_latched
                    body = await page.locator("body").inner_text(timeout=5000)
                    if challenge(page.url, body) or checker.is_amazon_confirmation_page(page.url, body):
                        safety_latched = True
                    if safety_latched:
                        raise FatalProbeError("Challenge/confirmation: stopped; no bypass")
                async def safe_goto(url, **kwargs):
                    if safety_latched:
                        raise FatalProbeError("Challenge previously detected; no further navigation")
                    response = await goto(url, **kwargs)
                    await check_safety()
                    return response
                page.goto = safe_goto
                import itertools
                for case_index, asin in enumerate(itertools.cycle(plan)):
                    if (out.parent / "STOP").exists():
                        result["stopped"] = True
                        break
                    if sync and not await wait_turn(sync, mode, first, case_index):
                        result["stopped"] = (sync / "STOP").exists()
                        break
                    if (not sync or mode == first) and case_index >= len(ASINS) and time.monotonic() >= deadline:
                        break
                    case = {"index": case_index, "asin": asin, "utc": datetime.now(timezone.utc).isoformat()}
                    started = time.monotonic()
                    try:
                        await page.goto("about:blank")
                        data = await asyncio.wait_for(checker.check_amazon_one(asin, page=page, page_timeout_ms=30000), 65)
                        case["baseline"] = {k: data.get(k) for k in FIELDS}
                        await check_safety()
                        if data.get("system_error"):
                            raise RuntimeError("Baseline not valid: " + data.get("ng_reason", ""))
                        case["baseline_clicks"] = await page.evaluate("window.__probeClicks||[]")
                        # A successful production fallback may leave AOD open.
                        # Reload a clean document before testing purchase options.
                        dialogs = page.locator("#all-offers-display[role='dialog']")
                        if any([await dialogs.nth(i).is_visible() for i in range(await dialogs.count())]):
                            await page.goto("about:blank")
                            await page.goto(checker.build_amazon_product_url(asin), wait_until="domcontentloaded", timeout=30000)
                            await page.wait_for_timeout(1000)
                            await checker.select_one_time_purchase(page)
                            case["reset_open_panel"] = True
                        case["purchase_rows"] = await page.locator("[data-a-accordion-row-name]").evaluate_all(
                            "els=>els.map(e=>({name:e.getAttribute('data-a-accordion-row-name'), text:e.innerText.slice(0,180)}))")
                        # Select a visible subscription OPTION only, never its submit button.
                        rows = page.locator("[data-a-accordion-row-name]")
                        changed = False
                        for i in range(await rows.count()):
                            row = rows.nth(i)
                            name = (await row.get_attribute("data-a-accordion-row-name") or "").lower()
                            if "sns" not in name and "subscribe" not in name:
                                continue
                            header = row.locator(".a-accordion-row-a11y").first
                            if await header.count() and await header.is_visible():
                                await header.click(timeout=5000)
                                await page.wait_for_timeout(800)
                                case["subscription_selection"] = {"row": name,
                                    "header_expanded": await header.get_attribute("aria-expanded"),
                                    "radio_class": await header.locator(".a-accordion-radio").first.get_attribute("class")}
                                changed = True
                                break
                        if changed:
                            case["restore_called_changed"] = await checker.select_one_time_purchase(page)
                            active = await checker.get_selected_new_buybox_row(page)
                            case["restored_regular"] = None if active is None else {
                                "row": await active.get_attribute("data-a-accordion-row-name"),
                                "class": await active.get_attribute("class"),
                                "radio_class": await active.locator(".a-accordion-radio").first.get_attribute("class")}
                            buybox = await checker.read_buybox_info(page)
                            case["restored_price"] = buybox["price"]
                        else:
                            case["purchase_toggle"] = "not_present_or_not_visible_not_tested"
                        # Explicitly exercise offer-list opening even when baseline BuyBox is valid.
                        await checker.open_all_offers(page)
                        offers = page.locator("#aod-offer-list #aod-offer")
                        total = page.locator("#aod-total-offer-count").first
                        try:
                            expected = int(await total.get_attribute("value") or "0")
                        except (ValueError, TypeError):
                            expected = 0
                        required = min(expected, offer_limit) if expected > 0 else offer_limit
                        stalled = 0
                        for _ in range(30):
                            before = await offers.count()
                            if before >= required or stalled >= 3:
                                break
                            more = page.locator("#aod-show-more-offers").first
                            if await more.count() and await more.is_visible():
                                await more.click()
                            else:
                                scroller = page.locator("#all-offers-display-scroller").first
                                if not await scroller.count() or not await scroller.is_visible():
                                    break
                                await scroller.evaluate("e => {e.scrollTop=e.scrollHeight; e.dispatchEvent(new Event('scroll', {bubbles:true}));}")
                            await page.wait_for_timeout(1000)
                            stalled = stalled + 1 if await offers.count() <= before else 0
                        case["advertised_offer_count"] = expected or None
                        case["required_offer_count"] = required
                        case["offer_count"] = await offers.count()
                        case["required_offers_loaded"] = case["offer_count"] >= required
                        case["count_known"] = expected > 0
                        case["offers"] = []
                        for i in range(min(await offers.count(), offer_limit)):
                            offer = offers.nth(i)
                            async def text(selector):
                                loc = offer.locator(selector).first
                                return (await loc.inner_text(timeout=2000)) if await loc.count() else ""
                            case["offers"].append({"price": await text("#aod-offer-price"),
                                "ships_from": await text("#aod-offer-shipsFrom"),
                                "seller": await text("#aod-offer-soldBy"),
                                "delivery": await text("[data-csa-c-delivery-price]"),
                                "condition": await text("#aod-offer-heading")})
                        panels = page.locator("#all-offers-display")
                        case["offer_panel_visible"] = any([await panels.nth(i).is_visible() for i in range(await panels.count())])
                        case["clicks"] = await page.evaluate("window.__probeClicks||[]")
                        if case_index < len(ASINS):
                            await page.screenshot(path=str(out.parent / f"{out.stem}_{asin}.png"), full_page=False)
                        # Return to product and rerun same parser after interactions. Reuses browser.
                        data2 = await asyncio.wait_for(checker.check_amazon_one(asin, page=page, page_timeout_ms=30000), 65)
                        case["after_navigation"] = {k: data2.get(k) for k in FIELDS}
                        await check_safety()
                        case["same_after_navigation"] = case["baseline"] == case["after_navigation"]
                    except asyncio.CancelledError:
                        case["error"] = "Explicit stop requested during product"
                        case["fatal"] = True
                        result["cases"].append(case)
                        raise
                    except Exception as exc:
                        case["error"] = f"{type(exc).__name__}: {exc}"
                        # Detect challenges even when the production parser caught
                        # the exception or an interaction navigated without goto.
                        try:
                            await check_safety()
                        except FatalProbeError:
                            safety_latched = True
                        except Exception:
                            pass
                        case["fatal"] = isinstance(exc, FatalProbeError) or safety_latched or not browser.is_connected() or page.is_closed()
                    case["elapsed_seconds"] = round(time.monotonic()-started, 3)
                    case["sample_private_working_set_mib"] = round(meter.rows[-1][4]/2**20, 1)
                    result["cases"].append(case)
                    atomic_json(out, result)
                    if case.get("fatal"):
                        result["error"] = "Stopped on safety boundary or closed browser"
                        if sync:
                            (sync / "STOP").touch()
                        break
                    if sync:
                        (sync / f"{mode}_{case_index}.done").touch()
                    print(mode, asin, "offers", case.get("offer_count"), "toggle", case.get("restore_called_changed"), "error", case.get("error"), flush=True)
                    await asyncio.sleep(10)
                result["blocked_request_count"] = len(blocked)
            finally:
                await browser.close()
    except asyncio.CancelledError:
        result["stopped"] = True
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        watcher.cancel()
        result["metrics"] = meter.finish()
        result["resource_samples"] = meter.resource_samples()
        atomic_json(out, result)
        if sync:
            (sync / f"{mode}.finished").touch()


def stop_tree(process):
    import psutil
    try:
        root = psutil.Process(process.pid)
        children = root.children(recursive=True)
    except psutil.Error:
        return
    for proc in list(reversed(children)) + [root]:
        try: proc.terminate()
        except psutil.Error: pass
    _, alive = psutil.wait_procs(children + [root], timeout=5)
    for proc in alive:
        try: proc.kill()
        except psutil.Error: pass


def main():
    parser = argparse.ArgumentParser(description="Read-only browser comparison; no production writes")
    parser.add_argument("--mode", choices=["chrome", "shell"])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--seconds", type=int, default=900)
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--offer-limit", type=int, default=20)
    parser.add_argument("--asin-file", type=Path)
    parser.add_argument("--db-limit", type=int, default=100)
    parser.add_argument("--hours", type=int, default=6)
    parser.add_argument("--use-stats", action="store_true")
    parser.add_argument("--smoke", action="store_true", help="Explicit fixed-three-product smoke test")
    parser.add_argument("--sync", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--first", choices=["chrome", "shell"], default="chrome", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.asin_file and args.smoke:
        parser.error("Choose --asin-file or --smoke, not both")
    if not 1 <= args.db_limit <= 1000 or not 0 <= args.hours <= 8760:
        parser.error("db-limit 1..1000; hours 0..8760")
    try:
        selected = ASINS if args.smoke else load_asins(args.asin_file) if args.asin_file else from_db(args.db_limit, args.hours, args.use_stats)
        plan = make_plan(selected)
    except Exception as exc:
        # Connection exceptions may contain connection details. Keep console generic.
        parser.error("ASIN selection failed (" + type(exc).__name__ + "). Check DB configuration / due targets or input file. No fallback.")
    if not 1 <= args.seconds <= 14400 or not 1 <= args.rounds <= 10 or not 1 <= args.offer_limit <= 100:
        parser.error("seconds 1..14400, rounds 1..10, offer-limit 1..100")
    if args.mode:
        if not args.output: parser.error("--output required")
        asyncio.run(run(args.mode, args.output, args.seconds, args.offer_limit, plan, args.sync, args.first))
        data = json.loads(args.output.read_text(encoding="utf-8"))
        return child_exit_code(data)
    import platform
    import psutil
    import importlib.metadata
    out = REPO / "output" / ("browser_probe_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
    out.mkdir(parents=True)
    manifest = {"platform": platform.platform(), "logical_cpus": psutil.cpu_count(),
                "ram_gib": round(psutil.virtual_memory().total / 2**30, 2),
                "python": sys.version, "arguments": vars(args),
                "playwright": importlib.metadata.version("playwright"),
                "psutil": importlib.metadata.version("psutil")}
    try:
        manifest["git_revision"] = subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        manifest["git_revision"] = None
    (out / "machine.json").write_text(json.dumps(manifest, default=str, indent=2), encoding="utf-8")
    print("Output:", out, "\\nStop: Ctrl+C or create STOP file in that folder.", flush=True)
    # Snapshot once; both children read exactly the same list, never the DB.
    snapshot = out / "asins.txt"
    snapshot.write_text("\n".join(selected) + "\n", encoding="utf-8")
    manifest["selection"] = {"source": "smoke" if args.smoke else "file" if args.asin_file else "DB",
                             "unique_asins": list(dict.fromkeys(plan)), "plan": plan,
                             "paired": True}
    (out / "machine.json").write_text(json.dumps(manifest, default=str, indent=2), encoding="utf-8")
    from contextlib import ExitStack
    for repetition in range(args.rounds):
        first = "chrome" if repetition % 2 == 0 else "shell"
        sync = out / f"round{repetition+1}_sync"
        sync.mkdir()
        processes = []
        with ExitStack() as stack:
            try:
                for mode in [first, "shell" if first == "chrome" else "chrome"]:
                    name = f"round{repetition+1}_{mode}"
                    log = stack.enter_context((out / (name + ".log")).open("w", encoding="utf-8"))
                    process = subprocess.Popen([sys.executable, __file__, "--mode", mode,
                        "--output", str(out / (name + ".json")), "--seconds", str(args.seconds),
                        "--offer-limit", str(args.offer_limit), "--asin-file", str(snapshot),
                        "--sync", str(sync), "--first", first], stdout=log, stderr=subprocess.STDOUT,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    processes.append(process)
                timeout = time.monotonic() + args.seconds + 600
                while any(p.poll() is None for p in processes):
                    if (out / "STOP").exists() or any(p.poll() not in (None, 0) for p in processes):
                        raise RuntimeError("Stopped or incomplete paired test")
                    if time.monotonic() >= timeout:
                        raise TimeoutError("Paired test timeout")
                    time.sleep(0.2)
                if any(p.returncode for p in processes):
                    raise RuntimeError("Incomplete paired test")
            except (KeyboardInterrupt, RuntimeError, TimeoutError, OSError):
                (sync / "STOP").touch()
                # Give both children time to close and flush their final metrics.
                grace = time.monotonic() + 20
                while any(p.poll() is None for p in processes) and time.monotonic() < grace:
                    time.sleep(0.2)
                for process in processes:
                    if process.poll() is None:
                        stop_tree(process)
                from summarize import summarize
                summarize(out)
                print("Stopped; partial results saved:", out, flush=True)
                return 1
        print("Paired round", repetition + 1, "finished", flush=True)
    from summarize import summarize
    summarize(out)
    print("Complete. Results:", out, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
