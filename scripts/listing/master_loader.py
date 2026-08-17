
from __future__ import annotations

from pathlib import Path
import re
from typing import Iterable

from scripts.listing.models import MasterData
from scripts.listing.prohibited_word_masking import (
    load_allowed_phrase_rules,
    normalize_allowed_phrase_payload,
    split_replacement_rules,
)


MASTER_FILENAMES = {
    "blacklist": "blacklist.txt",
    "kako_ng": "kakoNG_rakuten.txt",
    "replacements": "replacelist_rakuten.txt",
    "prohibited_rakuten": "kinsiword_rakuten.txt",
    "prohibited_other": "kinsiword_other.txt",
    "category_map": "catlist_rakuten.txt",
    "allowed_phrases": "allowed_phrases_rakuten.json",
    "attribute_definitions": "属性定義書.txt",
}

STORE_ALLOWED_PHRASES_FILENAME = "allowed_phrases_rakuten.{store_code}.json"
OPTIONAL_MASTER_KEYS = {"prohibited_other"}


ENCODINGS = ("utf-8-sig", "utf-8", "cp932", "shift_jis")


class MissingMasterFileError(RuntimeError):
    pass


def read_text_auto(path: Path) -> str:
    last_error: Exception | None = None
    for encoding in ENCODINGS:
        try:
            return path.read_text(encoding=encoding)
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"Failed to read master file: {path} ({last_error})")


def _normalized_lines(text: str) -> Iterable[str]:
    for raw_line in text.splitlines():
        line = raw_line.strip("\ufeff").strip()
        if not line:
            continue
        yield line


def _split_tab(line: str) -> list[str]:
    return [part.strip() for part in line.split("\t")]


def load_blacklist(path: Path) -> set[str]:
    return {line.split("\t")[0].strip().upper() for line in _normalized_lines(read_text_auto(path)) if line}


