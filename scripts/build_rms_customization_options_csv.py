#!/usr/bin/env python3
"""Create RMS CSV import files that replace only product customization options.

The input files are RMS "normal item" CSV exports.  Every existing option row
for each management number is removed and replaced with the canonical option
set used by new Rakuten listings.  All other columns and rows (including SKU
rows) are copied unchanged.  This script never calls an API or changes RMS.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Iterable

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.listing.rakuten_payload_builder import build_customization_options


# RMSのnormal-item出力（105列）では、0列目が商品管理番号、1列目が
# 選択肢タイプ、2列目が項目名、3列目以降が選択肢、103列目が必須フラグ、
# 104列目がSKU管理番号。以前の定数は1列ずれており、商品行と選択肢行を
# 取り違えていた。
REQUIRED_FLAG_INDEX = 103
OPTION_TYPE_INDEX = 1
OPTION_NAME_INDEX = 2
OPTION_VALUE_START_INDEX = 3
MANAGEMENT_NUMBER_INDEX = 0
SKU_MANAGEMENT_NUMBER_INDEX = 104
CSV_ENCODING = "cp932"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build RMS normal-item CSV files replacing only product customization options."
    )
    parser.add_argument(
        "--input",
        action="append",
        required=True,
        help="RMS normal-item export CSV. Specify once per source file.",
    )
    parser.add_argument("--output-dir", required=True, help="Directory for generated CSV files.")
    parser.add_argument(
        "--max-data-rows",
        type=int,
        default=99995,
        help="Maximum data rows per output file (default: 99995).",
    )
    parser.add_argument(
        "--prefix",
        default="normal-item-customization-options",
        help="Output filename prefix (default: normal-item-customization-options).",
    )
    return parser.parse_args()


def read_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open("r", encoding=CSV_ENCODING, newline="") as handle:
        rows = list(csv.reader(handle))
    if not rows:
        raise ValueError(f"CSV is empty: {path}")
    return rows[0], rows[1:]


def grouped_rows(rows: Iterable[list[str]]) -> list[list[list[str]]]:
    groups: list[list[list[str]]] = []
    group: list[list[str]] = []
    current_management_number = ""
    for row in rows:
        if len(row) <= MANAGEMENT_NUMBER_INDEX or not row[MANAGEMENT_NUMBER_INDEX]:
            raise ValueError("A data row has no product management number.")
        management_number = row[MANAGEMENT_NUMBER_INDEX]
        if management_number != current_management_number:
            if group:
                groups.append(group)
            group = []
            current_management_number = management_number
        group.append(row)
    if group:
        groups.append(group)
    return groups


def canonical_option_rows(management_number: str, column_count: int) -> list[list[str]]:
    type_codes = {
        "MULTIPLE_SELECTION": "c",
        "SINGLE_SELECTION": "s",
    }
    rows: list[list[str]] = []
    for option in build_customization_options():
        type_code = type_codes.get(str(option.get("inputType") or ""))
        if not type_code:
            raise ValueError(f"Unsupported canonical option input type: {option.get('inputType')!r}")
        row = [""] * column_count
        row[MANAGEMENT_NUMBER_INDEX] = management_number
        row[OPTION_TYPE_INDEX] = type_code
        row[OPTION_NAME_INDEX] = str(option.get("displayName") or "")
        for offset, selection in enumerate(option.get("selections") or []):
            target_index = OPTION_VALUE_START_INDEX + offset
            if target_index >= REQUIRED_FLAG_INDEX:
                raise ValueError("Too many option selections for RMS CSV.")
            row[target_index] = str((selection or {}).get("displayValue") or "")
        row[REQUIRED_FLAG_INDEX] = "1" if option.get("required") else "0"
        rows.append(row)
    return rows


def is_option_row(row: list[str]) -> bool:
    return (
        len(row) > OPTION_NAME_INDEX
        and bool(row[OPTION_TYPE_INDEX])
        and bool(row[OPTION_NAME_INDEX])
    )


def replace_options(group: list[list[str]], column_count: int) -> list[list[str]]:
    management_number = group[0][MANAGEMENT_NUMBER_INDEX]
    if any(row[MANAGEMENT_NUMBER_INDEX] != management_number for row in group):
        raise ValueError(f"Mixed management numbers in group: {management_number}")

    # 商品レベル行は選択肢タイプもSKU管理番号も空。選択肢行（type=c/s）と
    # SKU行（104列目にSKU管理番号あり）を確実に除外する。
    item_rows = [
        row
        for row in group
        if not is_option_row(row)
        and not (len(row) > SKU_MANAGEMENT_NUMBER_INDEX and row[SKU_MANAGEMENT_NUMBER_INDEX])
    ]
    if len(item_rows) != 1:
        raise ValueError(f"Expected one item row for {management_number}; found {len(item_rows)}")

    preserved_rows = [row for row in group if not is_option_row(row)]
    item_row = item_rows[0]
    remaining_rows = [row for row in preserved_rows if row is not item_row]
    return [item_row, *canonical_option_rows(management_number, column_count), *remaining_rows]


def write_batches(
    output_dir: Path,
    prefix: str,
    header: list[str],
    groups: Iterable[list[list[str]]],
    max_data_rows: int,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written_paths: list[Path] = []
    writer = None
    handle = None
    row_count = 0
    file_number = 0

    def open_next_file():
        nonlocal writer, handle, row_count, file_number
        if handle:
            handle.close()
        file_number += 1
        row_count = 0
        path = output_dir / f"{prefix}_{file_number:02d}.csv"
        handle = path.open("w", encoding=CSV_ENCODING, newline="")
        writer = csv.writer(handle, lineterminator="\r\n")
        writer.writerow(header)
        written_paths.append(path)

    try:
        for group in groups:
            if len(group) > max_data_rows:
                raise ValueError("One product group exceeds --max-data-rows.")
            if writer is None or row_count + len(group) > max_data_rows:
                open_next_file()
            writer.writerows(group)
            row_count += len(group)
    finally:
        if handle:
            handle.close()
    return written_paths


def main() -> int:
    args = parse_args()
    if args.max_data_rows < 5:
        raise ValueError("--max-data-rows must be at least 5.")

    header: list[str] | None = None
    source_groups: list[list[list[str]]] = []
    for raw_path in args.input:
        path = Path(raw_path).expanduser().resolve()
        current_header, rows = read_csv(path)
        if header is None:
            header = current_header
        elif current_header != header:
            raise ValueError(f"CSV header does not match the first input: {path}")
        source_groups.extend(grouped_rows(rows))

    if header is None or len(header) <= REQUIRED_FLAG_INDEX:
        raise ValueError("RMS normal-item CSV header is missing required option columns.")

    output_groups = [replace_options(group, len(header)) for group in source_groups]
    paths = write_batches(
        Path(args.output_dir).expanduser().resolve(),
        args.prefix,
        header,
        output_groups,
        args.max_data_rows,
    )
    print(
        "CUSTOMIZATION_OPTIONS_CSV_BUILT "
        f"products={len(output_groups)} output_files={len(paths)} "
        f"options_per_product={len(build_customization_options())}"
    )
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
