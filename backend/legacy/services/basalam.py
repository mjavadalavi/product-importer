from __future__ import annotations

import base64
import os
import re
import socket
import statistics
from dataclasses import dataclass
from typing import Any

import httpx


BASALAM_BASE_URL = "https://openapi.basalam.com"
LOCAL_PROXY_PORTS = (1087, 7890, 1080)


class BasalamError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502, detail: Any | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


@dataclass
class PriceSuggestion:
    suggested_price: int | None
    sample_count: int
    min_price: int | None
    max_price: int | None
    median_price: int | None
    confidence: str
    source: str
    samples: list[dict[str, Any]]
    criteria: dict[str, Any]
    warnings: list[str]


MASS_UNIT_TO_GRAMS = {
    6305: 1000.0,  # کیلوگرم
    6306: 1.0,  # گرم
    6309: 4.608,  # مثقال
    6314: 28.3495,  # انس
    6330: 75.0,  # سیر
    6438: 0.001,  # سوت
    6466: 0.2,  # قیراط
}
UNIT_TYPE_ID_ALIASES = {
    5060: 6306,  # گرم در خروجی دسته‌ها
    5130: 6305,  # کیلوگرم در خروجی دسته‌ها
    5135: 6312,  # میلی‌لیتر در خروجی دسته‌ها
}
RIALS_PER_TOMAN = 10
PRICE_ROUNDING_STEP = 1_000
APP_PRICE_UNIT = "toman"
PROVIDER_PRICE_UNIT = "rial"

PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

STOPWORDS = {
    "و",
    "یا",
    "از",
    "با",
    "به",
    "برای",
    "در",
    "این",
    "آن",
    "یک",
    "عدد",
    "عددی",
    "محصول",
    "جدید",
    "اصل",
    "اعلا",
    "درجه",
    "گرم",
    "گرمی",
    "کیلو",
    "کیلوگرم",
    "بسته",
    "بسته‌ای",
    "متری",
}


def auth_headers(token: str | None = None) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _configured_proxy_url() -> str | None:
    for key in ("BASALAM_PROXY_URL", "HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"):
        value = os.getenv(key)
        if value:
            return value
    return None


def _is_local_port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
            return True
    except OSError:
        return False


def _proxy_candidates() -> list[str | None]:
    candidates: list[str | None] = []
    configured = _configured_proxy_url()
    if configured:
        candidates.append(configured)
    for port in LOCAL_PROXY_PORTS:
        if _is_local_port_open(port):
            proxy_url = f"http://127.0.0.1:{port}"
            if proxy_url not in candidates:
                candidates.append(proxy_url)
    candidates.append(None)
    return candidates


async def _send_request(
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    json: Any | None,
    data: Any | None,
    files: Any | None,
    params: dict[str, Any] | None,
    timeout: float,
    proxy: str | None,
) -> httpx.Response:
    async with httpx.AsyncClient(timeout=timeout, proxy=proxy, trust_env=proxy is None) as client:
        return await client.request(
            method,
            url,
            headers=headers,
            json=json,
            data=data,
            files=files,
            params=params,
        )


async def _request(
    method: str,
    path: str,
    *,
    token: str | None = None,
    json: Any | None = None,
    data: Any | None = None,
    files: Any | None = None,
    params: dict[str, Any] | None = None,
    timeout: float = 35.0,
) -> Any:
    url = f"{BASALAM_BASE_URL}{path}"
    headers = auth_headers(token)
    attempts: list[dict[str, str | None]] = []
    last_error: httpx.HTTPError | None = None
    for proxy in _proxy_candidates():
        attempts.append({"proxy": proxy or "direct"})
        try:
            response = await _send_request(
                method,
                url,
                headers=headers,
                json=json,
                data=data,
                files=files,
                params=params,
                timeout=timeout,
                proxy=proxy,
            )
        except httpx.TimeoutException as exc:
            last_error = exc
            continue
        except httpx.HTTPError as exc:
            last_error = exc
            continue
        break
    else:
        if isinstance(last_error, httpx.TimeoutException):
            raise BasalamError("درخواست باسلام بیش از حد طول کشید.", 504, {"attempts": attempts}) from last_error
        raise BasalamError(
            "اتصال به باسلام ناموفق بود.",
            502,
            {"attempts": attempts, "error": str(last_error) if last_error else None},
        ) from last_error

    if response.status_code >= 400:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text
        raise BasalamError("خطای API باسلام", response.status_code, detail)

    if not response.content:
        return {}

    try:
        return response.json()
    except ValueError as exc:
        raise BasalamError("پاسخ باسلام JSON معتبر نبود.", 502, response.text) from exc


