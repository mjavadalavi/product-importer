from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.services import basalam, openrouter


APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
FONT_DIR = APP_DIR / "font"
CATEGORY_CACHE_TTL_SECONDS = 60 * 60
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

app = FastAPI(title="Basalam Product Importer MVP")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/font", StaticFiles(directory=FONT_DIR), name="font")

_categories_cache: dict[str, Any] = {"expires_at": 0, "payload": None}


class TokenRequest(BaseModel):
    token: str = Field(min_length=1)


class CategoryAttributesRequest(BaseModel):
    token: str | None = None
    vendor_id: int | None = None


class AnalyzeRequest(BaseModel):
    openrouter_key: str = Field(min_length=1)
    image_data_url: str = Field(min_length=20)
    categories: list[dict[str, Any]] = Field(default_factory=list)
    model: str = openrouter.DEFAULT_MODEL


class ImageEnhancementRequest(BaseModel):
    openrouter_key: str = Field(min_length=1)
    image_data_url: str = Field(min_length=20)
    filename: str = "product.jpg"
    model: str = openrouter.DEFAULT_IMAGE_MODEL


class PriceSuggestionRequest(BaseModel):
    token: str | None = None
    q: str = Field(min_length=1)
    name: str | None = None
    keywords: str | None = None
    category_title: str | None = None
    category_id: int | None = None
    weight: float | None = None
    unit_quantity: float | None = None
    unit_type: int | None = None
    rows: int = 40


class ProductImageRequest(BaseModel):
    image_data_url: str = Field(min_length=20)
    filename: str = "product.jpg"


class SubmitProductRequest(BaseModel):
    token: str = Field(min_length=1)
    vendor_id: int
    product_id: int | None = None
    image_data_url: str | None = None
    filename: str = "product.jpg"
    images: list[ProductImageRequest] = Field(default_factory=list)
    product: dict[str, Any]


def _handle_service_error(exc: Exception) -> HTTPException:
    if isinstance(exc, basalam.BasalamError):
        return HTTPException(
            status_code=exc.status_code,
            detail={"message": str(exc), "provider_detail": exc.detail},
        )
    if isinstance(exc, openrouter.OpenRouterError):
        return HTTPException(
            status_code=exc.status_code,
            detail={"message": str(exc), "provider_detail": exc.detail},
        )
    return HTTPException(status_code=500, detail={"message": "خطای نامشخص سرور"})


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
    return int(round(numeric * basalam.RIALS_PER_TOMAN))


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


def _normalize_product_payload(product: dict[str, Any], photo_ids: list[int]) -> dict[str, Any]:
    payload = dict(product)
    _convert_price_fields_to_provider_unit(payload)
    ordered_photo_ids = [int(photo_id) for photo_id in photo_ids if photo_id]
    if not ordered_photo_ids:
        raise basalam.BasalamError("حداقل یک عکس محصول لازم است.", 400)
    payload["photo"] = ordered_photo_ids[0]
    payload.setdefault("status", 2976)
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


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/basalam/me")
async def basalam_me(request: TokenRequest) -> Any:
    try:
        return await basalam.get_current_user(request.token)
    except Exception as exc:
        raise _handle_service_error(exc) from exc


@app.get("/api/basalam/categories")
async def basalam_categories(token: str | None = None) -> dict[str, Any]:
    now = time.time()
    cached = _categories_cache.get("payload")
    if cached and _categories_cache.get("expires_at", 0) > now:
        return cached
    try:
        raw = await basalam.get_categories(token)
    except Exception as exc:
        raise _handle_service_error(exc) from exc
    items = _extract_category_items(raw)
    payload = {"raw": raw, "flat": _flatten_categories(items)}
    _categories_cache["payload"] = payload
    _categories_cache["expires_at"] = now + CATEGORY_CACHE_TTL_SECONDS
    return payload


@app.get("/api/basalam/categories/{category_id}/attributes")
async def basalam_category_attributes(
    category_id: int,
    token: str | None = None,
    vendor_id: int | None = None,
) -> Any:
    try:
        return await basalam.get_category_attributes(category_id, token=token, vendor_id=vendor_id)
    except Exception as exc:
        raise _handle_service_error(exc) from exc


@app.post("/api/ai/analyze")
async def ai_analyze(request: AnalyzeRequest) -> Any:
    try:
        return await openrouter.analyze_product_image(
            openrouter_key=request.openrouter_key,
            image_data_url=request.image_data_url,
            categories=request.categories,
            model=request.model,
        )
    except Exception as exc:
        raise _handle_service_error(exc) from exc


@app.post("/api/ai/enhance-image")
async def ai_enhance_image(request: ImageEnhancementRequest) -> Any:
    try:
        return await openrouter.enhance_product_image(
            openrouter_key=request.openrouter_key,
            image_data_url=request.image_data_url,
            filename=request.filename,
            model=request.model,
        )
    except Exception as exc:
        raise _handle_service_error(exc) from exc


@app.post("/api/basalam/price-suggestion")
async def basalam_price_suggestion(request: PriceSuggestionRequest) -> Any:
    try:
        search_response = await basalam.search_products(
            request.q,
            token=request.token,
            rows=request.rows,
            filters={},
        )
        suggestion = basalam.build_price_suggestion(
            search_response,
            category_id=request.category_id,
            product_type=request.name or request.q,
            keywords=request.keywords,
            category_title=request.category_title,
            weight=request.weight,
            unit_quantity=request.unit_quantity,
            unit_type=request.unit_type,
        )
        return {
            "suggested_price": suggestion.suggested_price,
            "currency_unit": basalam.APP_PRICE_UNIT,
            "source_currency_unit": basalam.PROVIDER_PRICE_UNIT,
            "sample_count": suggestion.sample_count,
            "min_price": suggestion.min_price,
            "max_price": suggestion.max_price,
            "median_price": suggestion.median_price,
            "confidence": suggestion.confidence,
            "source": suggestion.source,
            "samples": suggestion.samples,
            "criteria": suggestion.criteria,
            "warnings": suggestion.warnings,
        }
    except Exception as exc:
        raise _handle_service_error(exc) from exc


@app.post("/api/basalam/submit-product")
async def basalam_submit_product(request: SubmitProductRequest) -> Any:
    try:
        image_requests = request.images
        if not image_requests and request.image_data_url:
            image_requests = [ProductImageRequest(image_data_url=request.image_data_url, filename=request.filename)]
        if not image_requests:
            raise basalam.BasalamError("حداقل یک عکس محصول لازم است.", 400)

        upload_responses = []
        photo_ids = []
        for image in image_requests:
            upload_response = await basalam.upload_product_photo(
                request.token,
                image.image_data_url,
                image.filename,
            )
            photo_id = upload_response.get("id")
            if not photo_id:
                raise basalam.BasalamError("شناسه فایل آپلودشده در پاسخ باسلام نبود.", 502, upload_response)
            upload_responses.append(upload_response)
            photo_ids.append(int(photo_id))

        payload = _normalize_product_payload(request.product, photo_ids)
        if request.product_id:
            product_response = await basalam.update_product(request.token, request.product_id, payload)
        else:
            product_response = await basalam.create_product(request.token, request.vendor_id, payload)
        return {
            "mode": "update" if request.product_id else "create",
            "uploads": upload_responses,
            "product": product_response,
            "payload": payload,
        }
    except Exception as exc:
        raise _handle_service_error(exc) from exc


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Any, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
