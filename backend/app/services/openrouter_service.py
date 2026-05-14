from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.exceptions import OpenRouterError
from app.utils.logging import LoggerMixin

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def _extract_usage(body: dict[str, Any], model: str) -> dict[str, Any]:
    """Extract usage + cost from an OpenRouter chat-completions response.

    Returns a dict with keys: model, prompt_tokens, completion_tokens,
    total_tokens, cost_usd, generation_id. Safe to call on partial bodies.
    """
    usage = body.get("usage") or {}
    return {
        "model": model,
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"),
        # OpenRouter returns the real billed cost in `usage.cost` (USD)
        # only when the request body contained `usage: {"include": true}`.
        "cost_usd": float(usage.get("cost") or 0),
        "generation_id": body.get("id"),
    }

TITLE_GENERATION_GUIDELINES = """
شما یک متخصص SEO و نام‌گذاری محصول در پلتفرم «باسلام» هستید که بر اساس دستورالعمل‌های مدیر سرچ باسلام عمل می‌کنید.

دستورالعمل‌های کلیدی نام‌گذاری محصول در باسلام:

اصل اول - شروع با موجودیت اصلی:
- عنوان را حتما با نام اصلی و دسته‌بندی محصول شروع کن.
- کلمه کلیدی اصلی، مثل کتانی، اجاق گاز، مانتو یا عسل، باید در ابتدای عنوان باشد.
- هرگز عنوان را با نام برند یا کلمات فرعی شروع نکن.
- مثال صحیح: «کتانی مردانه آدیداس مدل X»
- مثال غلط: «آدیداس کتانی مردانه»

اصل دوم - استفاده از نام‌های مترادف و رایج:
- اگر محصول نام مترادف، جایگزین یا املای رایج دیگری در بازار دارد، آن را به شکل طبیعی در عنوان اضافه کن.
- از کلماتی استفاده کن که مشتریان در خرید حضوری یا جستجوی محصول به کار می‌برند.
- در صورت نیاز، مترادف مهم را داخل پرانتز بیاور.

ویژگی‌های تکمیلی عنوان خوب:
- عنوان باید واضح و توصیف‌کننده محصول باشد.
- فقط ویژگی‌های قابل مشاهده یا قابل استنباط با اطمینان را اضافه کن؛ مثل جنس، رنگ، سایز، کاربرد یا مزیت مهم.
- مزیت‌هایی مثل ارگانیک، دست‌ساز، طبی یا ضدآب را فقط وقتی بنویس که از تصویر یا زمینه محصول قابل تشخیص است.
- عنوان برای الگوریتم جستجوی باسلام مناسب باشد، اما طبیعی و خوانا بماند.

ساختار نوشتاری عنوان:
- از « | » برای جدا کردن اجزای عنوان استفاده نکن.
- عنوان نهایی را فارسی، روان، بدون اغراق و بدون قیمت بنویس.
""".strip()

IMAGE_ENHANCEMENT_PROMPT = """
You are a professional product photo retoucher for marketplace listings.

Edit the provided product image into a clean industrial studio product photo.
Preserve the exact product identity. Do not redesign, replace, recolor, resize deceptively, add parts, remove parts, change material, change texture, change logo/label text, or alter visible defects that are part of the real item.

Create a square 1:1 product listing image.
Keep the product centered, fully visible, naturally scaled, and sharply focused.
Use realistic studio lighting, balanced exposure, clean contrast, natural color, mild shadow, and crisp edges.
Choose a simple, category-appropriate background based only on the visible product type. The background must stay minimal, neutral, non-distracting, and marketplace-safe.
Remove clutter and simplify the original background only when it does not change the product itself.

Do not add props, hands, packaging, decorations, text, watermark, badge, price, label, or brand elements that are not already present on the product.
Return only the edited image.
""".strip()


def _extract_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        value = json.loads(cleaned)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not match:
        raise OpenRouterError("مدل JSON قابل خواندن برنگرداند.", 502, text)
    try:
        value = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise OpenRouterError("JSON خروجی مدل معتبر نیست.", 502, text) from exc
    if not isinstance(value, dict):
        raise OpenRouterError("خروجی مدل آبجکت JSON نیست.", 502, text)
    return value


