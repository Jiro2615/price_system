import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BASE_DIR.parent / ".env"


def _get_env_first(*names: str) -> str:
    for name in names:
        value = os.getenv(name)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return ""


def get_db_config() -> dict[str, object]:
    load_dotenv(ENV_PATH)

    host = _get_env_first("PRICE_SYSTEM_DB_HOST", "DB_HOST") or "localhost"
    port_text = _get_env_first("PRICE_SYSTEM_DB_PORT", "DB_PORT") or "5432"
    dbname = _get_env_first("PRICE_SYSTEM_DB_NAME", "DB_NAME") or "price_system"
    user = _get_env_first("PRICE_SYSTEM_DB_USER", "DB_USER") or "price_app"
    password = _get_env_first("PRICE_SYSTEM_DB_PASSWORD", "DB_PASSWORD", "PGPASSWORD")

    if not password:
        raise RuntimeError(
            f"DB password is empty: {ENV_PATH} "
            "(set one of PRICE_SYSTEM_DB_PASSWORD / DB_PASSWORD / PGPASSWORD)"
        )

    try:
        port = int(port_text)
    except ValueError as e:
        raise RuntimeError(
            f"DB port is not numeric: {port_text} "
            "(check PRICE_SYSTEM_DB_PORT / DB_PORT)"
        ) from e

    return {
        "host": host,
        "port": port,
        "dbname": dbname,
        "user": user,
        "password": password,
    }


def connect_db(**kwargs):
    params = get_db_config()
    params.update(kwargs)
    return psycopg.connect(**params)
