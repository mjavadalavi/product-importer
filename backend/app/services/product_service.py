"""
ProductService — full product lifecycle.

Owns: create-with-images, list, get, update (including push to Basalam),
resubmit, confirm-draft, confirm-all-drafts, save-drafts (bulk import),
attach-images, attach-images-bulk, delete-image, reorder-images,
enhance-one-image.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.crypto import decrypt_token
from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.db.models.product import Product, ProductStatus
from app.db.models.product_image import ProductImage
from app.db.models.transaction import (
    ReferenceType,
    Transaction,
    TransactionStatus,
)
from app.db.models.user import User
from app.repositories.product import (
    ImportJobRepository,
    ProductImageRepository,
    ProductRepository,
)
from app.repositories.user import OAuthAccountRepository
from app.schemas.common import PaginatedResponse
from app.schemas.products import (
    AttachImagesRequest,
    BulkAttachImagesRequest,
    BulkDraftCreated,
    BulkSaveDraftsRequest,
    ConfirmAllRequest,
    ConfirmAllResponse,
    ConfirmAllResultItem,
    ProductCreateRequest,
    ProductListItem,
    ProductOut,
    ProductUpdateRequest,
    ReorderImagesRequest,
)
from app.services.basalam.payload import _toman_to_provider_rial
from app.services.basalam_service import BasalamService
from app.services.bulk_import.units import resolve_unit_type_title
from app.services.file_service import FileService
from app.services.jobs_service import JobsService
from app.services.ledger_service import LedgerService
from app.services.openrouter_service import OpenRouterService
from app.utils.logging import LoggerMixin


EDITABLE_IMAGE_STATUSES: set[ProductStatus] = {
    ProductStatus.DRAFT,
    ProductStatus.READY,
    ProductStatus.FAILED,
}


class ProductService(LoggerMixin):
    def __init__(self, session: AsyncSession):
        self.session = session
        self.product_repo = ProductRepository(session)
        self.image_repo = ProductImageRepository(session)
        self.job_repo = ImportJobRepository(session)
        self.oauth_repo = OAuthAccountRepository(session)
        self.ledger = LedgerService(session)
        self.jobs = JobsService(session)
        self.file_service = FileService(session)

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------

    async def _get_owned(self, user: User, product_id: UUID, *, with_images: bool = False) -> Product:
        product = await self.product_repo.get_for_user(product_id, user.id, with_images=with_images)
        if product is None:
            raise NotFoundError()
        return product

    def _ensure_editable_images(self, product: Product, *, verb: str) -> None:
        if product.status not in EDITABLE_IMAGE_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"{verb} عکس فقط برای پیش‌نویس، آماده یا ناموفق امکان‌پذیر است.",
            )

    # ------------------------------------------------------------------
    # CRUD-ish lifecycle
    # ------------------------------------------------------------------

    async def create_with_images(self, user: User, request: ProductCreateRequest) -> Product:
        settings = get_settings()
        cost = settings.cost_per_product
        self.logger.info(
            "create_with_images user=%s images=%d cost=%d",
            user.id, len(request.images), cost,
        )

        tx = await self.ledger.withdraw(
            user_id=user.id,
            reference_type=ReferenceType.PRODUCT,
            reference_id=None,
            amount=cost,
        )

        product = Product(user_id=user.id, status=ProductStatus.DRAFT)
        if request.description:
            product.description = request.description
        self.session.add(product)
        await self.session.flush()

        for idx, img in enumerate(request.images):
            if img.file_id is not None:
                # Wave B path: resolve file and derive original_url from it.
                file = await self.file_service.get_for_user(img.file_id, user)
                original_url = await self.file_service.data_url(file)
                filename = file.filename or img.filename or f"product-{idx + 1}.jpg"
                self.logger.debug(
                    "create_with_images file_id path file_id=%s product_id=%s",
                    img.file_id, product.id,
                )
            else:
                # Legacy path: raw data_url supplied by older client.
                original_url = img.data_url
                filename = img.filename or f"product-{idx + 1}.jpg"

            pi = ProductImage(
                product_id=product.id,
                order=idx,
                original_url=original_url,
                use_enhanced=False,
                filename=filename,
                file_id=img.file_id,
            )
            self.session.add(pi)

            # Bind the File row to this product after we have the product id.
            if img.file_id is not None:
                await self.file_service.attach_to_target(
                    file, target_type="product", target_id=product.id
                )

        product.withdraw_tx_id = tx.id
        product.status = ProductStatus.PROCESSING
        await self.jobs.enqueue(product.id)
        await self.session.commit()
        await self.session.refresh(product, attribute_names=["images"])
        return product

    async def list_for_user(
        self,
        user: User,
        *,
        status: ProductStatus | None,
        page: int,
        page_size: int,
    ) -> PaginatedResponse[ProductListItem]:
        rows, total = await self.product_repo.list_for_user(
            user.id, status=status, page=page, page_size=page_size,
        )
        items = [ProductListItem.from_product(r) for r in rows]
        return PaginatedResponse.build(items=items, total=total, page=page, page_size=page_size)

    async def get_for_user(self, user: User, product_id: UUID) -> Product:
        return await self._get_owned(user, product_id, with_images=True)

    # ------------------------------------------------------------------
    # update + push to Basalam if already submitted there
    # ------------------------------------------------------------------

    async def update_for_user(
        self, user: User, product_id: UUID, request: ProductUpdateRequest,
    ) -> Product:
        product = await self._get_owned(user, product_id, with_images=True)

        updated_fields = request.model_dump(exclude_unset=True)
        for field, value in updated_fields.items():
            if hasattr(product, field):
                setattr(product, field, value)

        if product.basalam_product_id and updated_fields:
            basalam_payload: dict[str, Any] = {}
            field_map = {
                "name": "name",
                "brief": "brief",
                "description": "description",
                "stock": "stock",
                "preparation_days": "preparation_days",
                "weight": "weight",
                "package_weight": "package_weight",
            }
            for local_field, remote_field in field_map.items():
                if local_field in updated_fields:
                    basalam_payload[remote_field] = updated_fields[local_field]
            if "price_final" in updated_fields:
                basalam_payload["primary_price"] = _toman_to_provider_rial(updated_fields["price_final"])
            if basalam_payload:
                try:
                    oauth = await self.oauth_repo.get_for_user(user.id, provider="basalam")
                    if oauth is None:
                        raise ValueError("no basalam oauth account found for user")
                    svc = BasalamService(token=decrypt_token(oauth.access_token_enc))
                    await svc.update_product(product.basalam_product_id, basalam_payload)
                except Exception as exc:
                    self.logger.warning(
                        "basalam update failed product=%s error=%s", product_id, exc,
                    )
                    existing = product.errors or {}
                    existing["basalam_update"] = str(exc)
                    product.errors = existing

        await self.session.commit()
        await self.session.refresh(product, attribute_names=["images"])
        return product

    # ------------------------------------------------------------------
    # resubmit + confirm + confirm-all
    # ------------------------------------------------------------------

    async def resubmit(self, user: User, product_id: UUID) -> Product:
        product = await self._get_owned(user, product_id, with_images=True)
        if product.status not in {ProductStatus.FAILED, ProductStatus.READY}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot resubmit a product with status '{product.status}'.",
            )
        if not product.images:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": "محصول بدون عکس قابل ثبت نیست.",
                    "product_ids_missing_images": [str(product.id)],
                },
            )

        settings = get_settings()
        cost = settings.cost_per_product
        if product.withdraw_tx_id is not None:
            prev_tx = await self.session.get(Transaction, product.withdraw_tx_id)
            if prev_tx is not None and prev_tx.status == TransactionStatus.REVERSED:
                new_tx = await self.ledger.withdraw(
                    user_id=user.id,
                    reference_type=ReferenceType.PRODUCT,
                    reference_id=None,
                    amount=cost,
                )
                product.withdraw_tx_id = new_tx.id
        else:
            new_tx = await self.ledger.withdraw(
                user_id=user.id,
                reference_type=ReferenceType.PRODUCT,
                reference_id=None,
                amount=cost,
            )
            product.withdraw_tx_id = new_tx.id

        product.status = ProductStatus.PROCESSING
        product.errors = None
        await self.jobs.enqueue(product.id)
        await self.session.commit()
        return product

    async def confirm_draft(self, user: User, product_id: UUID) -> Product:
        product = await self._get_owned(user, product_id, with_images=True)
        if product.status != ProductStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only DRAFT products can be confirmed.",
            )
        if not product.images:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": "محصول بدون عکس قابل ثبت نیست.",
                    "product_ids_missing_images": [str(product.id)],
                },
            )
        settings = get_settings()
        tx = await self.ledger.withdraw(
            user_id=user.id,
            reference_type=ReferenceType.PRODUCT,
            reference_id=None,
            amount=settings.cost_per_product,
        )
        product.withdraw_tx_id = tx.id
        product.status = ProductStatus.PROCESSING
        product.errors = None
        await self.jobs.enqueue(product.id)
        await self.session.commit()
        return product

    async def confirm_all(self, user: User, product_ids: list[UUID]) -> ConfirmAllResponse:
        from app.core.exceptions import InsufficientBalance

        settings = get_settings()
        cost = settings.cost_per_product

        result = await self.session.execute(
            select(Product)
            .options(selectinload(Product.images))
            .where(
                Product.id.in_(product_ids),
                Product.user_id == user.id,
                Product.status == ProductStatus.DRAFT,
            )
        )
        drafts = list(result.scalars().all())
        if not drafts:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="هیچ پیش‌نویس قابل ثبتی پیدا نشد.",
            )
        missing_images = [p for p in drafts if not p.images]
        if missing_images:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": "بعضی محصول‌ها بدون عکس‌اند و قابل ثبت نیستند.",
                    "product_ids_missing_images": [str(p.id) for p in missing_images],
                },
            )

        total_required = cost * len(drafts)
        available = await self.ledger.get_available_balance(user.id)
        if available < total_required:
            raise InsufficientBalance(required=total_required, available=available)

        results: list[ConfirmAllResultItem] = []
        total_charged = 0
        for product in drafts:
            try:
                tx = await self.ledger.withdraw(
                    user_id=user.id,
                    reference_type=ReferenceType.PRODUCT,
                    reference_id=None,
                    amount=cost,
                )
                product.withdraw_tx_id = tx.id
                product.status = ProductStatus.PROCESSING
                product.errors = None
                await self.jobs.enqueue(product.id)
                results.append(ConfirmAllResultItem(product_id=product.id, ok=True))
                total_charged += cost
            except Exception as exc:
                self.logger.exception("confirm_all per-product failure product=%s", product.id)
                results.append(ConfirmAllResultItem(product_id=product.id, ok=False, error=str(exc)))

        await self.session.commit()
        failed = sum(1 for r in results if not r.ok)
        return ConfirmAllResponse(confirmed=results, failed_count=failed, total_charged=total_charged)

    # ------------------------------------------------------------------
    # bulk save-drafts
    # ------------------------------------------------------------------

    async def save_drafts(self, user: User, request: BulkSaveDraftsRequest) -> list[BulkDraftCreated]:
        created: list[BulkDraftCreated] = []
        for idx, row in enumerate(request.rows):
            product = Product(
                user_id=user.id,
                status=ProductStatus.DRAFT,
                name=(row.name or None),
                brief=(row.brief or None),
                description=(row.description or None),
                category_title=(row.category_title or None),
                price_final=row.primary_price,
                stock=row.stock,
                weight=row.weight_g,
                package_weight=row.package_weight_g,
                preparation_days=row.preparation_days,
                unit_quantity=row.unit_quantity,
                unit_type=resolve_unit_type_title(row.unit_type_title),
                sku=(row.sku or None),
                attributes=None,
                ai_result={
                    "source": "bulk_import",
                    "row_index": idx,
                    "raw": {
                        "keywords": row.keywords or [],
                        "barcode": row.barcode,
                        "is_wholesale": row.is_wholesale,
                        "unit_type_title": row.unit_type_title,
                    },
                },
            )
            self.session.add(product)
            await self.session.flush()
            for order_idx, img in enumerate(row.images):
                if img.file_id is not None:
                    file = await self.file_service.get_for_user(img.file_id, user)
                    original_url = await self.file_service.data_url(file)
                    filename = file.filename or img.filename or f"row-{idx + 1}-{order_idx + 1}.jpg"
                    self.logger.debug(
                        "save_drafts file_id path file_id=%s product_id=%s",
                        img.file_id, product.id,
                    )
                else:
                    original_url = img.data_url
                    filename = img.filename or f"row-{idx + 1}-{order_idx + 1}.jpg"

                pi = ProductImage(
                    product_id=product.id,
                    order=order_idx,
                    original_url=original_url,
                    use_enhanced=False,
                    filename=filename,
                    file_id=img.file_id,
                )
                self.session.add(pi)

                if img.file_id is not None:
                    await self.file_service.attach_to_target(
                        file, target_type="product", target_id=product.id
                    )

            created.append(BulkDraftCreated(product_id=product.id, row_index=idx))
        await self.session.commit()
        return created

    # ------------------------------------------------------------------
    # images: attach, attach-bulk, delete, reorder, enhance-one
    # ------------------------------------------------------------------

    async def attach_images(self, user: User, product_id: UUID, request: AttachImagesRequest) -> Product:
        product = await self._get_owned(user, product_id, with_images=True)
        self._ensure_editable_images(product, verb="افزودن")
        next_order = max((img.order for img in product.images), default=-1) + 1
        for offset, img in enumerate(request.images):
            if img.file_id is not None:
                file = await self.file_service.get_for_user(img.file_id, user)
                original_url = await self.file_service.data_url(file)
                filename = file.filename or img.filename or f"image-{next_order + offset + 1}.jpg"
                self.logger.debug(
                    "attach_images file_id path file_id=%s product_id=%s",
                    img.file_id, product.id,
                )
            else:
                original_url = img.data_url
                filename = img.filename or f"image-{next_order + offset + 1}.jpg"

            pi = ProductImage(
                product_id=product.id,
                order=next_order + offset,
                original_url=original_url,
                use_enhanced=False,
                filename=filename,
                file_id=img.file_id,
            )
            self.session.add(pi)

            if img.file_id is not None:
                await self.file_service.attach_to_target(
                    file, target_type="product", target_id=product.id
                )

        await self.session.commit()
        await self.session.refresh(product, attribute_names=["images"])
        return product

    async def attach_images_bulk(self, user: User, request: BulkAttachImagesRequest) -> dict:
        target_ids = [a.product_id for a in request.assignments]
        result = await self.session.execute(
            select(Product)
            .options(selectinload(Product.images))
            .where(Product.id.in_(target_ids), Product.user_id == user.id)
        )
        products: dict[UUID, Product] = {p.id: p for p in result.scalars().all()}
        missing = [pid for pid in target_ids if pid not in products]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"محصول‌(های) یافت نشد: {missing}",
            )
        invalid = [pid for pid, p in products.items() if p.status not in EDITABLE_IMAGE_STATUSES]
        if invalid:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"عکس فقط به پیش‌نویس قابل افزودن است: {invalid}",
            )
        attached = 0
        for assignment in request.assignments:
            product = products[assignment.product_id]
            next_order = max((img.order for img in product.images), default=-1) + 1
            for offset, img in enumerate(assignment.images):
                if img.file_id is not None:
                    file = await self.file_service.get_for_user(img.file_id, user)
                    original_url = await self.file_service.data_url(file)
                    filename = file.filename or img.filename or f"image-{next_order + offset + 1}.jpg"
                    self.logger.debug(
                        "attach_images_bulk file_id path file_id=%s product_id=%s",
                        img.file_id, product.id,
                    )
                else:
                    original_url = img.data_url
                    filename = img.filename or f"image-{next_order + offset + 1}.jpg"

                pi = ProductImage(
                    product_id=product.id,
                    order=next_order + offset,
                    original_url=original_url,
                    use_enhanced=False,
                    filename=filename,
                    file_id=img.file_id,
                )
                self.session.add(pi)

                if img.file_id is not None:
                    await self.file_service.attach_to_target(
                        file, target_type="product", target_id=product.id
                    )

                attached += 1
        await self.session.commit()
        return {"attached": attached, "products": len(request.assignments)}

    async def delete_image(self, user: User, product_id: UUID, image_id: UUID) -> Product:
        product = await self._get_owned(user, product_id, with_images=True)
        self._ensure_editable_images(product, verb="حذف")
        target = next((img for img in product.images if img.id == image_id), None)
        if target is None:
            raise NotFoundError()
        await self.session.delete(target)
        await self.session.commit()
        await self.session.refresh(product, attribute_names=["images"])
        return product

    async def reorder_images(
        self, user: User, product_id: UUID, request: ReorderImagesRequest,
    ) -> Product:
        product = await self._get_owned(user, product_id, with_images=True)
        self._ensure_editable_images(product, verb="تغییر ترتیب")
        by_id = {img.id: img for img in product.images}
        if {pid for pid in request.ordered_ids} != set(by_id.keys()):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="فهرست ترتیب باید دقیقا شامل همان عکس‌های این محصول باشد.",
            )
        for order_idx, image_id in enumerate(request.ordered_ids):
            by_id[image_id].order = order_idx
        await self.session.commit()
        await self.session.refresh(product, attribute_names=["images"])
        return product

    async def enhance_one_image(self, user: User, product_id: UUID, image_id: UUID) -> Product:
        product = await self._get_owned(user, product_id, with_images=True)
        self._ensure_editable_images(product, verb="بهبود")
        target = next((img for img in product.images if img.id == image_id), None)
        if target is None:
            raise NotFoundError()
        if not target.original_url:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="عکس اصلی برای بهبود در دسترس نیست.",
            )
        from app.core.exceptions import OpenRouterError

        try:
            openrouter = OpenRouterService()
            enhanced = await openrouter.enhance_product_image(
                image_data_url=target.original_url,
                filename=target.filename or "product.jpg",
            )
            target.enhanced_url = enhanced.get("enhanced_image_data_url")
            target.enhancement_model = enhanced.get("model")
            target.enhancement_error = None
            target.use_enhanced = True
        except OpenRouterError as exc:
            target.enhancement_error = str(exc)
            target.use_enhanced = False
            await self.session.commit()
            raise HTTPException(
                status_code=502,
                detail=f"بهبود AI ناموفق بود: {exc}",
            ) from exc
        await self.session.commit()
        await self.session.refresh(product, attribute_names=["images"])
        return product
