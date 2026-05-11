from __future__ import annotations

import math
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.crypto import decrypt_token
from app.core.exceptions import AppException, BasalamError, OpenRouterError
from app.core.logging import get_logger
from app.db.models.import_job import ImportJob
from app.db.models.oauth_account import OAuthAccount
from app.db.models.product import Product, ProductStatus
from app.db.models.product_image import ProductImage
from app.db.models.transaction import Transaction
from app.db.models.user import User
from app.services import ledger
from app.services.basalam import BasalamClient, build_price_suggestion
from app.services.basalam.categories import _extract_category_items, _flatten_categories
from app.services.basalam.payload import VALID_UNIT_TYPE_IDS, UNIT_TYPE_ID_ALIASES, normalize_product_payload
from app.services.openrouter import analyze_product_image, enhance_product_image

logger = get_logger(__name__)

# Unit type IDs mirroring JS constants
_GRAM_UNIT_TYPE_ID = 6306
_KG_UNIT_TYPE_ID = 6305
_COUNT_UNIT_TYPE_ID = 6304
# Unit types where quantity is a physical measurement (not a plain count)
_MEASURED_QUANTITY_UNIT_TYPE_IDS: frozenset[int] = frozenset(
    [_GRAM_UNIT_TYPE_ID, _KG_UNIT_TYPE_ID, 6311, 6312, 6313]
)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _provider_field_key(field: str) -> str:
    """Map a Basalam API field name to an app-side field bucket."""
    value = str(field or "")
    if value.startswith("product_attribute") or value.startswith("attributes"):
        return "attributes"
    mapping = {
        "package_weight": "package_weight",
        "packaged_weight": "package_weight",
        "unit_type": "unit",
        "unit_quantity": "unit",
        "primary_price": "price",
        "price": "price",
        "stock": "stock",
        "inventory": "stock",
        "name": "name",
        "title": "name",
        "category_id": "category",
        "photo": "image",
        "photos": "image",
        "variants": "variants",
    }
    return mapping.get(value, "")


def _weight_value_in_grams(weight: Any) -> float | None:
    """Port of JS weightValueInGrams — extract a gram value from an analysis weight dict."""
    if isinstance(weight, dict):
        raw = weight.get("value") or weight.get("quantity")
    else:
        raw = weight
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    unit = ""
    if isinstance(weight, dict):
        unit = str(
            weight.get("unit") or weight.get("unit_title") or weight.get("title") or "gram"
        ).lower()
    if "kilogram" in unit or "kg" in unit or "کیلو" in unit:
        return value * 1000.0
    return value


def _valid_unit_type_id(value: Any) -> int | None:
    """Resolve a unit type value to a canonical valid ID, or None."""
    if isinstance(value, dict):
        value = value.get("id")
    try:
        uid = int(value)
    except (TypeError, ValueError):
        return None
    uid = UNIT_TYPE_ID_ALIASES.get(uid, uid)
    return uid if uid in VALID_UNIT_TYPE_IDS else None


def _apply_estimated_package_weight(product: Product, analysis: dict[str, Any]) -> None:
    """Port of JS applyEstimatedPackageWeight."""
    if product.package_weight is not None:
        return
    package_weight_raw = analysis.get("estimated_package_weight") or {}
    if not isinstance(package_weight_raw, dict):
        package_weight_raw = {}
    ai_grams = _weight_value_in_grams(package_weight_raw)
    net_weight = product.weight
    if ai_grams is not None and float(package_weight_raw.get("confidence") or 0) >= 0.45:
        if net_weight is not None:
            product.package_weight = float(math.ceil(max(ai_grams, net_weight + 1)))
        else:
            product.package_weight = float(math.ceil(ai_grams))
        return
    if net_weight is not None:
        extra = max(20.0, min(150.0, net_weight * 0.12))
        product.package_weight = float(math.ceil(net_weight + extra))


