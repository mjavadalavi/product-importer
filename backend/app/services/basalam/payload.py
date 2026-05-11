from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.core.exceptions import BasalamError

VALID_UNIT_TYPE_IDS = {
    6375,
    6374,
    6373,
    6332,
    6331,
    6330,
    6329,
    6328,
    6327,
    6326,
    6325,
    6324,
    6323,
    6322,
    6321,
    6320,
    6319,
    6318,
    6317,
    6316,
    6315,
    6314,
    6313,
    6312,
    6311,
    6310,
    6309,
    6308,
    6307,
    6306,
    6305,
    6304,
    6392,
    6438,
    6466,
}
UNIT_TYPE_ID_ALIASES = {
    5060: 6306,
    5130: 6305,
    5135: 6312,
}
RIALS_PER_TOMAN = 10


def _clean_payload(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, child in value.items():
            cleaned_child = _clean_payload(child)
            if cleaned_child in (None, "", [], {}):
                continue
            cleaned[key] = cleaned_child
        return cleaned
    if isinstance(value, list):
        return [_clean_payload(item) for item in value if _clean_payload(item) not in (None, "", [], {})]
    return value


def _toman_to_provider_rial(value: Any) -> Any:
    if value in (None, ""):
        return value
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return value
    return int(round(numeric * RIALS_PER_TOMAN))


def _normalize_unit_type_id(value: Any) -> int | None:
    if isinstance(value, dict):
        value = value.get("id")
    try:
        unit_type_id = int(value)
    except (TypeError, ValueError):
        return None
    return UNIT_TYPE_ID_ALIASES.get(unit_type_id, unit_type_id)


def _convert_price_fields_to_provider_unit(payload: dict[str, Any]) -> None:
    for field in ("primary_price", "price"):
        if field in payload:
            payload[field] = _toman_to_provider_rial(payload[field])
    variants = payload.get("variants")
    if not isinstance(variants, list):
        return
    for variant in variants:
        if not isinstance(variant, dict):
            continue
        for field in ("primary_price", "price"):
            if field in variant:
                variant[field] = _toman_to_provider_rial(variant[field])


def normalize_product_payload(product: dict[str, Any], photo_ids: list[int]) -> dict[str, Any]:
    settings = get_settings()
    payload = dict(product)
    _convert_price_fields_to_provider_unit(payload)
    ordered_photo_ids = [int(photo_id) for photo_id in photo_ids if photo_id]
    if not ordered_photo_ids:
        raise BasalamError("حداقل یک عکس محصول لازم است.", 400)
    payload["photo"] = ordered_photo_ids[0]
    payload.setdefault("status", settings.basalam_product_status)
    weight = payload.get("weight")
    package_weight = payload.get("package_weight")
    if weight is not None:
        try:
            weight_value = float(weight)
            package_weight_value = float(package_weight) if package_weight is not None else None
            if package_weight_value is None or package_weight_value <= weight_value:
                payload["package_weight"] = int(weight_value + 1)
        except (TypeError, ValueError):
            pass
    unit_type = payload.get("unit_type")
    unit_quantity = payload.get("unit_quantity")
    unit_type_value = _normalize_unit_type_id(unit_type)
    if (
        unit_type_value is None
        or unit_type_value not in VALID_UNIT_TYPE_IDS
        or unit_quantity in (None, "")
    ):
        payload.pop("unit_type", None)
        payload.pop("unit_quantity", None)
    else:
        payload["unit_type"] = unit_type_value
    existing_photos = payload.get("photos")
    if isinstance(existing_photos, list):
        for photo_id in existing_photos:
            try:
                numeric_photo_id = int(photo_id)
            except (TypeError, ValueError):
                continue
            if numeric_photo_id not in ordered_photo_ids:
                ordered_photo_ids.append(numeric_photo_id)
    payload["photos"] = ordered_photo_ids
    return _clean_payload(payload)
