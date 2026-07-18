from __future__ import annotations

import argparse
import asyncio
import builtins
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

if __package__ in (None, ""):
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

from playwright.async_api import BrowserContext, Page, Playwright, async_playwright


DEFAULT_START_URL = "https://webservice.rms.rakuten.co.jp/merchant-portal/backToMenu"
DEFAULT_OUTPUT_ROOT = Path("output") / "rms_webservice"
DEFAULT_PROFILE_DIR = DEFAULT_OUTPUT_ROOT / "chrome_profile"

COMMON_CHROME_PATHS = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "Application" / "chrome.exe",
]


def configure_output() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None or not hasattr(stream, "reconfigure"):
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def safe_print(*args: object, **kwargs: object) -> None:
    try:
        builtins.print(*args, **kwargs)
    except UnicodeEncodeError:
        sep = kwargs.get("sep", " ")
        end = kwargs.get("end", "\n")
        file = kwargs.get("file", sys.stdout)
        flush = kwargs.get("flush", False)
        text = str(sep).join(str(arg) for arg in args)
        encoding = getattr(file, "encoding", None) or "utf-8"
        safe_text = text.encode(encoding, errors="replace").decode(encoding, errors="replace")
        builtins.print(safe_text, end=end, file=file, flush=flush)


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def slugify(value: str) -> str:
    normalized = re.sub(r"\s+", "_", str(value or "").strip())
    normalized = re.sub(r"[\\/:*?\"<>|]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("._")
    return normalized or "page"


def resolve_output_dir(output_root: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return output_root / timestamp


def find_local_chrome_path() -> Path | None:
    for candidate in COMMON_CHROME_PATHS:
        if candidate.exists():
            return candidate
    return None


async def launch_logged_in_chrome(
    playwright: Playwright,
    *,
    profile_dir: Path,
    start_url: str,
    chrome_path: Path | None,
) -> tuple[BrowserContext, Page, dict[str, Any]]:
    profile_dir.mkdir(parents=True, exist_ok=True)
    launch_meta: dict[str, Any] = {
        "profile_dir": str(profile_dir),
        "launch_mode": None,
        "chrome_path": str(chrome_path) if chrome_path else None,
    }

    common_kwargs = {
        "headless": False,
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check",
        ],
        "viewport": {"width": 1440, "height": 960},
        "locale": "ja-JP",
    }

    last_error: Exception | None = None
    context: BrowserContext | None = None

    if chrome_path is not None:
        try:
            context = await playwright.chromium.launch_persistent_context(
                str(profile_dir),
                executable_path=str(chrome_path),
                **common_kwargs,
            )
            launch_meta["launch_mode"] = "executable_path"
        except Exception as exc:
            last_error = exc

    if context is None:
        try:
            context = await playwright.chromium.launch_persistent_context(
                str(profile_dir),
                channel="chrome",
                **common_kwargs,
            )
            launch_meta["launch_mode"] = "channel"
        except Exception as exc:
            last_error = exc

    if context is None:
        detected = find_local_chrome_path()
        if detected is not None and (chrome_path is None or detected != chrome_path):
            context = await playwright.chromium.launch_persistent_context(
                str(profile_dir),
                executable_path=str(detected),
                **common_kwargs,
            )
            launch_meta["launch_mode"] = "detected_executable_path"
            launch_meta["chrome_path"] = str(detected)

    if context is None:
        raise RuntimeError(f"Chrome launch failed: {last_error}")

    page = context.pages[0] if context.pages else await context.new_page()
    await page.goto(start_url, wait_until="domcontentloaded")
    return context, page, launch_meta


async def prompt_after_manual_login(page: Page, *, start_url: str) -> None:
    safe_print("")
    safe_print("Chrome を起動しました。")
    safe_print("1. 画面で RMS WEB SERVICE にログインしてください")
    safe_print(f"2. 次のページまで移動してください: {start_url}")
    safe_print("3. 準備できたら、このターミナルに戻って Enter を押してください")
    safe_print("")
    await asyncio.to_thread(input, "Enter を押すと保存巡回を開始します > ")


async def collect_menu_links(page: Page, *, base_url: str) -> list[dict[str, Any]]:
    script = """
() => Array.from(document.querySelectorAll('#leftNavi a.listNavi')).map((anchor) => {
  const item = anchor.closest('li');
  const number = anchor.querySelector('.listSpan')?.textContent?.trim() || '';
  const title = anchor.querySelector('.listPosition')?.textContent?.trim() || anchor.textContent?.trim() || '';
  return {
    id: item?.id || '',
    number,
    title,
    href: anchor.getAttribute('href') || '',
  };
})
"""
    raw_items = await page.evaluate(script)
    links: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in list(raw_items or []):
        href = str((raw or {}).get("href") or "").strip()
        if not href:
            continue
        absolute_url = urljoin(base_url, href)
        if absolute_url in seen:
            continue
        seen.add(absolute_url)
        links.append(
            {
                "id": str((raw or {}).get("id") or "").strip(),
                "number": str((raw or {}).get("number") or "").strip(),
                "title": str((raw or {}).get("title") or "").strip(),
                "href": href,
                "url": absolute_url,
            }
        )
    return links


def _is_service_api_page(url: str, *, base_url: str) -> bool:
    if not url.startswith(base_url):
        return False
    parsed = urlparse(url)
    path = parsed.path or ""
    return bool(re.fullmatch(r"/merchant-portal/view/ja/common/1-1_service_index/[^/]+/?", path))


def _is_supported_capture_url(url: str, *, base_url: str) -> bool:
    if not url.startswith(base_url):
        return False
    parsed = urlparse(url)
    path = parsed.path or ""
    if path.startswith("/merchant-portal/view/"):
        return True
    if path in {
        "/merchant-portal/backToMenu",
        "/merchant-portal/serviceList",
        "/merchant-portal/applicationContract",
        "/merchant-portal/serviceCreate",
        "/merchant-portal/sensContract",
        "/merchant-portal/sensConfigurations",
        "/merchant-portal/demoShopIndex",
        "/merchant-portal/failureList",
    }:
        return True
    return False


async def collect_service_api_links(page: Page, *, base_url: str) -> list[dict[str, Any]]:
    script = """
() => Array.from(document.querySelectorAll('#main-content a, #contentWhole a, #contentsMain a, #confluence a')).map((anchor) => {
  return {
    text: anchor.textContent?.trim() || '',
    title: anchor.getAttribute('title') || '',
    href: anchor.getAttribute('href') || '',
  };
})
"""
    raw_items = await page.evaluate(script)
    links: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in list(raw_items or []):
        href = str((raw or {}).get("href") or "").strip()
        if not href or href.startswith("#") or href.lower().startswith("javascript:"):
            continue
        absolute_url = urljoin(base_url, href)
        if absolute_url in seen or not _is_service_api_page(absolute_url, base_url=base_url):
            continue
        seen.add(absolute_url)
        text = str((raw or {}).get("text") or "").strip()
        title = str((raw or {}).get("title") or "").strip()
        links.append(
            {
                "id": "",
                "number": "",
                "title": text or title or absolute_url,
                "href": href,
                "url": absolute_url,
                "source": "service_index",
            }
        )
    return links


async def collect_content_links(page: Page, *, base_url: str) -> list[dict[str, Any]]:
    script = """
() => Array.from(document.querySelectorAll('#main-content a, #contentWhole a, #contentsMain a, #confluence a')).map((anchor) => {
  const text = anchor.textContent?.trim() || '';
  return {
    text,
    title: anchor.getAttribute('title') || '',
    href: anchor.getAttribute('href') || '',
  };
})
"""
    raw_items = await page.evaluate(script)
    links: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in list(raw_items or []):
        href = str((raw or {}).get("href") or "").strip()
        if not href or href.startswith("#") or href.lower().startswith("javascript:"):
            continue
        absolute_url = urljoin(base_url, href)
        if absolute_url in seen or not _is_supported_capture_url(absolute_url, base_url=base_url):
            continue
        seen.add(absolute_url)
        text = str((raw or {}).get("text") or "").strip()
        title = str((raw or {}).get("title") or "").strip()
        links.append(
            {
                "id": "",
                "number": "",
                "title": text or title or absolute_url,
                "href": href,
                "url": absolute_url,
                "source": "content",
            }
        )
    return links


async def extract_feature_list(page: Page) -> list[dict[str, Any]]:
    script = """
() => {
  const root = document.querySelector('#main-content, #contentWhole, #contentsMain, #confluence') || document.body;
  const anchors = Array.from(root.querySelectorAll('a[href]'));
  const currentUrl = new URL(window.location.href);
  const currentPath = currentUrl.pathname.endsWith('/') ? currentUrl.pathname : currentUrl.pathname + '/';

  function normalize(text) {
    return (text || '').replace(/\\s+/g, ' ').trim();
  }

  function blockText(anchor) {
    const block = anchor.closest('li, p, div, tr, td') || anchor.parentElement;
    return normalize(block ? block.textContent : '');
  }

  return anchors.map((anchor) => {
    const href = anchor.getAttribute('href') || '';
    let absolute = '';
    try {
      absolute = new URL(href, window.location.href).toString();
    } catch (e) {
      return null;
    }
    const text = normalize(anchor.textContent);
    const absoluteUrl = new URL(absolute);
    const path = absoluteUrl.pathname.endsWith('/') ? absoluteUrl.pathname : absoluteUrl.pathname + '/';
    if (!path.startsWith(currentPath) || path === currentPath) {
      return null;
    }
    const relative = path.slice(currentPath.length).replace(/\\/$/, '');
    if (!relative || relative.includes('/')) {
      return null;
    }
    const surrounding = blockText(anchor);
    const description = normalize(surrounding.replace(text, ''));
    return {
      name: text,
      url: absolute,
      description,
    };
  }).filter(Boolean);
}
"""
    raw_items = await page.evaluate(script)
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in list(raw_items or []):
        url = str((raw or {}).get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        deduped.append(
            {
                "name": str((raw or {}).get("name") or "").strip(),
                "url": url,
                "description": str((raw or {}).get("description") or "").strip(),
            }
        )
    return deduped


async def wait_for_page_ready(page: Page) -> None:
    try:
        await page.wait_for_load_state("networkidle", timeout=5000)
    except Exception:
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass
    await page.wait_for_timeout(500)


async def extract_page_payload(page: Page, *, url: str) -> dict[str, Any]:
    await wait_for_page_ready(page)
    title = await page.title()
    body_text = await page.locator("body").inner_text()
    main_text = body_text
    for selector in ("#main-content", "#contentWhole", "#contentsMain", "#confluence"):
        locator = page.locator(selector)
        if await locator.count() == 0:
            continue
        text = (await locator.first.inner_text()).strip()
        if text:
            main_text = text
            break
    html = await page.content()
    return {
        "url": url,
        "title": title,
        "main_text": main_text,
        "body_text": body_text,
        "html": html,
    }


def save_page_files(
    *,
    output_dir: Path,
    index: int,
    item: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    label_parts = [str(item.get("number") or "").strip(), str(item.get("title") or "").strip()]
    filename_stem = slugify("_".join(part for part in label_parts if part))
    filename_stem = f"{index:02d}_{filename_stem}"
    html_path = output_dir / "pages" / f"{filename_stem}.html"
    txt_path = output_dir / "pages" / f"{filename_stem}.txt"
    json_path = output_dir / "pages" / f"{filename_stem}.json"

    ensure_parent(html_path)
    html_path.write_text(str(payload.get("html") or ""), encoding="utf-8")
    txt_path.write_text(str(payload.get("main_text") or ""), encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {
                "menu_item": item,
                "url": payload.get("url"),
                "title": payload.get("title"),
                "main_text": payload.get("main_text"),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\r\n",
        encoding="utf-8",
    )

    return {
        **item,
        "saved_html": str(html_path),
        "saved_text": str(txt_path),
        "saved_json": str(json_path),
        "page_title": payload.get("title"),
    }


def save_feature_list_files(
    *,
    output_dir: Path,
    index: int,
    item: dict[str, Any],
    page_title: str,
    feature_list: list[dict[str, Any]],
) -> dict[str, Any]:
    label_parts = [str(item.get("number") or "").strip(), str(item.get("title") or "").strip()]
    filename_stem = slugify("_".join(part for part in label_parts if part))
    filename_stem = f"{index:02d}_{filename_stem}"
    md_path = output_dir / "feature_lists" / f"{filename_stem}.md"
    json_path = output_dir / "feature_lists" / f"{filename_stem}.json"

    ensure_parent(md_path)
    lines = [page_title, "", "機能一覧", ""]
    for feature in feature_list:
        lines.append(f"- [{feature['name']}]({feature['url']})")
        if feature["description"]:
            lines.append(f"  {feature['description']}")
    md_path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {
                "service_page": item,
                "page_title": page_title,
                "feature_list": feature_list,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\r\n",
        encoding="utf-8",
    )
    return {
        **item,
        "page_title": page_title,
        "feature_count": len(feature_list),
        "saved_markdown": str(md_path),
        "saved_json": str(json_path),
    }


async def crawl_and_save(page: Page, *, start_url: str, output_dir: Path) -> dict[str, Any]:
    parsed = urlparse(start_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    saved_pages: list[dict[str, Any]] = []
    await page.goto(start_url, wait_until="domcontentloaded")
    service_links = await collect_service_api_links(page, base_url=base_url)

    for index, item in enumerate(service_links, start=1):
        url = str(item.get("url") or "")
        safe_print(f"[{index}/{len(service_links)}] {item.get('title')} -> {url}")
        await page.goto(url, wait_until="domcontentloaded")
        payload = await extract_page_payload(page, url=url)
        feature_list = await extract_feature_list(page)
        saved_pages.append(
            save_feature_list_files(
                output_dir=output_dir,
                index=index,
                item=item,
                page_title=str(payload.get("title") or item.get("title") or url),
                feature_list=feature_list,
            )
        )

    index_path = output_dir / "index.json"
    ensure_parent(index_path)
    index_payload = {
        "start_url": start_url,
        "captured_at": datetime.now().isoformat(),
        "page_count": len(saved_pages),
        "pages": saved_pages,
    }
    index_path.write_text(json.dumps(index_payload, ensure_ascii=False, indent=2) + "\r\n", encoding="utf-8")
    return index_payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch logged-in Chrome for RMS WEB SERVICE and save menu pages as html/text/json")
    parser.add_argument("--start-url", default=DEFAULT_START_URL)
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--profile-dir", default=str(DEFAULT_PROFILE_DIR))
    parser.add_argument("--chrome-path", default="")
    parser.add_argument("--open-only", action="store_true", help="Open Chrome and stop after manual login without crawling")
    parser.add_argument("--keep-open", action="store_true", help="Keep Chrome open after capture")
    return parser.parse_args(argv)


async def async_main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output_root = Path(args.output_root)
    profile_dir = Path(args.profile_dir)
    output_dir = resolve_output_dir(output_root)
    chrome_path = Path(args.chrome_path) if args.chrome_path else None

    playwright = await async_playwright().start()
    context: BrowserContext | None = None
    try:
        context, page, launch_meta = await launch_logged_in_chrome(
            playwright,
            profile_dir=profile_dir,
            start_url=args.start_url,
            chrome_path=chrome_path,
        )
        safe_print(json.dumps({"launch_meta": launch_meta}, ensure_ascii=False, indent=2))
        await prompt_after_manual_login(page, start_url=args.start_url)

        if args.open_only:
            safe_print("open-only モードのため、保存巡回は行わず終了します。")
            return 0

        index_payload = await crawl_and_save(page, start_url=args.start_url, output_dir=output_dir)
        safe_print("")
        safe_print("保存完了")
        safe_print(json.dumps({"output_dir": str(output_dir), "page_count": index_payload["page_count"]}, ensure_ascii=False, indent=2))
        if args.keep_open:
            safe_print("Chrome を開いたままにします。閉じたい場合はブラウザを手動で閉じてください。")
            await asyncio.to_thread(input, "終了するには Enter > ")
        return 0
    finally:
        try:
            if context is not None and not args.keep_open:
                await context.close()
        finally:
            await playwright.stop()


async def prompt_after_manual_login(page: Page, *, start_url: str) -> None:
    del page
    safe_print("")
    safe_print("Chrome を起動しました。")
    safe_print("1. 画面で RMS WEB SERVICE にログインしてください")
    safe_print(f"2. 次のページまで移動してください: {start_url}")
    safe_print("3. 準備できたら、このターミナルに戻って Enter を押してください")
    safe_print("")
    await asyncio.to_thread(input, "Enter を押すと取得を開始します > ")


async def extract_feature_list(page: Page) -> list[dict[str, Any]]:
    script = """
() => {
  const root = document.querySelector('#main-content, #contentWhole, #contentsMain, #confluence') || document.body;
  const anchors = Array.from(root.querySelectorAll('a[href]'));
  const currentUrl = new URL(window.location.href);
  const currentPath = currentUrl.pathname.endsWith('/') ? currentUrl.pathname : currentUrl.pathname + '/';

  function normalize(text) {
    return (text || '').replace(/\\s+/g, ' ').trim();
  }

  function blockText(anchor) {
    const block = anchor.closest('li, p, div, tr, td') || anchor.parentElement;
    return normalize(block ? block.textContent : '');
  }

  return anchors.map((anchor) => {
    const href = anchor.getAttribute('href') || '';
    let absolute = '';
    try {
      absolute = new URL(href, window.location.href).toString();
    } catch (e) {
      return null;
    }
    const text = normalize(anchor.textContent);
    const absoluteUrl = new URL(absolute);
    const path = absoluteUrl.pathname.endsWith('/') ? absoluteUrl.pathname : absoluteUrl.pathname + '/';
    if (!path.startsWith(currentPath) || path === currentPath) {
      return null;
    }
    const relative = path.slice(currentPath.length).replace(/\\/$/, '');
    if (!relative || relative.includes('/')) {
      return null;
    }
    const surrounding = blockText(anchor);
    const description = normalize(surrounding.replace(text, ''));
    return {
      name: text,
      url: absolute,
      description,
    };
  }).filter(Boolean);
}
"""
    raw_items = await page.evaluate(script)
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in list(raw_items or []):
        url = str((raw or {}).get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        deduped.append(
            {
                "name": str((raw or {}).get("name") or "").strip(),
                "url": url,
                "description": str((raw or {}).get("description") or "").strip(),
            }
        )
    return deduped


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="RMS WEB SERVICE のサービスAPIページを開き、各ページの機能一覧だけを保存します"
    )
    parser.add_argument("--start-url", default=DEFAULT_START_URL)
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--profile-dir", default=str(DEFAULT_PROFILE_DIR))
    parser.add_argument("--chrome-path", default="")
    parser.add_argument("--open-only", action="store_true", help="ログイン確認だけ行い、取得せず終了します")
    parser.add_argument("--keep-open", action="store_true", help="取得後も Chrome を開いたままにします")
    return parser.parse_args(argv)


async def async_main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output_root = Path(args.output_root)
    profile_dir = Path(args.profile_dir)
    output_dir = resolve_output_dir(output_root)
    chrome_path = Path(args.chrome_path) if args.chrome_path else None

    playwright = await async_playwright().start()
    context: BrowserContext | None = None
    try:
        context, page, launch_meta = await launch_logged_in_chrome(
            playwright,
            profile_dir=profile_dir,
            start_url=args.start_url,
            chrome_path=chrome_path,
        )
        safe_print(json.dumps({"launch_meta": launch_meta}, ensure_ascii=False, indent=2))
        await prompt_after_manual_login(page, start_url=args.start_url)

        if args.open_only:
            safe_print("open-only モードのため、保存巡回は行わず終了します。")
            return 0

        index_payload = await crawl_and_save(page, start_url=args.start_url, output_dir=output_dir)
        safe_print("")
        safe_print("取得完了:")
        safe_print(json.dumps({"output_dir": str(output_dir), "page_count": index_payload["page_count"]}, ensure_ascii=False, indent=2))
        if args.keep_open:
            safe_print("Chrome は開いたままにします。閉じる場合はブラウザを手動で終了してください。")
            await asyncio.to_thread(input, "終了するには Enter > ")
        return 0
    finally:
        try:
            if context is not None and not args.keep_open:
                await context.close()
        finally:
            await playwright.stop()


def main(argv: list[str] | None = None) -> int:
    configure_output()
    try:
        return asyncio.run(async_main(argv))
    except KeyboardInterrupt:
        safe_print("cancelled by user", file=sys.stderr)
        return 130
    except Exception as exc:
        safe_print(f"capture error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
