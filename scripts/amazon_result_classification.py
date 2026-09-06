"""Price/stock classification of known product-level purchase restrictions."""


def classify_purchase_restriction(result: dict) -> dict:
    """Keep technical failures retryable; known purchase restrictions are NG."""
    if any(result.get(key) for key in (
        "amazon_confirmation_waiting", "skip_product_persistence", "page_needs_reset"
    )):
        return result

    reason = str(result.get("ng_reason") or "").strip()
    known_restriction = (
        reason == "ギフト不可"
        or reason.startswith("ギフト不可（")
        or reason == "ASIN不一致（別商品へ遷移）"
        or reason.startswith("ASIN不一致 current=")
        or reason in {"BuyBox取得失敗", "BuyBoxなし"}
    )
    if known_restriction:
        result["business_ng"] = True
        result["system_error"] = False
        result["shipping_status"] = "NG"
        result.pop("system_error_reason", None)
    return result
