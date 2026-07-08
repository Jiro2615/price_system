
from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional


SECRET_KEYWORDS = ("key", "token", "password", "authorization", "secret")


@dataclass
class AmazonCheckResult:
    requested_asin: str
    page_asin: str = ""
    title: str = ""
    amazon_price: Optional[int] = None
    available_qty: Optional[int] = None
    gift_available: Optional[bool] = None
    shipping_status: str = ""
    business_ng: bool = False
    system_error: bool = False
    ng_reason: str = ""
    current_url: str = ""


@dataclass
class KeepaProductData:
    asin: str
    title: str = ""
    brand: str = ""
    model: str = ""
    ean: str = ""
    images_csv: str = ""
    category_id: Optional[int] = None
    features: list[str] = field(default_factory=list)
    description: str = ""
    style: str = ""
    size: str = ""
    color: str = ""
    buy_box_price: Optional[int] = None
    buy_box_shipping: Optional[int] = None
    avg90_seller_count: Optional[float] = None
    is_adult: bool = False
    raw_summary: dict[str, Any] = field(default_factory=dict)


@dataclass
class MatchedRule:
    rule_type: str
    value: str
    detail: str


@dataclass
class EvaluationResult:
    listing_status: str
    listing_reason: str
    matched_master_rules: list[MatchedRule] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    title: str = ""
    description_pc: str = ""
    description_sp: str = ""
    genre_id: Optional[int] = None
    attributes: list[dict[str, str]] = field(default_factory=list)
    article_number: str = ""
    image_candidates: list[dict[str, str]] = field(default_factory=list)


@dataclass
class MasterData:
    blacklist: set[str]
    kako_ng: dict[str, str]
    replacements: list[tuple[str, str]]
    prohibited_words_rakuten: list[str]
    prohibited_words_other: list[str]
    listed_asins: dict[str, str]
    category_map: dict[int, int]
    attribute_definitions: dict[int, list[str]]
    missing_files: list[str] = field(default_factory=list)


@dataclass
class StoreSettings:
    store_id: Optional[int]
    store_code: str
    store_name: str
    max_stock: int
    fee_rate: float
    use_amazon_point: bool
    profit_mode: str
    profit_rate: float
    profit_amount: int
    fixed_cost: int
    rounding_unit: int
    normal_delivery_date_id: int
    back_order_delivery_date_id: int
    normal_delivery_time_id: int
    back_order_delivery_time_id: int
    ship_from_ids: list[str]
    min_avg90_sellers: float
    management_suffix: str = "187"


@dataclass
class ManagementNumberBundle:
    selected: str
    legacy_candidate: str
    safe_candidate: str
    note: str


def _normalize_scalar(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return to_jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): to_jsonable(inner) for key, inner in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(inner) for inner in value]
    return _normalize_scalar(value)


def sanitize_for_output(value: Any) -> Any:
    if is_dataclass(value):
        value = asdict(value)

    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, inner in value.items():
            if any(word in str(key).lower() for word in SECRET_KEYWORDS):
                continue
            sanitized[str(key)] = sanitize_for_output(inner)
        return sanitized

    if isinstance(value, list):
        return [sanitize_for_output(inner) for inner in value]

    if isinstance(value, tuple):
        return [sanitize_for_output(inner) for inner in value]

    return _normalize_scalar(value)
