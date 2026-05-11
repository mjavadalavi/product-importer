from __future__ import annotations

from typing import Any


def _extract_category_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        value = payload.get("data")
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _category_unit_type(item: dict[str, Any]) -> Any:
    for key in (
        "unit_type",
        "unitType",
        "unit_type_id",
        "unitTypeId",
        "default_unit_type",
        "defaultUnitType",
        "sale_unit_type",
        "saleUnitType",
    ):
        value = item.get(key)
        if value not in (None, ""):
            return value
    for key in ("unit", "default_unit", "defaultUnit", "sale_unit", "saleUnit"):
        unit = item.get(key)
        if unit not in (None, ""):
            return unit
    for key, value in item.items():
        normalized_key = key.replace("_", "").lower()
        if "unit" in normalized_key and "type" in normalized_key and value not in (None, ""):
            return value
    return None


def _normalize_unit_type_id(value: Any) -> int | None:
    from app.services.basalam.payload import UNIT_TYPE_ID_ALIASES

    if isinstance(value, dict):
        value = value.get("id")
    try:
        unit_type_id = int(value)
    except (TypeError, ValueError):
        return None
    return UNIT_TYPE_ID_ALIASES.get(unit_type_id, unit_type_id)


def _flatten_categories(items: list[dict[str, Any]], path: str = "") -> list[dict[str, Any]]:
    flat: list[dict[str, Any]] = []
    for item in items:
        title = str(item.get("title") or "")
        current_path = f"{path} / {title}" if path else title
        category_id = item.get("id")
        children = item.get("children")
        if category_id is not None:
            flat.append(
                {
                    "id": category_id,
                    "title": title,
                    "path": current_path,
                    "unit_type": _category_unit_type(item),
                    "is_leaf": not bool(children),
                }
            )
        if isinstance(children, list) and children:
            flat.extend(_flatten_categories([child for child in children if isinstance(child, dict)], current_path))
    return flat