def _apply_sale_unit(product: Product, analysis: dict[str, Any]) -> None:
    """Port of JS applySaleUnit."""
    sale_unit = analysis.get("sale_unit") or {}
    if not isinstance(sale_unit, dict):
        sale_unit = {}

    analysis_unit_type = _valid_unit_type_id(
        sale_unit.get("unit_type") or sale_unit.get("unitType") or sale_unit.get("unit_type_id")
    )
    existing_unit_type = _valid_unit_type_id(product.unit_type)

    if existing_unit_type is not None:
        product.unit_type = existing_unit_type
    elif analysis_unit_type is not None:
        product.unit_type = analysis_unit_type
    else:
        product.unit_type = _COUNT_UNIT_TYPE_ID

    resolved_unit_type = _valid_unit_type_id(product.unit_type)
    if resolved_unit_type is None or product.unit_quantity is not None:
        return

    analysis_quantity_raw = sale_unit.get("quantity") or sale_unit.get("unit_quantity") or sale_unit.get("value")
    analysis_confidence = float(sale_unit.get("confidence") or 0)
    try:
        analysis_quantity = float(analysis_quantity_raw) if analysis_quantity_raw is not None else None
        if analysis_quantity is not None and analysis_quantity <= 0:
            analysis_quantity = None
    except (TypeError, ValueError):
        analysis_quantity = None

    if analysis_quantity is not None and analysis_confidence >= 0.45:
        product.unit_quantity = analysis_quantity
        return

    net_weight = product.weight
    if resolved_unit_type == _GRAM_UNIT_TYPE_ID and net_weight is not None:
        product.unit_quantity = net_weight
    elif resolved_unit_type == _KG_UNIT_TYPE_ID and net_weight is not None:
        product.unit_quantity = net_weight / 1000.0
    elif resolved_unit_type not in _MEASURED_QUANTITY_UNIT_TYPE_IDS:
        product.unit_quantity = 1.0


def _flatten_attrs(attrs_payload: Any) -> list[dict[str, Any]]:
    """Flatten category attributes payload (data -> groups -> attributes)."""
    flat: list[dict[str, Any]] = []
    raw = attrs_payload if isinstance(attrs_payload, dict) else {}
    groups = raw.get("data") or []
    if not isinstance(groups, list):
        return flat
    for group in groups:
        if not isinstance(group, dict):
            continue
        for attr in group.get("attributes") or []:
            if isinstance(attr, dict):
                flat.append(attr)
    return flat


def _extract_provider_error_items(detail: Any) -> list[dict[str, Any]]:
    """Port of JS providerErrorItems — pull structured error items from a Basalam detail dict."""
    provider = detail if isinstance(detail, dict) else {}
    candidates = [
        provider.get("messages"),
        provider.get("openapi_raw_data"),
        provider.get("errors"),
        provider.get("detail"),
    ]
    for candidate in candidates:
        if isinstance(candidate, list):
            return [item for item in candidate if isinstance(item, dict)]
    return []