def _confidence(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _scalar_field(value: Any) -> dict[str, Any]:
    """Normalize {value, confidence} bundles, accepting bare strings too."""
    if isinstance(value, dict):
        return {
            "value": str(value.get("value") or value.get("title") or "").strip(),
            "confidence": _confidence(value.get("confidence")),
        }
    if isinstance(value, str):
        return {"value": value.strip(), "confidence": 0.0}
    return {"value": "", "confidence": 0.0}


def _str_list(value: Any, limit: int = 16) -> list[str]:
    if not isinstance(value, list):
        return []
    seen: set[str] = set()
    result: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
        if len(result) >= limit:
            break
    return result


def _dimensions(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"length_cm": None, "width_cm": None, "height_cm": None, "confidence": 0.0}

    def _num(v: Any) -> float | None:
        try:
            n = float(v)
        except (TypeError, ValueError):
            return None
        return n if n > 0 else None

    return {
        "length_cm": _num(value.get("length_cm") or value.get("length")),
        "width_cm": _num(value.get("width_cm") or value.get("width")),
        "height_cm": _num(value.get("height_cm") or value.get("height")),
        "confidence": _confidence(value.get("confidence")),
    }


def _normalize_analysis(value: dict[str, Any]) -> dict[str, Any]:
    category = value.get("category") if isinstance(value.get("category"), dict) else {}
    attributes = value.get("attributes") if isinstance(value.get("attributes"), list) else []
    warnings = value.get("warnings") if isinstance(value.get("warnings"), list) else []
    sale_unit = value.get("sale_unit") or value.get("saleUnit") or value.get("unit") or {}
    if not isinstance(sale_unit, dict):
        sale_unit = {}
    if not sale_unit:
        sale_unit = {
            "quantity": value.get("unit_quantity") or value.get("sale_quantity"),
            "unit_type": value.get("unit_type") or value.get("unitType"),
            "unit_title": value.get("unit_title") or value.get("unit"),
            "confidence": value.get("unit_confidence") or value.get("confidence"),
        }
    package_weight = (
        value.get("estimated_package_weight")
        or value.get("package_weight")
        or value.get("estimated_packaged_weight")
        or {}
    )
    if not isinstance(package_weight, dict):
        package_weight = {}
    return {
        "title": str(value.get("title") or ""),
        "brief": str(value.get("brief") or ""),
        "description": str(value.get("description") or ""),
        "category": {
            "id": category.get("id"),
            "title": str(category.get("title") or ""),
            "confidence": _confidence(category.get("confidence")),
        },
        "attributes": [
            {
                "attribute_id": item.get("attribute_id") or item.get("id"),
                "title": str(item.get("title") or ""),
                "value": str(item.get("value") or ""),
                "confidence": _confidence(item.get("confidence")),
            }
            for item in attributes
            if isinstance(item, dict)
        ],
        "estimated_weight": value.get("estimated_weight") or {},
        "estimated_package_weight": package_weight,
        "sale_unit": {
            "quantity": sale_unit.get("quantity") or sale_unit.get("unit_quantity") or sale_unit.get("value"),
            "unit_type": sale_unit.get("unit_type") or sale_unit.get("unitType") or sale_unit.get("unit_type_id"),
            "unit_title": str(sale_unit.get("unit_title") or sale_unit.get("title") or sale_unit.get("unit") or ""),
            "confidence": _confidence(sale_unit.get("confidence")),
        },
        "brand": _scalar_field(value.get("brand")),
        "color": _scalar_field(value.get("color")),
        "material": _scalar_field(value.get("material")),
        "condition": _scalar_field(value.get("condition")),
        "country_of_origin": _scalar_field(value.get("country_of_origin")),
        "packaging": _scalar_field(value.get("packaging")),
        "dimensions": _dimensions(value.get("dimensions")),
        "keywords": _str_list(value.get("keywords"), limit=12),
        "tags": _str_list(value.get("tags"), limit=8),
        "warnings": [str(item) for item in warnings if item],
    }


def _extract_image_url(value: Any) -> str | None:
    if isinstance(value, str):
        return value if value.startswith("data:image/") else None
    if isinstance(value, list):
        for item in value:
            image_url = _extract_image_url(item)
            if image_url:
                return image_url
        return None
    if not isinstance(value, dict):
        return None

    for key in ("image_url", "imageUrl"):
        image_url = _extract_image_url(value.get(key))
        if image_url:
            return image_url

    url = value.get("url")
    if isinstance(url, str) and url.startswith("data:image/"):
        return url

    for child in value.values():
        image_url = _extract_image_url(child)
        if image_url:
            return image_url
    return None


def _make_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "Basalam Product Importer",
    }


