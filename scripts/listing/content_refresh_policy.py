"""Identity checks for content refresh, independent of listing eligibility."""
from __future__ import annotations

from dataclasses import fields

from scripts.listing.models import AmazonCheckResult


def content_identity_error(asin: str, amazon: AmazonCheckResult | None) -> str | None:
    expected = asin.strip().upper()
    if amazon is None:
        return "Amazon確認結果がありません"
    # The bridge can retain the requested ASIN after the browser guard rejected
    # a different product. Never interpret that fallback field as proof.
    reason = str(amazon.ng_reason or "").strip()
    if reason.startswith(("ASIN不一致", "ASIN未確認")):
        return reason
    if str(amazon.requested_asin or "").strip().upper() != expected:
        return "ASIN不一致: Amazon確認の要求ASINが異なります"
    observed = str(amazon.page_asin or "").strip().upper()
    if not observed:
        return "ASIN未確認: AmazonページのASINを確認できません"
    if observed != expected:
        return f"ASIN不一致: {expected} != {observed}"
    return None


def content_refresh_artifact_error(result: dict) -> str | None:
    """Recheck saved refresh observations before any external write."""
    if result.get("content_refresh") is not True:
        return "最新化専用の準備結果が必要です。最新版で再取得してください"
    amazon = result.get("amazon_result")
    if isinstance(amazon, dict):
        try:
            amazon = AmazonCheckResult(**{f.name: amazon[f.name] for f in fields(AmazonCheckResult) if f.name in amazon})
        except (TypeError, ValueError):
            amazon = None
    if not isinstance(amazon, AmazonCheckResult):
        return "Amazon確認結果がありません"
    if amazon.system_error or amazon.amazon_confirmation_waiting:
        return amazon.ng_reason or "Amazonの確認が完了していません"
    error = content_identity_error(str(result.get("asin") or ""), amazon)
    if error:
        return error
    keepa = result.get("keepa_result")
    keepa_asin = keepa.get("asin") if isinstance(keepa, dict) else getattr(keepa, "asin", "")
    if str(keepa_asin or "").strip().upper() != str(result.get("asin") or "").strip().upper():
        return "ASIN不一致: Keepaの商品ASINが異なります"
    return None