async def get_current_user(token: str) -> dict[str, Any]:
    return await _request("GET", "/v1/users/me", token=token)


async def get_categories(token: str | None = None) -> dict[str, Any]:
    return await _request("GET", "/v1/categories", token=token)


async def get_category_attributes(
    category_id: int,
    token: str | None = None,
    vendor_id: int | None = None,
    exclude_multi_selects: bool = True,
) -> dict[str, Any]:
    params: dict[str, Any] = {"exclude_multi_selects": str(exclude_multi_selects).lower()}
    if vendor_id:
        params["vendor_id"] = vendor_id
    return await _request(
        "GET",
        f"/v1/categories/{category_id}/attributes",
        token=token,
        params=params,
    )


async def search_products(
    query: str,
    *,
    token: str | None = None,
    rows: int = 24,
    start: int = 0,
    filters: dict[str, Any] | None = None,
) -> Any:
    payload = {
        "q": query,
        "rows": rows,
        "start": start,
        "filters": filters or {},
    }
    return await _request("POST", "/v1/products/search", token=token, json=payload)


def _unwrap_search_items(response: Any) -> list[dict[str, Any]]:
    if isinstance(response, list):
        return [item for item in response if isinstance(item, dict)]
    if isinstance(response, dict):
        for key in ("data", "products", "items", "results", "hits"):
            value = response.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        nested = response.get("result")
        if isinstance(nested, list):
            return [item for item in nested if isinstance(item, dict)]
        if isinstance(nested, dict):
            return _unwrap_search_items(nested)
    return []


def _is_available(item: dict[str, Any]) -> bool:
    flags = [
        item.get("IsAvailable"),
        item.get("isAvailable"),
        item.get("IsSaleable"),
        item.get("isSaleable"),
        item.get("canAddToCart"),
    ]
    present_flags = [flag for flag in flags if flag is not None]
    if present_flags and not all(bool(flag) for flag in present_flags):
        return False
    status = item.get("status")
    if isinstance(status, dict):
        title = str(status.get("title") or status.get("name") or "")
        if title and "ناموجود" in title:
            return False
    return True


def _category_matches(item: dict[str, Any], category_id: int | None) -> bool:
    if not category_id:
        return True
    candidate_ids = [
        item.get("new_categoryId"),
        item.get("newCategoryId"),
        item.get("categoryId"),
        item.get("category_id"),
    ]
    return any(str(value) == str(category_id) for value in candidate_ids if value is not None)


def _price_of(item: dict[str, Any]) -> int | None:
    for key in ("primaryPrice", "primary_price", "price"):
        value = item.get(key)
        if value in (None, ""):
            continue
        try:
            price = int(float(value))
        except (TypeError, ValueError):
            continue
        if price > 0:
            return int(round(price / RIALS_PER_TOMAN))
    return None


def _number_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(str(value).translate(PERSIAN_DIGITS).replace(",", "."))
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _unit_type_id(value: Any) -> int | None:
    if isinstance(value, dict):
        value = value.get("id")
    try:
        unit_id = int(value)
    except (TypeError, ValueError):
        return None
    return UNIT_TYPE_ID_ALIASES.get(unit_id, unit_id)


