
from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional


SECRET_KEYWORDS = ("apikey", "api_key", "access_token", "refresh_token", "password", "authorization", "secret", "cookie")


def _is_secret_key_name(key: str) -> bool:
    lowered = key.lower()
    if lowered in SECRET_KEYWORDS:
        return True
    return any(keyword in lowered for keyword in ("authorization", "password", "cookie", "secret", "apikey", "api_key", "access_token", "refresh_token"))


@dataclass
class AmazonCheckResult:
    requested_asin: str
    page_asin: str = ""
    title: str = ""
    amazon_price: Optional[int] = None
    available_qty: Optional[int] = None
    minimum_order_quantity: Optional[int] = None
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
    manufacturer: str = ""
    model: str = ""
    part_number: str = ""
    ean: str = ""
    images_csv: str = ""
    image_urls: list[str] = field(default_factory=list)
    image_source: str = "none"
    category_id: Optional[int] = None
    category_tree: list[dict[str, Any]] = field(default_factory=list)
    features: list[str] = field(default_factory=list)
    description: str = ""
    style: str = ""
    size: str = ""
    color: str = ""
    buy_box_price: Optional[int] = None
    buy_box_shipping: Optional[int] = None
    current_new_offer_count: Optional[int] = None
    avg90_new_offer_count: Optional[float] = None
    avg90_seller_count: Optional[float] = None
    total_offer_count: Optional[int] = None
    offer_count_fba: Optional[int] = None
    offer_count_fbm: Optional[int] = None
    hazardous_materials: list[str] = field(default_factory=list)
    is_heat_sensitive: Optional[bool] = None
    scent: str = ""
    is_adult: Optional[bool] = None
    is_adult_source: str = "unknown"
    raw_summary: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResolvedField:
    value: Any = None
    source: str = "none"
    raw_path: Optional[str] = None
    transform: str = ""
    confidence: str = "none"
    evidence: str = ""
    fallback_used: bool = False
    resolution_action: str = "unresolved"


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
    resolved_attributes: dict[str, ResolvedField] = field(default_factory=dict)
    seller_count_evaluation: dict[str, Any] = field(default_factory=dict)
    article_number: str = ""
    image_candidates: list[dict[str, str]] = field(default_factory=list)
    allowed_phrase_matches: list[dict[str, Any]] = field(default_factory=list)
    matched_forbidden_words: list[dict[str, Any]] = field(default_factory=list)
    required_separate_checks: list[str] = field(default_factory=list)
    matched_separate_check_phrases: list[dict[str, Any]] = field(default_factory=list)
    legacy_spacing_reviews: list[dict[str, Any]] = field(default_factory=list)
    provisional_genre_candidate: dict[str, Any] = field(default_factory=dict)
    compliance_evidence: dict[str, Any] = field(default_factory=dict)


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
    genre_paths: dict[int, str] = field(default_factory=dict)
    cleanup_replacements: list[tuple[str, str]] = field(default_factory=list)
    legacy_spacing_replacements: list[dict[str, Any]] = field(default_factory=list)
    allowed_phrase_rules: dict[str, list[str]] = field(default_factory=dict)
    allowed_phrase_meta: dict[str, Any] = field(default_factory=dict)
    allowed_phrase_separate_checks: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
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
    shipping_method_group: str = ""
    cabinet: dict[str, Any] = field(default_factory=dict)
    management_suffix: str = "187"
    min_avg90_new_offer_count: Optional[float] = None
    min_avg90_sellers: Optional[float] = None
    send_inventory_delivery_ids: bool = False
    listing_image_limit: Optional[int] = None


@dataclass
class ListingCommonSettings:
    min_avg90_new_offer_count: float


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
            if _is_secret_key_name(str(key)):
                continue
            sanitized[str(key)] = sanitize_for_output(inner)
        return sanitized

    if isinstance(value, list):
        return [sanitize_for_output(inner) for inner in value]

    if isinstance(value, tuple):
        return [sanitize_for_output(inner) for inner in value]

    return _normalize_scalar(value)
