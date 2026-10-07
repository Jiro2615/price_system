"""Fail closed for obviously corrupted advertiser names, never guess a name."""
from __future__ import annotations

import html
import re
import unicodedata
from typing import Any


class ComplianceTextError(RuntimeError):
    """A local configuration/text problem, not a product business-NG rule."""


def validate_advertiser_name(value: object, *, field: str = "advertiser_name") -> None:
    text = unicodedata.normalize("NFKC", str(value or ""))
    # Typical UTF-8 bytes misread as CP932: 株式会社 -> 譬ｪ蠑丈ｼ夂､ｾ,
    # Katakana -> repeated 繝/繧 sequences. Check only the advertiser label,
    # not arbitrary product prose; do not repair a legal entity by guessing.
    corrupted = (
        "\ufffd" in text
        or any(unicodedata.category(char) in {"Cc", "Cs"} for char in text)
        or re.search(r"譬[ェｪ]蠑", text) is not None
        or len(re.findall(r"[縺繧繝][ぁ-んァ-ヶ一-龯]", text)) >= 2
    )
    if corrupted:
        raise ComplianceTextError(
            f"広告文責の文字化けを検出しました（{field}）。"
            "実行PCの C:\\rakuten\\.env をUTF-8で保存し、会社名を確認してから再判定してください。"
        )


def validate_advertiser_payload(payload: dict[str, Any]) -> None:
    descriptions = payload.get("productDescription") or {}
    fields = ([(f"productDescription.{key}", value) for key, value in descriptions.items()]
              if isinstance(descriptions, dict) else [])
    fields.append(("salesDescription", payload.get("salesDescription") or ""))
    for field, value in fields:
        if not isinstance(value, str):
            continue
        # Support both generated <br /> blocks and saved files with wrappers
        # or HTML entities. Tags on the same line must not hide a broken name.
        text = re.sub(r"<\s*(?:br\b[^>]*|/p|/div)\s*/?>", "\n", value, flags=re.I)
        text = html.unescape(re.sub(r"<[^>]+>", "", text))
        for match in re.finditer(r"広告文責\s*[:：]\s*([^\r\n]+)", text):
            validate_advertiser_name(match.group(1), field=field)
