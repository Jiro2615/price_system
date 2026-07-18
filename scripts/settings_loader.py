import json
import os
import socket
from dataclasses import dataclass
from typing import Any

from db_config import connect_db


SOURCE_CLI = "cli"
SOURCE_DB = "db"
SOURCE_DEFAULT = "default"

WORKER_TYPE_AMAZON = "amazon_check"
WORKER_TYPE_RAKUTEN = "rakuten_update"
WORKER_TYPES = {WORKER_TYPE_AMAZON, WORKER_TYPE_RAKUTEN}

AMAZON_DEFAULTS: dict[str, Any] = {
    "limit": 300,
    "loop_sleep_seconds": 10,
    "empty_sleep_seconds": 60,
    "page_timeout_ms": 60000,
    "use_stats": True,
    "log_retention_days": 14,
}

RAKUTEN_DEFAULTS: dict[str, Any] = {
    "price_limit": 20,
    "stock_limit": 50,
    "blocked_limit": 0,
    "empty_sleep_seconds": 10,
    "error_sleep_seconds": 300,
    "verify": False,
    "api_interval_seconds": 1.5,
    "verify_wait_seconds": 1.5,
    "retry_count": 5,
    "retry_wait_seconds": 5.0,
    "max_change_rate": 0.5,
    "inventory_batch_size": 100,
}


@dataclass(frozen=True)
class SettingRule:
    expected_type: str
    minimum: float | None = None
    exclusive_minimum: bool = False


SETTINGS_RULES: dict[str, dict[str, SettingRule]] = {
    WORKER_TYPE_AMAZON: {
        "limit": SettingRule("int", minimum=1),
        "loop_sleep_seconds": SettingRule("int", minimum=0),
        "empty_sleep_seconds": SettingRule("int", minimum=0),
        "page_timeout_ms": SettingRule("int", minimum=1),
        "use_stats": SettingRule("bool"),
        "log_retention_days": SettingRule("int", minimum=0),
    },
    WORKER_TYPE_RAKUTEN: {
        "price_limit": SettingRule("int", minimum=1),
        "stock_limit": SettingRule("int", minimum=1),
        "blocked_limit": SettingRule("int", minimum=0),
        "empty_sleep_seconds": SettingRule("int", minimum=0),
        "error_sleep_seconds": SettingRule("int", minimum=0),
        "verify": SettingRule("bool"),
        "api_interval_seconds": SettingRule("float", minimum=0),
        "verify_wait_seconds": SettingRule("float", minimum=0),
        "retry_count": SettingRule("int", minimum=0),
        "retry_wait_seconds": SettingRule("float", minimum=0),
        "max_change_rate": SettingRule("float", minimum=0, exclusive_minimum=True),
        "inventory_batch_size": SettingRule("int", minimum=1),
    },
}


class SettingsLoaderError(RuntimeError):
    pass


def default_settings_for_worker_type(worker_type: str) -> dict[str, Any]:
    if worker_type == WORKER_TYPE_AMAZON:
        return dict(AMAZON_DEFAULTS)
    if worker_type == WORKER_TYPE_RAKUTEN:
        return dict(RAKUTEN_DEFAULTS)
    raise SettingsLoaderError(f"unsupported worker_type: {worker_type}")


def _normalize_worker_type(worker_type: str) -> str:
    normalized = str(worker_type or "").strip()
    if normalized not in WORKER_TYPES:
        raise SettingsLoaderError(f"unsupported worker_type: {worker_type}")
    return normalized


def _node_lookup_strategy(explicit_node_code: str | None = None) -> tuple[str, str]:
    env_node_code = str(os.getenv("PRICE_SYSTEM_NODE_CODE") or "").strip()
    if env_node_code:
        return "env", env_node_code

    explicit = str(explicit_node_code or "").strip()
    if explicit:
        return "cli", explicit

    return "hostname", socket.gethostname().strip()


