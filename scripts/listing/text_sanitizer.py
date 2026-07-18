from __future__ import annotations

from typing import Any


MACHINE_DEPENDENT_TEXT_REPLACEMENTS: dict[str, str] = {
    "№": "No.",
    "㎝": "cm",
    "㎜": "mm",
    "㈱": "株式会社",
    "①": "1",
    "②": "2",
    "③": "3",
    "④": "4",
    "⑤": "5",
    "⑥": "6",
    "⑦": "7",
    "⑧": "8",
    "⑨": "9",
    "⑩": "10",
}


def sanitize_text_for_rakuten_api(value: str) -> str:
    sanitized = str(value)
    for source, replacement in MACHINE_DEPENDENT_TEXT_REPLACEMENTS.items():
        sanitized = sanitized.replace(source, replacement)
    return sanitized


def sanitize_payload_text_for_rakuten_api(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_text_for_rakuten_api(value)
    if isinstance(value, list):
        return [sanitize_payload_text_for_rakuten_api(item) for item in value]
    if isinstance(value, dict):
        return {key: sanitize_payload_text_for_rakuten_api(item) for key, item in value.items()}
    return value
