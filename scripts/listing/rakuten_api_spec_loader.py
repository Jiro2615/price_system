from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REQUIRED_TOP_LEVEL_KEYS = {
    "meta",
    "item_api",
    "inventory_api",
    "image_api",
    "genre_attributes",
    "delete_or_hide",
}


def load_rakuten_api_spec(path: Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("Rakuten API spec must be a JSON object")

    missing = sorted(REQUIRED_TOP_LEVEL_KEYS - set(data.keys()))
    if missing:
        raise RuntimeError(f"Rakuten API spec is missing keys: {', '.join(missing)}")

    for key in REQUIRED_TOP_LEVEL_KEYS:
        if not isinstance(data.get(key), dict):
            raise RuntimeError(f"Rakuten API spec {key} must be an object")

    return data


def build_confirmed_specifications(api_spec: dict[str, Any], *, genre_id: int | None) -> list[dict[str, Any]]:
    confirmed: list[dict[str, Any]] = []

    item_api = api_spec.get("item_api") or {}
    if item_api.get("confirmed") and item_api.get("endpoint") and item_api.get("auth_type"):
        confirmed.append(
            {
                "scope": "item_api",
                "name": "item_api_transport",
                "details": {
                    "endpoint": item_api.get("endpoint"),
                    "method": item_api.get("method"),
                    "auth_type": item_api.get("auth_type"),
                },
            }
        )

    inventory_api = api_spec.get("inventory_api") or {}
    if inventory_api.get("confirmed") and inventory_api.get("endpoint") and inventory_api.get("auth_type"):
        confirmed.append(
            {
                "scope": "inventory_api",
                "name": "inventory_api_transport",
                "details": {
                    "endpoint": inventory_api.get("endpoint"),
                    "method": inventory_api.get("method"),
                    "auth_type": inventory_api.get("auth_type"),
                },
            }
        )

    image_api = api_spec.get("image_api") or {}
    if image_api.get("transport_confirmed") and image_api.get("endpoint") and image_api.get("auth_type"):
        confirmed.append(
            {
                "scope": "image_api",
                "name": "image_api_transport",
                "details": {
                    "endpoint": image_api.get("endpoint"),
                    "method": image_api.get("method"),
                    "auth_type": image_api.get("auth_type"),
                    "content_type": image_api.get("content_type"),
                    "response_type": image_api.get("response_type"),
                    "response_file_id_field": image_api.get("response_file_id_field"),
                },
            }
        )
    if image_api.get("destination_confirmed"):
        cabinet_destination = image_api.get("cabinet_destination") or {}
        if cabinet_destination.get("shop_url"):
            confirmed.append(
                {
                    "scope": "image_api.cabinet_destination",
                    "name": "cabinet_shop_url",
                    "details": {"shop_url": cabinet_destination.get("shop_url")},
                }
            )
        if cabinet_destination.get("folder_path"):
            confirmed.append(
                {
                    "scope": "image_api.cabinet_destination",
                    "name": "cabinet_folder_path",
                    "details": {"folder_path": cabinet_destination.get("folder_path")},
                }
            )
        if cabinet_destination.get("folder_id"):
            confirmed.append(
                {
                    "scope": "image_api.cabinet_destination",
                    "name": "cabinet_folder_id",
                    "details": {"folder_id": cabinet_destination.get("folder_id")},
                }
            )
        confirmed.append(
            {
                "scope": "image_api.cabinet_destination",
                "name": "cabinet_destination",
                "details": cabinet_destination,
            }
        )

    if genre_id is not None:
        genre_rules = (api_spec.get("genre_attributes") or {}).get(str(genre_id)) or {}
        for attribute_name, rule in genre_rules.items():
            if isinstance(rule, dict) and rule.get("confirmed"):
                confirmed.append(
                    {
                        "scope": f"genre_attributes.{genre_id}",
                        "name": attribute_name,
                        "details": rule,
                    }
                )

    if (api_spec.get("delete_or_hide") or {}).get("confirmed"):
        confirmed.append(
            {
                "scope": "delete_or_hide",
                "name": "pilot_cleanup",
                "details": api_spec.get("delete_or_hide"),
            }
        )

    return confirmed


def build_unresolved_specifications(api_spec: dict[str, Any], *, genre_id: int | None) -> list[dict[str, Any]]:
    unresolved: list[dict[str, Any]] = []

    item_api = api_spec.get("item_api") or {}
    if not item_api.get("confirmed") or not item_api.get("endpoint") or not item_api.get("auth_type"):
        unresolved.append(
            {
                "scope": "item_api",
                "name": "item_api_transport",
                "reason": "item API transport が未確定です",
                "details": item_api,
            }
        )

    inventory_api = api_spec.get("inventory_api") or {}
    if not inventory_api.get("confirmed") or not inventory_api.get("endpoint") or not inventory_api.get("auth_type"):
        unresolved.append(
            {
                "scope": "inventory_api",
                "name": "inventory_api_transport",
                "reason": "inventory API transport が未確定です",
                "details": inventory_api,
            }
        )

    image_api = api_spec.get("image_api") or {}
    if not image_api.get("transport_confirmed") or not image_api.get("endpoint") or not image_api.get("auth_type"):
        unresolved.append(
            {
                "scope": "image_api",
                "name": "image_api_transport",
                "reason": "image API transport が未確定です",
                "details": image_api,
            }
        )
    if not image_api.get("destination_confirmed"):
        unresolved.append(
            {
                "scope": "image_api",
                "name": "cabinet_destination",
                "reason": "CABINET upload destination runtime config が未確定です",
                "details": {
                    "required_runtime_config": list(image_api.get("required_runtime_config") or []),
                    "item_location_build_method": image_api.get("item_location_build_method"),
                },
            }
        )

    if genre_id is not None:
        genre_rules = (api_spec.get("genre_attributes") or {}).get(str(genre_id)) or {}
        for attribute_name, rule in genre_rules.items():
            if isinstance(rule, dict) and not rule.get("confirmed"):
                unresolved.append(
                    {
                        "scope": f"genre_attributes.{genre_id}",
                        "name": attribute_name,
                        "reason": "属性仕様が未確定です",
                        "details": rule,
                    }
                )

    delete_or_hide = api_spec.get("delete_or_hide") or {}
    if not delete_or_hide.get("confirmed"):
        unresolved.append(
            {
                "scope": "delete_or_hide",
                "name": "pilot_cleanup",
                "reason": "パイロット後の cleanup 手順が未確定です",
                "details": delete_or_hide,
            }
        )

    return unresolved
