"""Local-only preview; never contacts Rakuten or updates listing records."""
import argparse
import json
from pathlib import Path
from scripts.listing.image_overlay import render_overlay


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("images", nargs="+", type=Path, help="Original local image paths")
    parser.add_argument("--output", type=Path, default=Path("output/overlay_preview"))
    parser.add_argument("--free-shipping", action="store_true", help="Confirm these products have free shipping")
    args = parser.parse_args()
    results = []
    for source in args.images:
        output = render_overlay(source, args.output, postage_included=args.free_shipping)
        results.append({"original": str(source.resolve()), "preview": str(output.resolve()),
                        "free_shipping": args.free_shipping})
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = args.output / "preview_manifest.json"
    manifest.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(manifest.resolve())


if __name__ == "__main__":
    main()