def resolve_node(conn, node_code: str | None = None) -> dict[str, Any]:
    strategy, value = _node_lookup_strategy(node_code)

    sql_by_node_code = """
        SELECT id, node_code, hostname, display_name, enabled
        FROM worker_nodes
        WHERE LOWER(node_code) = LOWER(%s)
        ORDER BY id
        LIMIT 1
    """
    sql_by_hostname = """
        SELECT id, node_code, hostname, display_name, enabled
        FROM worker_nodes
        WHERE LOWER(hostname) = LOWER(%s)
        ORDER BY id
        LIMIT 1
    """

    with conn.cursor() as cur:
        if strategy in {"env", "cli"}:
            cur.execute(sql_by_node_code, (value,))
        else:
            cur.execute(sql_by_hostname, (value,))
        row = cur.fetchone()

    if not row:
        raise SettingsLoaderError(
            f"worker node not found using {strategy} lookup: {value}"
        )

    return {
        "id": row[0],
        "node_code": row[1],
        "hostname": row[2],
        "display_name": row[3],
        "enabled": row[4],
        "lookup_source": strategy,
        "lookup_value": value,
    }


def generate_worker_id(
    *,
    hostname: str,
    worker_type: str,
    worker_number: int | None = None,
    store_code: str | None = None,
    explicit_worker_id: str | None = None,
) -> str:
    explicit = str(explicit_worker_id or "").strip()
    if explicit:
        return explicit

    hostname_value = str(hostname or "").strip()
    if not hostname_value:
        raise SettingsLoaderError("hostname is empty")

    if worker_type == WORKER_TYPE_AMAZON:
        if worker_number is None:
            raise SettingsLoaderError("worker_number is required for amazon_check")
        return f"{hostname_value}-amazon-{worker_number}"

    if worker_type == WORKER_TYPE_RAKUTEN:
        store_value = str(store_code or "").strip()
        if not store_value:
            raise SettingsLoaderError("store_code is required for rakuten_update")
        return f"{hostname_value}-{store_value}"

    raise SettingsLoaderError(f"unsupported worker_type: {worker_type}")


def _validate_type(name: str, value: Any, rule: SettingRule) -> Any:
    if rule.expected_type == "bool":
        if not isinstance(value, bool):
            raise SettingsLoaderError(f"{name} must be boolean")
        return value

    if rule.expected_type == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            raise SettingsLoaderError(f"{name} must be integer")
        numeric = value
    elif rule.expected_type == "float":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SettingsLoaderError(f"{name} must be numeric")
        numeric = float(value)
    else:
        raise SettingsLoaderError(f"unsupported expected_type for {name}: {rule.expected_type}")

    if rule.minimum is not None:
        if rule.exclusive_minimum:
            if numeric <= rule.minimum:
                raise SettingsLoaderError(f"{name} must be > {rule.minimum}")
        else:
            if numeric < rule.minimum:
                raise SettingsLoaderError(f"{name} must be >= {rule.minimum}")

    return numeric if rule.expected_type == "float" else int(numeric)


def validate_settings_json(worker_type: str, settings_json: Any) -> dict[str, Any]:
    normalized_worker_type = _normalize_worker_type(worker_type)

    if not isinstance(settings_json, dict):
        raise SettingsLoaderError("settings_json must be an object")

    allowed_rules = SETTINGS_RULES[normalized_worker_type]
    unknown_keys = sorted(set(settings_json.keys()) - set(allowed_rules.keys()))
    if unknown_keys:
        raise SettingsLoaderError(
            f"unknown settings_json keys for {normalized_worker_type}: {', '.join(unknown_keys)}"
        )

    validated: dict[str, Any] = {}
    for key, value in settings_json.items():
        validated[key] = _validate_type(key, value, allowed_rules[key])
    return validated