def _unit_quantity_to_grams(quantity: Any, unit_type: Any) -> float | None:
    value = _number_or_none(quantity)
    unit_id = _unit_type_id(unit_type)
    if value is None or unit_id not in MASS_UNIT_TO_GRAMS:
        return None
    return value * MASS_UNIT_TO_GRAMS[unit_id]


def _normalize_text(value: Any) -> str:
    return (
        str(value or "")
        .translate(PERSIAN_DIGITS)
        .replace("ي", "ی")
        .replace("ك", "ک")
        .replace("‌", " ")
        .lower()
    )


def _tokens(value: Any) -> set[str]:
    text = _normalize_text(value)
    return {
        token
        for token in re.findall(r"[\wآ-ی]+", text)
        if len(token) > 1 and token not in STOPWORDS and not token.isdigit()
    }


def _extract_weight_from_text(*values: Any) -> tuple[float | None, str]:
    text = " ".join(_normalize_text(value) for value in values if value)
    if not text:
        return None, ""
    if "نیم کیلو" in text or "نیم‌کیلو" in text:
        return 500.0, "title"
    patterns = [
        (r"(\d+(?:[\.,]\d+)?)\s*(?:کیلوگرم|کیلو|kg|kilo)\b", 1000.0),
        (r"(\d+(?:[\.,]\d+)?)\s*(?:گرم|گرمی|g|gr)\b", 1.0),
        (r"(\d+(?:[\.,]\d+)?)\s*(?:مثقال)\b", 4.608),
        (r"(\d+(?:[\.,]\d+)?)\s*(?:سیر)\b", 75.0),
    ]
    for pattern, multiplier in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        amount = _number_or_none(match.group(1))
        if amount:
            return amount * multiplier, "title"
    return None, ""


def _candidate_weight_grams(item: dict[str, Any]) -> tuple[float | None, str]:
    unit_weight = _unit_quantity_to_grams(
        _first_value(item, "unit_quantity", "unitQuantity"),
        _first_value(item, "unit_type", "unitType"),
    )
    if unit_weight:
        return unit_weight, "unit_quantity"

    for key in ("net_weight", "netWeight", "net_weight_decimal", "netWeightDecimal", "weight"):
        weight = _number_or_none(item.get(key))
        if weight:
            return weight, key

    return _extract_weight_from_text(
        _first_value(item, "name", "title", "product_title", "productTitle"),
        _first_value(item, "brief", "summary", "description"),
    )


def _target_weight_grams(
    *,
    weight: float | None = None,
    unit_quantity: float | None = None,
    unit_type: int | None = None,
) -> tuple[float | None, str]:
    unit_weight = _unit_quantity_to_grams(unit_quantity, unit_type)
    if unit_weight:
        return unit_weight, "unit_quantity"
    if weight and weight > 0:
        return float(weight), "weight"
    return None, ""