def load_kako_ng(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in _normalized_lines(read_text_auto(path)):
        parts = _split_tab(line)
        asin = parts[0].upper()
        reason = parts[1] if len(parts) > 1 else "過去NG"
        result[asin] = reason
    return result


def load_replacements(path: Path) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    for line in _normalized_lines(read_text_auto(path)):
        parts = _split_tab(line)
        source = parts[0]
        target = parts[1] if len(parts) > 1 else ""
        if source:
            result.append((source, target))
    return result


def load_word_list(path: Path) -> list[str]:
    return [line.split("\t")[0].strip() for line in _normalized_lines(read_text_auto(path)) if line]


def load_listed_asins(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in _normalized_lines(read_text_auto(path)):
        parts = _split_tab(line)
        if not parts:
            continue
        asin = parts[0].upper()
        management_number = parts[1] if len(parts) > 1 else ""
        result[asin] = management_number
    return result


def load_category_map(path: Path) -> dict[int, int]:
    result: dict[int, int] = {}
    for line in _normalized_lines(read_text_auto(path)):
        parts = _split_tab(line)
        if len(parts) < 2:
            continue
        try:
            keepa_cat_id = int(parts[0])
            rakuten_genre_id = int(parts[1])
        except ValueError:
            continue
        result.setdefault(keepa_cat_id, rakuten_genre_id)
    return result


def load_attribute_definition_records(path: Path) -> tuple[dict[int, list[str]], dict[int, str]]:
    result: dict[int, list[str]] = {}
    genre_paths: dict[int, str] = {}
    for line in _normalized_lines(read_text_auto(path)):
        parts = _split_tab(line)
        if len(parts) < 3:
            continue
        try:
            genre_id = int(parts[0])
        except ValueError:
            continue
        genre_paths[genre_id] = parts[1]
        attr_names = [part for part in parts[2:] if part]
        result[genre_id] = attr_names
    return result, genre_paths


def load_attribute_definitions(path: Path) -> dict[int, list[str]]:
    result, _genre_paths = load_attribute_definition_records(path)
    return result


def apply_store_allowed_phrase_overrides(
    master_data: MasterData,
    master_dir: Path,
    store_code: str,
) -> MasterData:
    """Merge an optional store-specific allow-list on top of shared rules."""
    normalized_store_code = str(store_code or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", normalized_store_code):
        return master_data

    override_path = Path(master_dir) / STORE_ALLOWED_PHRASES_FILENAME.format(
        store_code=normalized_store_code
    )
    if override_path.exists():
        overlay = load_allowed_phrase_rules(override_path)
        merged_rules = {
            word: list(phrases)
            for word, phrases in master_data.allowed_phrase_rules.items()
        }
        for word, phrases in overlay["rules"].items():
            merged_rules.setdefault(word, []).extend(phrases)

        master_data.allowed_phrase_rules = normalize_allowed_phrase_payload(merged_rules)["rules"]

        merged_checks = {
            phrase: list(checks)
            for phrase, checks in master_data.allowed_phrase_separate_checks.items()
        }
        for phrase, checks in overlay["separate_checks"].items():
            target = merged_checks.setdefault(phrase, [])
            for check in checks:
                if check not in target:
                    target.append(check)
        master_data.allowed_phrase_separate_checks = merged_checks
        master_data.allowed_phrase_meta = {
            **master_data.allowed_phrase_meta,
            "store_override_file": override_path.name,
        }
    # PostgreSQL becomes the active source only after the explicit legacy
    # import completes. Until then this safely preserves file-based behavior.
    from scripts.listing.listing_master_db import apply_database_master_snapshot

    return apply_database_master_snapshot(master_data, normalized_store_code)


def load_master_data(master_dir: Path, allow_missing: bool = False) -> MasterData:
    master_dir = Path(master_dir)
    missing_files: list[str] = []
    loaded: dict[str, object] = {}

    for key, filename in MASTER_FILENAMES.items():
        path = master_dir / filename
        if not path.exists():
            if key not in OPTIONAL_MASTER_KEYS:
                missing_files.append(filename)
            continue
        if key == "blacklist":
            loaded[key] = load_blacklist(path)
        elif key == "kako_ng":
            loaded[key] = load_kako_ng(path)
        elif key == "replacements":
            loaded[key] = load_replacements(path)
        elif key in {"prohibited_rakuten", "prohibited_other"}:
            loaded[key] = load_word_list(path)
        elif key == "listed_asins":
            loaded[key] = load_listed_asins(path)
        elif key == "category_map":
            loaded[key] = load_category_map(path)
        elif key == "attribute_definitions":
            attr_defs, genre_paths = load_attribute_definition_records(path)
            loaded[key] = attr_defs
            loaded["genre_paths"] = genre_paths
        elif key == "allowed_phrases":
            loaded[key] = load_allowed_phrase_rules(path)

    if missing_files and not allow_missing:
        missing = ", ".join(missing_files)
        raise MissingMasterFileError(f"Missing master files: {missing}")

    prohibited_words_rakuten = loaded.get("prohibited_rakuten", [])
    cleanup_replacements, legacy_spacing_replacements = split_replacement_rules(
        loaded.get("replacements", []),
        prohibited_words_rakuten,
    )

    return MasterData(
        blacklist=loaded.get("blacklist", set()),
        kako_ng=loaded.get("kako_ng", {}),
        replacements=loaded.get("replacements", []),
        prohibited_words_rakuten=prohibited_words_rakuten,
        prohibited_words_other=loaded.get("prohibited_other", []),
        listed_asins=loaded.get("listed_asins", {}),
        category_map=loaded.get("category_map", {}),
        attribute_definitions=loaded.get("attribute_definitions", {}),
        genre_paths=loaded.get("genre_paths", {}),
        cleanup_replacements=cleanup_replacements,
        legacy_spacing_replacements=legacy_spacing_replacements,
        allowed_phrase_rules=loaded.get("allowed_phrases", {}).get("rules", {}),
        allowed_phrase_meta=loaded.get("allowed_phrases", {}).get("meta", {}),
        allowed_phrase_separate_checks=loaded.get("allowed_phrases", {}).get("separate_checks", {}),
        missing_files=missing_files,
    )