class OpenRouterService(LoggerMixin):
    """Stateless service wrapper around the OpenRouter API."""

    def __init__(self, api_key: str | None = None) -> None:
        """Initialise with an optional API key.

        If api_key is not provided it falls back to settings.openrouter_api_key.
        No persistent HTTP session is held — each call opens its own httpx client.
        """
        self._api_key = api_key
        # Populated after each successful chat-completions call so callers can
        # persist usage/cost alongside the result. See _extract_usage for keys.
        self.last_usage: dict[str, Any] | None = None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_key(self) -> str:
        key = self._api_key or get_settings().openrouter_api_key
        if not key:
            raise OpenRouterError("کلید OpenRouter وارد نشده است.", 400)
        return key

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def analyze_product_image(
        self,
        *,
        image_data_url: str,
        categories: list[dict[str, Any]],
        model: str | None = None,
    ) -> dict[str, Any]:
        """Call the text/vision model to analyse a product image.

        Returns a normalised dict matching the _normalize_analysis schema.
        """
        api_key = self._resolve_key()
        selected_model = model or get_settings().openrouter_text_model

        category_lines = []
        for category in categories[:1000]:
            unit = category.get("unit_type")
            unit_text = ""
            if isinstance(unit, dict):
                unit_text = f" | sale unit: {unit.get('title')} (id={unit.get('id')})"
            elif unit:
                unit_text = f" | sale unit id: {unit}"
            category_lines.append(f"- {category.get('id')}: {category.get('title')}{unit_text}")
        category_context = "\n".join(category_lines)

        prompt = f"""
You are helping a Persian Basalam vendor create a product listing from a product photo.
Return only valid JSON. Do not wrap it in markdown.
Extract every detail you can see or strongly infer. For every field include a
confidence in [0,1]. When a field is not visible or you are unsure, return an
empty string / null AND set confidence below 0.5 — never invent.

Pick category only from this category list, using its numeric id:
{category_context}

Use these Basalam product title rules when generating the final "title":
{TITLE_GENERATION_GUIDELINES}

JSON schema:
{{
  "title": "Persian Basalam SEO product title following the title rules",
  "brief": "short Persian summary",
  "description": "complete Persian product description",
  "category": {{"id": 0, "title": "string", "confidence": 0.0}},
  "attributes": [
    {{"attribute_id": 0, "title": "string", "value": "string", "confidence": 0.0}}
  ],
  "estimated_weight": {{"value": 0, "unit": "gram", "confidence": 0.0}},
  "estimated_package_weight": {{"value": 0, "unit": "gram", "confidence": 0.0}},
  "sale_unit": {{"quantity": 0, "unit_type": 0, "unit_title": "string", "confidence": 0.0}},
  "brand": {{"value": "string", "confidence": 0.0}},
  "color": {{"value": "string", "confidence": 0.0}},
  "material": {{"value": "string", "confidence": 0.0}},
  "condition": {{"value": "new|used|refurbished", "confidence": 0.0}},
  "country_of_origin": {{"value": "string", "confidence": 0.0}},
  "packaging": {{"value": "string", "confidence": 0.0}},
  "dimensions": {{
    "length_cm": 0,
    "width_cm": 0,
    "height_cm": 0,
    "confidence": 0.0
  }},
  "keywords": ["string"],
  "tags": ["string"],
  "variants": [
    {{
      "primary_price_toman": 0,
      "stock": 0,
      "properties": [{{"property": "string", "value": "string"}}],
      "confidence": 0.0
    }}
  ],
  "warnings": ["string"]
}}

Detection rules:
- Read every visible text on the packaging (brand, weight, ingredients, certifications).
- "brand": only if a recognizable logo or brand name is printed on the product.
- "color": dominant visible color of the product itself (not the background).
- "material": fabric/plastic/metal/wood/ceramic/glass/leather/paper, only when visually clear.
- "condition": default "new" with confidence 0.7 if the product looks unused and intact; otherwise lower.
- "country_of_origin": only if explicitly labeled (e.g. "Made in Iran", "ایران").
- "packaging": short Persian phrase like "جعبه مقوایی"، "بسته نایلونی"، "شیشه‌ای".
- "dimensions": estimate in centimeters with confidence below 0.5 if not directly measurable.
- "keywords": 5–10 Persian search keywords a Basalam buyer would type to find this item — short tokens, not full sentences.
- "tags": 3–6 free-form Persian descriptors (e.g. "خانگی"، "گیاهی"، "زنانه").
- estimated_weight is the product net weight in grams when visible or strongly inferable.
- estimated_package_weight is product weight with packaging in grams; it must be greater than net weight.
- sale_unit is the sellable amount shown/implied by the product package. If the category line includes a sale unit, use that unit_type id.
- For gram-based packaged food, sale_unit.quantity should usually match the visible/estimated net gram amount.
- For count-based items, use quantity 1 and the count unit only when the category/unit clearly supports it.
- Do not invent price.
- Keep the product truthful; describe visible material, color, shape, and likely use.
""".strip()

        payload = {
            "model": selected_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_data_url}},
                    ],
                }
            ],
            "temperature": 0.2,
            "max_tokens": 2200,
            "response_format": {"type": "json_object"},
            # Ask OpenRouter to include billed cost in the response.usage.
            "usage": {"include": True},
        }

        self.last_usage = None
        self.logger.debug("analyzing product image model=%s", selected_model)
        async with httpx.AsyncClient(timeout=90.0) as client:
            try:
                response = await client.post(OPENROUTER_URL, headers=_make_headers(api_key), json=payload)
            except httpx.TimeoutException as exc:
                raise OpenRouterError("تحلیل تصویر بیش از حد طول کشید.", 504) from exc
            except httpx.HTTPError as exc:
                raise OpenRouterError("اتصال به OpenRouter ناموفق بود.", 502) from exc

        if response.status_code >= 400:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text
            raise OpenRouterError("خطای OpenRouter", response.status_code, detail)

        try:
            body = response.json()
            text = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise OpenRouterError("پاسخ OpenRouter قابل خواندن نبود.", 502, response.text) from exc

        self.last_usage = _extract_usage(body, selected_model)
        if isinstance(text, list):
            text = "".join(part.get("text", "") for part in text if isinstance(part, dict))
        parsed = _extract_json(str(text))
        return _normalize_analysis(parsed)

    async def enhance_product_image(
        self,
        *,
        image_data_url: str,
        filename: str = "product.jpg",
        model: str | None = None,
    ) -> dict[str, Any]:
        """Call the image-generation model to produce a clean studio-style photo.

        Returns a dict with enhanced_image_data_url, model, and filename.
        """
        api_key = self._resolve_key()
        if not image_data_url.startswith("data:image/"):
            raise OpenRouterError("فرمت تصویر برای بهبود AI معتبر نیست.", 400)
        selected_model = model or get_settings().openrouter_image_model

        payload = {
            "model": selected_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": IMAGE_ENHANCEMENT_PROMPT},
                        {"type": "image_url", "image_url": {"url": image_data_url}},
                    ],
                }
            ],
            "modalities": ["image", "text"],
            "image_config": {"aspect_ratio": "1:1"},
            "temperature": 0.1,
            # Ask OpenRouter to include billed cost in the response.usage.
            "usage": {"include": True},
        }

        self.last_usage = None
        self.logger.debug("enhancing product image model=%s", selected_model)
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(OPENROUTER_URL, headers=_make_headers(api_key), json=payload)
            except httpx.TimeoutException as exc:
                raise OpenRouterError("بهبود عکس بیش از حد طول کشید.", 504) from exc
            except httpx.HTTPError as exc:
                raise OpenRouterError("اتصال به OpenRouter برای بهبود عکس ناموفق بود.", 502) from exc

        if response.status_code >= 400:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text
            raise OpenRouterError("خطای OpenRouter در بهبود عکس", response.status_code, detail)

        try:
            body = response.json()
        except ValueError as exc:
            raise OpenRouterError("پاسخ بهبود عکس JSON معتبر نبود.", 502, response.text) from exc

        self.last_usage = _extract_usage(body, selected_model)
        image_url = _extract_image_url(body.get("choices"))
        if not image_url:
            raise OpenRouterError("OpenRouter تصویر بهبود‌یافته برنگرداند.", 502, body)

        return {
            "enhanced_image_data_url": image_url,
            "model": selected_model,
            "filename": filename,
        }