def _first_value(item: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return None


def _nested_value(item: dict[str, Any], key: str, *nested_keys: str) -> Any:
    value = item.get(key)
    if not isinstance(value, dict):
        return None
    return _first_value(value, *nested_keys)


def _product_url(item: dict[str, Any], product_id: Any) -> str:
    url = _first_value(item, "url", "web_url", "webUrl", "share_url", "shareUrl")
    if not url and product_id:
        url = f"https://basalam.com/p/{product_id}"
    if not url:
        return ""
    url = str(url)
    if url.startswith("/"):
        return f"https://basalam.com{url}"
    return url


def _type_score(item: dict[str, Any], target_tokens: set[str], exact_phrase: str) -> tuple[float, list[str]]:
    if not target_tokens:
        return 1.0, []
    candidate_text = " ".join(
        str(value or "")
        for value in (
            _first_value(item, "name", "title", "product_title", "productTitle"),
            _first_value(item, "brief", "summary"),
            _first_value(item, "categoryTitle", "category_title") or _nested_value(item, "category", "title", "name"),
        )
    )
    candidate_tokens = _tokens(candidate_text)
    matched = sorted(target_tokens & candidate_tokens)
    score = len(matched) / max(len(target_tokens), 1)
    normalized_candidate = _normalize_text(candidate_text)
    if exact_phrase and exact_phrase in normalized_candidate:
        score = min(1.0, score + 0.25)
    return round(score, 3), matched


def _strip_outliers(samples: list[dict[str, Any]], price_key: str = "price") -> list[dict[str, Any]]:
    if len(samples) < 4:
        return samples
    prices = sorted(sample[price_key] for sample in samples)
    midpoint = len(prices) // 2
    lower_half = prices[:midpoint]
    upper_half = prices[midpoint + (0 if len(prices) % 2 == 0 else 1) :]
    q1 = statistics.median(lower_half)
    q3 = statistics.median(upper_half)
    iqr = q3 - q1
    if iqr <= 0:
        return samples
    low = q1 - (1.5 * iqr)
    high = q3 + (1.5 * iqr)
    return [sample for sample in samples if low <= sample[price_key] <= high]


def _rounded_market_price(price: int) -> int:
    if price <= 0:
        return price
    return int(round(price / PRICE_ROUNDING_STEP) * PRICE_ROUNDING_STEP)


def _weight_band(weight_ratio: float | None) -> str:
    if not weight_ratio:
        return "unknown"
    if 0.9 <= weight_ratio <= 1.1:
        return "exact"
    if 0.65 <= weight_ratio <= 1.55:
        return "close"
    if 0.5 <= weight_ratio <= 2.0:
        return "usable"
    if 0.25 <= weight_ratio <= 4.0:
        return "broad"
    return "far"


def _weight_relevance(weight_ratio: float | None) -> float:
    if not weight_ratio:
        return 0.65
    if 0.9 <= weight_ratio <= 1.1:
        return 1.0
    if 0.65 <= weight_ratio <= 1.55:
        return 0.82
    if 0.5 <= weight_ratio <= 2.0:
        return 0.58
    if 0.25 <= weight_ratio <= 4.0:
        return 0.32
    return 0.08


def _weighted_median(samples: list[dict[str, Any]], price_key: str) -> int:
    pairs = sorted(
        (
            int(sample[price_key]),
            max(float(sample.get("relevance_weight") or 1), 0.05),
        )
        for sample in samples
    )
    total_weight = sum(weight for _, weight in pairs)
    if total_weight <= 0:
        return int(statistics.median(price for price, _ in pairs))
    midpoint = total_weight / 2
    running = 0.0
    for price, weight in pairs:
        running += weight
        if running >= midpoint:
            return price
    return pairs[-1][0]


def build_price_suggestion(
    response: Any,
    *,
    category_id: int | None = None,
    product_type: str | None = None,
    keywords: str | None = None,
    category_title: str | None = None,
    weight: float | None = None,
    unit_quantity: float | None = None,
    unit_type: int | None = None,
) -> PriceSuggestion:
    warnings: list[str] = []
    items = _unwrap_search_items(response)
    samples: list[dict[str, Any]] = []
    target_tokens = _tokens(" ".join([product_type or "", keywords or "", category_title or ""]))
    exact_phrase = _normalize_text(product_type).strip()
    target_weight, target_weight_source = _target_weight_grams(
        weight=weight,
        unit_quantity=unit_quantity,
        unit_type=unit_type,
    )
    for item in items:
        if not _is_available(item):
            continue
        if not _category_matches(item, category_id):
            continue
        price = _price_of(item)
        if price is None:
            continue
        product_id = _first_value(item, "id", "product_id", "productId")
        type_score, matched_terms = _type_score(item, target_tokens, exact_phrase)
        sample_weight, sample_weight_source = _candidate_weight_grams(item)
        comparable_price = price
        weight_ratio = None
        weight_band = "unknown"
        if target_weight and sample_weight:
            weight_ratio = sample_weight / target_weight
            weight_band = _weight_band(weight_ratio)
            comparable_price = int(round(price * (target_weight / sample_weight)))
        relevance_weight = (0.35 + (0.65 * type_score)) * _weight_relevance(weight_ratio)
        samples.append(
            {
                "id": product_id,
                "name": _first_value(item, "name", "title", "product_title", "productTitle"),
                "price": price,
                "used_price": comparable_price,
                "comparable_price": comparable_price if target_weight and sample_weight else None,
                "detected_weight_grams": round(sample_weight, 2) if sample_weight else None,
                "weight_source": sample_weight_source,
                "weight_ratio": round(weight_ratio, 3) if weight_ratio else None,
                "weight_band": weight_band,
                "type_score": type_score,
                "matched_terms": matched_terms[:8],
                "relevance_weight": round(relevance_weight, 3),
                "category_id": _first_value(item, "new_categoryId", "newCategoryId", "categoryId", "category_id"),
                "category_title": _first_value(item, "categoryTitle", "category_title")
                or _nested_value(item, "category", "title", "name"),
                "vendor_title": _first_value(item, "vendorTitle", "vendor_title")
                or _nested_value(item, "vendor", "title", "name"),
                "url": _product_url(item, product_id),
            }
        )

    if target_tokens:
        strong_typed_samples = [sample for sample in samples if sample["type_score"] >= 0.45]
        typed_samples = [sample for sample in samples if sample["type_score"] >= 0.3]
        if len(strong_typed_samples) >= 4:
            samples = strong_typed_samples
        elif len(typed_samples) >= 3:
            samples = typed_samples
        else:
            warnings.append("نمونه کافی با نوع دقیق محصول پیدا نشد؛ چند نمونه نزدیک‌تر هم وارد محاسبه شد.")

    price_key = "price"
    sample_selection = "raw_price"
    if target_weight:
        close_weighted_samples = [
            sample
            for sample in samples
            if sample.get("detected_weight_grams") and sample.get("weight_band") in {"exact", "close"}
        ]
        usable_weighted_samples = [
            sample
            for sample in samples
            if sample.get("detected_weight_grams") and sample.get("weight_band") in {"exact", "close", "usable"}
        ]
        broad_weighted_samples = [
            sample
            for sample in samples
            if sample.get("detected_weight_grams") and sample.get("weight_band") in {"exact", "close", "usable", "broad"}
        ]
        if len(close_weighted_samples) >= 4:
            samples = close_weighted_samples
            price_key = "used_price"
            sample_selection = "close_weight"
            warnings.append("قیمت فقط از نمونه‌های نزدیک به وزن/مقدار فروش هدف محاسبه شد.")
        elif len(usable_weighted_samples) >= 3:
            samples = usable_weighted_samples
            price_key = "used_price"
            sample_selection = "usable_weight"
            warnings.append("قیمت نمونه‌ها بر اساس وزن/مقدار فروش محصول هدف نرمال شد.")
        elif len(broad_weighted_samples) >= 3:
            samples = broad_weighted_samples
            price_key = "used_price"
            sample_selection = "broad_weight"
            warnings.append("نمونه نزدیک به وزن هدف کم بود؛ چند نمونه دورتر با نرمال‌سازی وزن وارد محاسبه شد.")
        else:
            warnings.append("نمونه وزن‌دار کافی پیدا نشد؛ قیمت‌گذاری بیشتر بر اساس نوع و دسته انجام شد.")
    else:
        warnings.append("وزن یا مقدار فروش محصول هدف خالی است؛ معیار وزن در قیمت‌گذاری اعمال نشد.")

    filtered = _strip_outliers(samples, price_key=price_key)
    if len(filtered) != len(samples):
        warnings.append("چند قیمت پرت از محاسبه حذف شد.")

    for sample in filtered:
        sample["used_price"] = int(sample.get(price_key) or sample["price"])

    prices = [sample["used_price"] for sample in filtered]
    if not prices:
        warnings.append("محصول مشابه کافی برای قیمت‌گذاری پیدا نشد.")
        return PriceSuggestion(
            suggested_price=None,
            sample_count=0,
            min_price=None,
            max_price=None,
            median_price=None,
            confidence="low",
            source="basalam_market_search",
            samples=[],
            criteria={
                "currency_unit": APP_PRICE_UNIT,
                "source_currency_unit": PROVIDER_PRICE_UNIT,
                "type_terms": sorted(target_tokens),
                "target_weight_grams": round(target_weight, 2) if target_weight else None,
                "target_weight_source": target_weight_source,
                "price_basis": price_key,
                "sample_selection": sample_selection,
                "raw_sample_count": len(items),
            },
            warnings=warnings,
        )

    median_price = int(statistics.median(prices))
    suggested_price = _rounded_market_price(_weighted_median(filtered, price_key))
    sample_count = len(prices)
    close_count = sum(1 for sample in filtered if sample.get("weight_band") in {"exact", "close"})
    if sample_count >= 8 and (not target_weight or close_count >= 5):
        confidence = "high"
    elif sample_count >= 4:
        confidence = "medium"
    else:
        confidence = "low"
        warnings.append("تعداد نمونه‌های مشابه کم است و قیمت نیاز به بازبینی دارد.")
    if target_weight and price_key != "used_price":
        confidence = "low" if sample_count < 8 else "medium"
    if sample_selection == "broad_weight" and confidence == "high":
        confidence = "medium"

    return PriceSuggestion(
        suggested_price=suggested_price,
        sample_count=sample_count,
        min_price=min(prices),
        max_price=max(prices),
        median_price=median_price,
        confidence=confidence,
        source="basalam_market_search",
        samples=sorted(filtered, key=lambda sample: sample.get("relevance_weight") or 0, reverse=True)[:10],
        criteria={
            "currency_unit": APP_PRICE_UNIT,
            "source_currency_unit": PROVIDER_PRICE_UNIT,
            "type_terms": sorted(target_tokens),
            "target_weight_grams": round(target_weight, 2) if target_weight else None,
            "target_weight_source": target_weight_source,
            "price_basis": price_key,
            "sample_selection": sample_selection,
            "raw_sample_count": len(items),
            "close_weight_sample_count": close_count,
            "rounding_step": PRICE_ROUNDING_STEP,
        },
        warnings=warnings,
    )


def data_url_to_file(data_url: str, filename: str = "product.jpg") -> tuple[str, bytes, str]:
    if "," not in data_url:
        raise BasalamError("فرمت تصویر معتبر نیست.", 400)
    header, encoded = data_url.split(",", 1)
    mime_type = "image/jpeg"
    if header.startswith("data:") and ";" in header:
        mime_type = header[5 : header.index(";")]
    try:
        content = base64.b64decode(encoded)
    except ValueError as exc:
        raise BasalamError("base64 تصویر معتبر نیست.", 400) from exc
    return filename, content, mime_type


async def upload_product_photo(token: str, image_data_url: str, filename: str) -> dict[str, Any]:
    file_name, content, mime_type = data_url_to_file(image_data_url, filename)
    files = {"file": (file_name, content, mime_type)}
    data = {"file_type": "product.photo"}
    return await _request("POST", "/v1/files", token=token, files=files, data=data, timeout=60.0)


async def create_product(token: str, vendor_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    return await _request(
        "POST",
        f"/v1/vendors/{vendor_id}/products",
        token=token,
        json=payload,
        timeout=60.0,
    )


async def update_product(token: str, product_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    return await _request(
        "PATCH",
        f"/v1/products/{product_id}",
        token=token,
        json=payload,
        timeout=60.0,
    )
