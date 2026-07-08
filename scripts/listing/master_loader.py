
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .models import MasterData


MASTER_FILENAMES = {
    "blacklist": "blacklist.txt",
    "kako_ng": "kakoNG_rakuten.txt",
    "replacements": "replacelist_rakuten.txt",
    "prohibited_rakuten": "kinsiword_rakuten.txt",
    "prohibited_other": "kinsiword_other.txt",
    "listed_asins": "shuppinlist_rakuten.txt",
    "category_map": "catlist_rakuten.txt",
    "attribute_definitions": "属性定義書.txt",
}


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


def load_attribute_definitions(path: Path) -> dict[int, list[str]]:
    result: dict[int, list[str]] = {}
    for line in _normalized_lines(read_text_auto(path)):
        parts = _split_tab(line)
        if len(parts) < 3:
            continue
        try:
            genre_id = int(parts[0])
        except ValueError:
            continue
        attr_names = [part for part in parts[2:] if part]
        result[genre_id] = attr_names
    return result


def load_master_data(master_dir: Path, allow_missing: bool = False) -> MasterData:
    master_dir = Path(master_dir)
    missing_files: list[str] = []
    loaded: dict[str, object] = {}

    for key, filename in MASTER_FILENAMES.items():
        path = master_dir / filename
        if not path.exists():
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
            loaded[key] = load_attribute_definitions(path)

    if missing_files and not allow_missing:
        missing = ", ".join(missing_files)
        raise MissingMasterFileError(f"Missing master files: {missing}")

    return MasterData(
        blacklist=loaded.get("blacklist", set()),
        kako_ng=loaded.get("kako_ng", {}),
        replacements=loaded.get("replacements", []),
        prohibited_words_rakuten=loaded.get("prohibited_rakuten", []),
        prohibited_words_other=loaded.get("prohibited_other", []),
        listed_asins=loaded.get("listed_asins", {}),
        category_map=loaded.get("category_map", {}),
        attribute_definitions=loaded.get("attribute_definitions", {}),
        missing_files=missing_files,
    )