def _build_provider_field_errors(exc: BasalamError) -> dict[str, list[str]]:
    """Build a field_errors dict from a BasalamError, mirroring JS applyProviderErrors."""
    field_errors: dict[str, list[str]] = {}
    general_errors: list[str] = []
    mapped_count = 0
    detail = exc.detail

    items = _extract_provider_error_items(detail)
    for item in items:
        message = item.get("message") or item.get("msg") or str(exc)
        fields = item.get("fields") or []
        if not isinstance(fields, list):
            fields = []
        keys = list(dict.fromkeys(k for f in fields for k in [_provider_field_key(str(f))] if k))
        if not keys:
            general_errors.append(message)
            continue
        for key in keys:
            field_errors.setdefault(key, []).append(message)
            mapped_count += 1

    if not mapped_count and not general_errors:
        general_errors.append(str(exc))

    result: dict[str, Any] = {}
    if field_errors:
        result["field_errors"] = field_errors
    if general_errors:
        result["general_errors"] = list(dict.fromkeys(general_errors))
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def process_product_job(product_id: uuid.UUID, db: AsyncSession) -> None:
    """Orchestrate the full AI-analyze → price-suggest → Basalam-submit pipeline for one product."""

    # ------------------------------------------------------------------
    # Step 1: Load product (with images eagerly), user, and oauth account
    # ------------------------------------------------------------------
    product_result = await db.execute(
        select(Product)
        .where(Product.id == product_id)
        .options(selectinload(Product.images), selectinload(Product.user))
    )
    product = product_result.scalar_one_or_none()
    if product is None:
        logger.error("process_product_job: product not found product_id=%s", product_id)
        return

    user: User = product.user
    images: list[ProductImage] = sorted(product.images, key=lambda img: img.order)

    oauth_result = await db.execute(
        select(OAuthAccount)
        .where(OAuthAccount.user_id == user.id, OAuthAccount.provider == "basalam")
        .order_by(OAuthAccount.updated_at.desc())
        .limit(1)
    )
    oauth: OAuthAccount | None = oauth_result.scalar_one_or_none()

    # Validate preconditions before any work
    if oauth is None:
        logger.warning("process_product_job: no oauth account product_id=%s user_id=%s", product_id, user.id)
        product.status = ProductStatus.FAILED
        product.errors = {"message": "no basalam token"}
        if product.withdraw_tx_id:
            await ledger.reverse_transaction(db, product.withdraw_tx_id)
        await db.flush()
        await db.commit()
        return

    if not images:
        logger.warning("process_product_job: no images product_id=%s", product_id)
        product.status = ProductStatus.FAILED
        product.errors = {"message": "no images"}
        if product.withdraw_tx_id:
            await ledger.reverse_transaction(db, product.withdraw_tx_id)
        await db.flush()
        await db.commit()
        return

    # ------------------------------------------------------------------
    # Step 2: Decrypt access token
    # ------------------------------------------------------------------
    access_token = decrypt_token(oauth.access_token_enc)
    logger.debug("process_product_job: token decrypted product_id=%s", product_id)

    # ------------------------------------------------------------------
    # Step 3: Build Basalam client
    # ------------------------------------------------------------------
    client = BasalamClient(token=access_token)

    # ------------------------------------------------------------------
    # Main pipeline wrapped in try/except
    # ------------------------------------------------------------------
    try:
        # --------------------------------------------------------------
        # Step 4: Fetch and flatten categories
        # --------------------------------------------------------------
        logger.info("process_product_job: fetching categories product_id=%s", product_id)
        raw_categories = await client.get_categories()
        flat_categories = _flatten_categories(_extract_category_items(raw_categories))
        categories_for_ai = [
            {
                "id": c["id"],
                "title": c.get("path") or c.get("title"),
                "unit_type": c.get("unit_type"),
            }
            for c in flat_categories
            if c.get("is_leaf")
        ]
        # Build a quick lookup by id for later use
        flat_by_id: dict[int | str, dict[str, Any]] = {str(c["id"]): c for c in flat_categories}

        # --------------------------------------------------------------
        # Step 5: Enhance images
        # --------------------------------------------------------------
        for img in images:
            if img.enhanced_url:
                continue
            if not img.original_url:
                continue
            logger.info(
                "process_product_job: enhancing image img_id=%s product_id=%s", img.id, product_id
            )
            try:
                result = await enhance_product_image(
                    image_data_url=img.original_url,
                    filename=img.filename or "product.jpg",
                )
                img.enhanced_url = result["enhanced_image_data_url"]
                img.enhancement_model = result.get("model")
                img.use_enhanced = True
            except Exception as enhance_exc:
                logger.warning(
                    "process_product_job: image enhancement failed img_id=%s error=%s",
                    img.id,
                    enhance_exc,
                )
                img.enhancement_error = str(enhance_exc)
                img.use_enhanced = False

        # --------------------------------------------------------------
        # Step 6: AI analyze first image
        # --------------------------------------------------------------
        first_image = images[0]
        analyze_url = first_image.original_url or ""
        logger.info("process_product_job: analyzing product image product_id=%s", product_id)
        analysis = await analyze_product_image(
            image_data_url=analyze_url,
            categories=categories_for_ai,
        )

        # --------------------------------------------------------------
        # Step 7: Apply analysis to product (port of applyAnalysis)
        # --------------------------------------------------------------
        product.name = analysis.get("title") or product.name
        product.brief = analysis.get("brief") or product.brief
        product.description = analysis.get("description") or product.description

        category_info = analysis.get("category") or {}
        category_id_raw = category_info.get("id")
        if category_id_raw is not None:
            try:
                cat_id_int = int(category_id_raw)
            except (TypeError, ValueError):
                cat_id_int = None
            if cat_id_int is not None:
                product.category_id = cat_id_int
                matched_cat = flat_by_id.get(str(cat_id_int))
                if matched_cat:
                    product.category_title = matched_cat.get("path") or matched_cat.get("title") or category_info.get("title") or ""
                else:
                    product.category_title = category_info.get("title") or ""
                product.category_confidence = float(category_info.get("confidence") or 0)

                # Apply category unit type if not already set
                if matched_cat and product.unit_type is None:
                    cat_unit = matched_cat.get("unit_type")
                    resolved = _valid_unit_type_id(cat_unit)
                    if resolved is not None:
                        product.unit_type = resolved

        # Estimated weight
        weight_raw = analysis.get("estimated_weight") or {}
        if isinstance(weight_raw, dict) and product.weight is None:
            weight_conf = float(weight_raw.get("confidence") or 0)
            if weight_conf >= 0.5:
                weight_grams = _weight_value_in_grams(weight_raw)
                if weight_grams is not None:
                    product.weight = round(weight_grams)
                    logger.debug(
                        "process_product_job: set weight=%s product_id=%s", product.weight, product_id
                    )

        # Estimated package weight
        _apply_estimated_package_weight(product, analysis)

        # Sale unit
        _apply_sale_unit(product, analysis)

        # --------------------------------------------------------------
        # Step 8: Fetch category attributes
        # --------------------------------------------------------------
        attrs_payload: dict[str, Any] = {}
        flat_attrs: list[dict[str, Any]] = []
        if product.category_id:
            logger.info(
                "process_product_job: fetching attributes category_id=%s product_id=%s",
                product.category_id,
                product_id,
            )
            attrs_payload = await client.get_category_attributes(
                product.category_id, vendor_id=user.vendor_id
            )
            flat_attrs = _flatten_attrs(attrs_payload)

        # --------------------------------------------------------------
        # Step 9: Apply attribute guesses (port of applyAttributeGuesses)
        # --------------------------------------------------------------
        guesses = analysis.get("attributes") or []
        if product.attributes is None:
            product.attributes = {}
        for guess in guesses:
            if not isinstance(guess, dict):
                continue
            if not guess.get("value"):
                continue
            guess_confidence = float(guess.get("confidence") or 0)
            if guess_confidence < 0.45:
                continue
            # Match by attribute_id first, then by title
            matched_attr: dict[str, Any] | None = None
            guess_attr_id = guess.get("attribute_id") or guess.get("id")
            if guess_attr_id is not None:
                for attr in flat_attrs:
                    if str(attr.get("id")) == str(guess_attr_id):
                        matched_attr = attr
                        break
            if matched_attr is None and guess.get("title"):
                guess_title = str(guess["title"]).strip()
                for attr in flat_attrs:
                    if str(attr.get("title") or "").strip() == guess_title:
                        matched_attr = attr
                        break
            if matched_attr is not None:
                attr_key = str(matched_attr["id"])
                product.attributes[attr_key] = str(guess["value"])
                logger.debug(
                    "process_product_job: set attribute attr_id=%s product_id=%s", attr_key, product_id
                )

        # --------------------------------------------------------------
        # Step 10: Build price suggestion
        # --------------------------------------------------------------
        query_parts = [product.name, product.category_title]
        query = " ".join(part for part in query_parts if part)
        suggestion = None
        if query.strip():
            logger.info(
                "process_product_job: searching for price suggestion query=%r product_id=%s",
                query,
                product_id,
            )
            search_result = await client.search_products(query, rows=80)
            suggestion = build_price_suggestion(
                search_result,
                category_id=product.category_id,
                product_type=product.name,
                category_title=product.category_title,
                weight=product.weight,
                unit_quantity=product.unit_quantity,
                unit_type=product.unit_type,
            )
            product.price_suggested = suggestion.suggested_price
            product.price_meta = {
                "min": suggestion.min_price,
                "max": suggestion.max_price,
                "median": suggestion.median_price,
                "confidence": suggestion.confidence,
                "sample_count": suggestion.sample_count,
                "source": suggestion.source,
                "criteria": suggestion.criteria,
                "warnings": suggestion.warnings,
                "samples": suggestion.samples[:10],
            }
            if product.price_final is None and suggestion.suggested_price is not None:
                product.price_final = suggestion.suggested_price
                logger.debug(
                    "process_product_job: set price_final=%s product_id=%s",
                    product.price_final,
                    product_id,
                )

        # --------------------------------------------------------------
        # Step 11: Persist AI result and price samples
        # --------------------------------------------------------------
        product.ai_result = analysis
        if suggestion is not None:
            product.price_samples = suggestion.samples

        # --------------------------------------------------------------
        # Step 12: Validate readiness
        # --------------------------------------------------------------
        field_errors: dict[str, list[str]] = {}
        general_errors: list[str] = []

        if not product.name:
            field_errors.setdefault("name", []).append("نام محصول وارد نشده است.")
        if not product.category_id:
            field_errors.setdefault("category", []).append("دسته‌بندی وارد نشده است.")
        if product.price_final is None:
            field_errors.setdefault("price", []).append("قیمت فروش وارد نشده است.")
        if product.stock is None:
            field_errors.setdefault("stock", []).append("موجودی وارد نشده است.")

        # Packaged weight must be > net weight
        packaged_weight_ok = False
        if product.package_weight is not None and product.weight is not None:
            packaged_weight_ok = product.package_weight >= product.weight + 1
        elif product.package_weight is not None:
            packaged_weight_ok = True
        if not packaged_weight_ok:
            field_errors.setdefault("package_weight", []).append("وزن با بسته‌بندی را وارد کنید.")

        if not images:
            field_errors.setdefault("image", []).append("عکس محصول الزامی است.")

        # Required attributes
        for attr in flat_attrs:
            is_required = bool(attr.get("required") or attr.get("is_required") or attr.get("isRequired"))
            if is_required:
                attr_key = str(attr.get("id"))
                if not (product.attributes or {}).get(attr_key):
                    field_errors.setdefault("attributes", []).append(
                        f"ویژگی «{attr.get('title')}» الزامی است."
                    )

        if field_errors or general_errors:
            product.status = ProductStatus.READY
            product.errors = {}
            if field_errors:
                product.errors["field_errors"] = field_errors
            if general_errors:
                product.errors["general_errors"] = general_errors
            logger.info(
                "process_product_job: validation failed, status=READY product_id=%s errors=%s",
                product_id,
                product.errors,
            )
            await db.flush()
            await db.commit()
            return

        # --------------------------------------------------------------
        # Step 13: Submit to Basalam
        # --------------------------------------------------------------
        logger.info("process_product_job: uploading images product_id=%s", product_id)
        photo_ids: list[int] = []
        for img in images:
            selected_url = (img.enhanced_url if img.use_enhanced and img.enhanced_url else None) or img.original_url
            if not selected_url:
                logger.warning(
                    "process_product_job: image has no URL, skipping img_id=%s", img.id
                )
                continue
            upload_result = await client.upload_product_photo(
                image_data_url=selected_url,
                filename=img.filename or "product.jpg",
            )
            # The API returns {id: ..., ...} or {data: {id: ...}}
            photo_id = (
                upload_result.get("id")
                or (upload_result.get("data") or {}).get("id")
            )
            if photo_id is not None:
                photo_ids.append(int(photo_id))
                logger.debug(
                    "process_product_job: uploaded photo photo_id=%s img_id=%s", photo_id, img.id
                )
            else:
                logger.warning(
                    "process_product_job: upload returned no id, result=%s img_id=%s",
                    upload_result,
                    img.id,
                )

        if not photo_ids:
            raise BasalamError("هیچ عکسی با موفقیت آپلود نشد.", 422)

        # Build product attribute list
        product_attribute = [
            {"attribute_id": int(attr_id), "value": value}
            for attr_id, value in (product.attributes or {}).items()
            if value
        ]

        product_dict: dict[str, Any] = {
            "name": product.name,
            "brief": product.brief,
            "description": product.description,
            "category_id": product.category_id,
            "primary_price": int(product.price_final) if product.price_final is not None else None,
            "stock": product.stock,
            "preparation_days": product.preparation_days,
            "weight": int(product.weight) if product.weight is not None else None,
            "package_weight": int(product.package_weight) if product.package_weight is not None else None,
            "unit_quantity": product.unit_quantity,
            "unit_type": product.unit_type,
            "sku": product.sku,
            "product_attribute": product_attribute,
        }

        # Variants
        variants_raw = product.variants
        if isinstance(variants_raw, list) and variants_raw:
            product_dict["variants"] = [
                {
                    "primary_price": v.get("primary_price"),
                    "stock": v.get("stock"),
                    "properties": v.get("properties") or [],
                }
                for v in variants_raw
                if isinstance(v, dict)
            ]

        payload = normalize_product_payload(product_dict, photo_ids)

        logger.info(
            "process_product_job: creating product vendor_id=%s product_id=%s",
            user.vendor_id,
            product_id,
        )
        response = await client.create_product(vendor_id=user.vendor_id, payload=payload)

        # Extract Basalam product ID
        basalam_id = (
            response.get("id")
            or (response.get("data") or {}).get("id")
        )
        if basalam_id is not None:
            product.basalam_product_id = int(basalam_id)

        product.status = ProductStatus.SUBMITTED
        product.errors = None
        logger.info(
            "process_product_job: submitted basalam_product_id=%s product_id=%s",
            product.basalam_product_id,
            product_id,
        )

        if product.withdraw_tx_id:
            await ledger.complete_transaction(db, product.withdraw_tx_id)

        await db.flush()
        await db.commit()

    except Exception as exc:
        logger.error(
            "process_product_job: pipeline error product_id=%s error=%s",
            product_id,
            exc,
            exc_info=True,
        )
        product.status = ProductStatus.FAILED

        if isinstance(exc, BasalamError):
            error_payload = _build_provider_field_errors(exc)
            error_payload["message"] = str(exc)
            if exc.detail is not None:
                error_payload["provider_detail"] = exc.detail
            product.errors = error_payload
        else:
            product.errors = {
                "message": str(exc),
                "provider_detail": getattr(exc, "detail", None),
            }

        if product.withdraw_tx_id:
            try:
                await ledger.reverse_transaction(db, product.withdraw_tx_id)
            except Exception as ledger_exc:
                logger.error(
                    "process_product_job: failed to reverse transaction tx_id=%s error=%s",
                    product.withdraw_tx_id,
                    ledger_exc,
                )

        await db.flush()
        await db.commit()