def _load_worker_row(
    conn,
    *,
    node_id: int,
    worker_type: str,
    worker_number: int | None = None,
    store_code: str | None = None,
) -> dict[str, Any]:
    normalized_worker_type = _normalize_worker_type(worker_type)
    where = [
        "wc.node_id = %s",
        "wc.worker_type = %s",
    ]
    params: list[Any] = [node_id, normalized_worker_type]

    if normalized_worker_type == WORKER_TYPE_AMAZON:
        if worker_number is None:
            raise SettingsLoaderError("--worker-number is required for amazon_check")
        where.append("wc.worker_number = %s")
        params.append(worker_number)
    else:
        store_value = str(store_code or "").strip()
        if not store_value:
            raise SettingsLoaderError("--store is required for rakuten_update")
        where.append("LOWER(s.store_code) = LOWER(%s)")
        params.append(store_value)

    sql = f"""
        SELECT
            wc.id AS worker_config_id,
            wn.id AS node_id,
            wn.node_code,
            wn.hostname,
            wc.worker_type,
            wc.worker_number,
            wc.store_id,
            s.store_code,
            wc.enabled,
            wc.desired_state,
            wc.settings_json,
            wc.revision
        FROM worker_configs wc
        JOIN worker_nodes wn ON wn.id = wc.node_id
        LEFT JOIN stores s ON s.id = wc.store_id
        WHERE {" AND ".join(where)}
        ORDER BY wc.id
        LIMIT 1
    """

    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()

    if not row:
        raise SettingsLoaderError(
            f"worker config not found: worker_type={normalized_worker_type}, "
            f"worker_number={worker_number}, store_code={store_code}"
        )

    raw_settings = row[10]
    settings_json = raw_settings if isinstance(raw_settings, dict) else {}

    return {
        "worker_config_id": row[0],
        "node_id": row[1],
        "node_code": row[2],
        "hostname": row[3],
        "worker_type": row[4],
        "worker_number": row[5],
        "store_id": row[6],
        "store_code": row[7],
        "enabled": row[8],
        "desired_state": row[9],
        "settings_json": validate_settings_json(normalized_worker_type, settings_json),
        "revision": row[11],
    }


def resolve_setting_values(
    *,
    worker_type: str,
    db_settings: dict[str, Any],
    cli_overrides: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    normalized_worker_type = _normalize_worker_type(worker_type)
    defaults = default_settings_for_worker_type(normalized_worker_type)
    db_validated = validate_settings_json(normalized_worker_type, db_settings)
    cli_input = dict(cli_overrides or {})
    cli_validated = validate_settings_json(normalized_worker_type, cli_input)

    resolved: dict[str, dict[str, Any]] = {}
    for key, default_value in defaults.items():
        if key in cli_validated:
            resolved[key] = {"value": cli_validated[key], "source": SOURCE_CLI}
        elif key in db_validated:
            resolved[key] = {"value": db_validated[key], "source": SOURCE_DB}
        else:
            resolved[key] = {"value": default_value, "source": SOURCE_DEFAULT}
    return resolved


def load_resolved_worker_settings(
    *,
    worker_type: str,
    worker_number: int | None = None,
    store_code: str | None = None,
    node_code: str | None = None,
    explicit_worker_id: str | None = None,
    cli_overrides: dict[str, Any] | None = None,
    db_name: str | None = None,
) -> dict[str, Any]:
    conn_kwargs: dict[str, Any] = {"options": "-c default_transaction_read_only=on"}
    if db_name:
        conn_kwargs["dbname"] = db_name

    conn = connect_db(**conn_kwargs)
    try:
        node = resolve_node(conn, node_code=node_code)
        worker = _load_worker_row(
            conn,
            node_id=node["id"],
            worker_type=worker_type,
            worker_number=worker_number,
            store_code=store_code,
        )
    finally:
        conn.close()

    resolved_settings = resolve_setting_values(
        worker_type=worker["worker_type"],
        db_settings=worker["settings_json"],
        cli_overrides=cli_overrides,
    )

    worker_id = generate_worker_id(
        hostname=worker["hostname"],
        worker_type=worker["worker_type"],
        worker_number=worker["worker_number"],
        store_code=worker["store_code"],
        explicit_worker_id=explicit_worker_id,
    )

    return {
        "worker_config_id": worker["worker_config_id"],
        "worker_id": worker_id,
        "node_id": worker["node_id"],
        "node_code": worker["node_code"],
        "hostname": worker["hostname"],
        "worker_type": worker["worker_type"],
        "worker_number": worker["worker_number"],
        "store_id": worker["store_id"],
        "store_code": worker["store_code"],
        "enabled": worker["enabled"],
        "desired_state": worker["desired_state"],
        "settings_json": worker["settings_json"],
        "revision": worker["revision"],
        "resolved_settings": resolved_settings,
        "node_lookup": {
            "source": node["lookup_source"],
            "value": node["lookup_value"],
        },
    }


def format_resolved_settings_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False)
