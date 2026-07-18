from __future__ import annotations

import argparse
import builtins
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

from scripts.keepa_raw_analyzer import analyze_keepa_response
from scripts.listing.keepa_product_client import KeepaClient, load_keepa_api_key
from scripts.listing.models import sanitize_for_output, to_jsonable


DEFAULT_OUTPUT_DIR = Path("output") / "keepa_inspect"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch and inspect raw Keepa Product API responses.")
    parser.add_argument("--asin", help="ASIN to inspect")
    parser.add_argument("--raw-json", help="Use saved raw Keepa response JSON instead of calling the API")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for raw and report JSON outputs")
    return parser.parse_args()


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def configure_output() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None or not hasattr(stream, "reconfigure"):
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def safe_print_json(payload: object) -> None:
    text = json.dumps(to_jsonable(sanitize_for_output(payload)), ensure_ascii=False, indent=2)
    try:
        builtins.print(text)
    except UnicodeEncodeError:
        stream = getattr(sys, "stdout", None)
        encoding = getattr(stream, "encoding", None) or "utf-8"
        safe_text = text.encode(encoding, errors="replace").decode(encoding, errors="replace")
        builtins.print(safe_text)


def write_json(path: Path, payload: object) -> None:
    safe_payload = sanitize_for_output(payload)
    text = json.dumps(to_jsonable(safe_payload), ensure_ascii=False, indent=2)
    path.write_text(text + "\n", encoding="utf-8")


def load_raw_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    configure_output()
    args = parse_args()
    raw_json_path = Path(args.raw_json) if args.raw_json else None
    raw_response: dict[str, object] | None = None
    if raw_json_path is not None:
        raw_response = load_raw_json(raw_json_path)

    asin = (args.asin or "").strip().upper()
    if not asin and raw_response is not None:
        products = raw_response.get("products") or []
        if products and isinstance(products[0], dict):
            asin = str(products[0].get("asin") or "").strip().upper()
    if not asin:
        raise RuntimeError("--asin is required unless it is available in --raw-json")
    output_dir = Path(args.output_dir)
    ensure_directory(output_dir)

    client = KeepaClient(api_key="REDACTED")
    request_params = client.build_product_request_params(asin)
    if raw_response is None:
        client.api_key = load_keepa_api_key()
        raw_response = client.fetch_product_raw(asin)
    parsed_product, field_report, mapping_report = analyze_keepa_response(
        asin=asin,
        raw_response=raw_response,
        request_params=request_params,
    )

    raw_path = output_dir / f"{asin}_raw.json"
    field_report_path = output_dir / f"{asin}_field_report.json"
    mapping_report_path = output_dir / f"{asin}_mapping_report.json"

    write_json(raw_path, raw_response)
    write_json(field_report_path, field_report)
    write_json(mapping_report_path, mapping_report)

    summary = {
        "asin": asin,
        "raw_json": str(raw_path),
        "field_report_json": str(field_report_path),
        "mapping_report_json": str(mapping_report_path),
        "parsed_keepa_product": parsed_product,
    }
    safe_print_json(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
