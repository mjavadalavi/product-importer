from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, require_user
from app.db.models.product import ProductStatus
from app.db.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.products import (
    AttachImagesRequest,
    BulkAttachImagesRequest,
    BulkSaveDraftsFromFilesRequest,
    BulkSaveDraftsRequest,
    BulkSaveDraftsResponse,
    ConfirmAllRequest,
    ConfirmAllResponse,
    ProductCreateRequest,
    ProductCreatedResponse,
    ProductOut,
    ProductListItem,
    ProductUpdateRequest,
    ReorderImagesRequest,
)
from app.services.bulk_import import COLUMNS, build_template_xlsx
from app.services.bulk_import_service import BulkImportService
from app.services.product_service import ProductService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/products", tags=["products"])


# ---------------------------------------------------------------------------
# GET /template  — downloadable xlsx for bulk import
# ---------------------------------------------------------------------------

@router.get(
    "/template",
    summary="Download bulk-import xlsx template",
    response_class=Response,
)
async def download_template(
    _user: Annotated[User, Depends(require_user)],
) -> Response:
    content = build_template_xlsx()
    return Response(
        content=content,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": 'attachment; filename="basalam-products-template.xlsx"',
        },
    )


# ---------------------------------------------------------------------------
# GET /bulk/schema  — column metadata for client-side parsing + mapping
# ---------------------------------------------------------------------------

@router.get(
    "/bulk/schema",
    summary="Bulk-import column schema (metadata only, no products touched)",
)
async def bulk_schema(
    _user: Annotated[User, Depends(require_user)],
) -> dict:
    return {
        "columns": [
            {
                "key": c.key,
                "title": c.title,
                "required": c.required,
                "example": c.example,
                "description": c.description,
                "aliases": list(c.aliases),
            }
            for c in COLUMNS
        ],
    }


# ---------------------------------------------------------------------------
# POST /bulk/save-drafts  — persist parsed rows as DRAFTs (no withdraw, no AI)
# ---------------------------------------------------------------------------

@router.post(
    "/bulk/save-drafts",
    response_model=BulkSaveDraftsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save parsed rows as DRAFT products (no balance withdraw)",
)
async def save_drafts(
    request: BulkSaveDraftsRequest,
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BulkSaveDraftsResponse:
    created = await ProductService(db).save_drafts(user, request)
    return BulkSaveDraftsResponse(created=created)


# ---------------------------------------------------------------------------
# POST /bulk/save-drafts-from-files  — server-side sheet parse + ZIP images
# ---------------------------------------------------------------------------

@router.post(
    "/bulk/save-drafts-from-files",
    response_model=BulkSaveDraftsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Parse an uploaded sheet (xlsx/csv) and optional ZIP to save DRAFTs",
)
async def save_drafts_from_files(
    payload: BulkSaveDraftsFromFilesRequest,
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BulkSaveDraftsResponse:
    created = await BulkImportService(db).save_drafts_from_files(
        user,
        sheet_file_id=payload.sheet_file_id,
        zip_file_id=payload.zip_file_id,
        column_mapping=payload.column_mapping,
    )
    return BulkSaveDraftsResponse(created=created)


# ---------------------------------------------------------------------------
# POST /bulk/images  — bulk-attach images across multiple DRAFTs
# (defined BEFORE /{product_id}/images to avoid path collision)
# ---------------------------------------------------------------------------

@router.post(
    "/bulk/images",
    summary="Attach images to multiple DRAFT products in one transaction",
)
async def bulk_attach_images_endpoint(
    request: BulkAttachImagesRequest,
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    return await ProductService(db).attach_images_bulk(user, request)


# ---------------------------------------------------------------------------
# POST /confirm-all  — confirm multiple DRAFTs with pre-flight balance check
# (defined BEFORE /{product_id}/... to avoid path collision)
# ---------------------------------------------------------------------------

@router.post(
    "/confirm-all",
    response_model=ConfirmAllResponse,
    summary="Confirm many DRAFT products at once",
)
async def confirm_all(
    request: ConfirmAllRequest,
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConfirmAllResponse:
    return await ProductService(db).confirm_all(user, request.product_ids)


# ---------------------------------------------------------------------------
# POST /  — create a new product and enqueue the import job
# ---------------------------------------------------------------------------

@router.post(
    "/",
    response_model=ProductCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new product import job",
)
async def create_product(
    request: ProductCreateRequest,
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductCreatedResponse:
    product = await ProductService(db).create_with_images(user, request)
    return ProductCreatedResponse(product_id=product.id, status=product.status)


# ---------------------------------------------------------------------------
# GET /  — list products owned by the current user
# ---------------------------------------------------------------------------

@router.get(
    "/",
    response_model=PaginatedResponse[ProductListItem],
    summary="List products for the current user",
)
async def list_products(
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    product_status: ProductStatus | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse[ProductListItem]:
    return await ProductService(db).list_for_user(
        user, status=product_status, page=page, page_size=page_size,
    )


# ---------------------------------------------------------------------------
# GET /{product_id}  — retrieve a single product
# ---------------------------------------------------------------------------

@router.get(
    "/{product_id}",
    response_model=ProductOut,
    summary="Get product detail",
)
async def get_product(
    product_id: UUID,
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductOut:
    product = await ProductService(db).get_for_user(user, product_id)
    return ProductOut.model_validate(product)


# ---------------------------------------------------------------------------
# PATCH /{product_id}  — update editable fields, optionally push to Basalam
# ---------------------------------------------------------------------------

@router.patch(
    "/{product_id}",
    response_model=ProductOut,
    summary="Update product fields",
)
async def update_product(
    product_id: UUID,
    request: ProductUpdateRequest,
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductOut:
    product = await ProductService(db).update_for_user(user, product_id, request)
    await db.refresh(product)
    return ProductOut.model_validate(product)


# ---------------------------------------------------------------------------
# POST /{product_id}/resubmit  — re-queue a failed or ready product
# ---------------------------------------------------------------------------

@router.post(
    "/{product_id}/resubmit",
    response_model=ProductCreatedResponse,
    summary="Resubmit a failed or ready product for processing",
)
async def resubmit_product(
    product_id: UUID,
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductCreatedResponse:
    product = await ProductService(db).resubmit(user, product_id)
    return ProductCreatedResponse(product_id=product.id, status=product.status)


# ---------------------------------------------------------------------------
# POST /{product_id}/confirm  — withdraw + enqueue a DRAFT (bulk-imported)
# ---------------------------------------------------------------------------

@router.post(
    "/{product_id}/confirm",
    response_model=ProductCreatedResponse,
    summary="Confirm a DRAFT product → withdraw + enqueue processing",
)
async def confirm_draft(
    product_id: UUID,
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductCreatedResponse:
    product = await ProductService(db).confirm_draft(user, product_id)
    return ProductCreatedResponse(product_id=product.id, status=product.status)


# ---------------------------------------------------------------------------
# POST /{product_id}/images  — attach images to a single DRAFT/READY/FAILED
# ---------------------------------------------------------------------------

@router.post(
    "/{product_id}/images",
    response_model=ProductOut,
    summary="Append images to a DRAFT/READY/FAILED product",
)
async def attach_images(
    product_id: UUID,
    request: AttachImagesRequest,
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductOut:
    product = await ProductService(db).attach_images(user, product_id, request)
    return ProductOut.model_validate(product)


# ---------------------------------------------------------------------------
# DELETE /{product_id}  — delete a product (DRAFT / READY / FAILED only)
# ---------------------------------------------------------------------------

@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a product (only DRAFT / READY / FAILED; refunds the withdraw)",
)
async def delete_product(
    product_id: UUID,
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    await ProductService(db).delete_for_user(user, product_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# DELETE /{product_id}/images/{image_id}  — remove one image from a DRAFT
# ---------------------------------------------------------------------------

@router.delete(
    "/{product_id}/images/{image_id}",
    response_model=ProductOut,
    summary="Delete one image from a DRAFT product",
)
async def delete_image(
    product_id: UUID,
    image_id: UUID,
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductOut:
    product = await ProductService(db).delete_image(user, product_id, image_id)
    return ProductOut.model_validate(product)


# ---------------------------------------------------------------------------
# PATCH /{product_id}/images/order  — reorder images by ordered_ids list
# ---------------------------------------------------------------------------

@router.patch(
    "/{product_id}/images/order",
    response_model=ProductOut,
    summary="Reorder a product's images",
)
async def reorder_images(
    product_id: UUID,
    request: ReorderImagesRequest,
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductOut:
    product = await ProductService(db).reorder_images(user, product_id, request)
    return ProductOut.model_validate(product)


# ---------------------------------------------------------------------------
# POST /{product_id}/images/{image_id}/enhance  — run AI enhance on one image
# ---------------------------------------------------------------------------

@router.post(
    "/{product_id}/images/{image_id}/enhance",
    response_model=ProductOut,
    summary="Run AI enhancement on a single image",
)
async def enhance_one_image(
    product_id: UUID,
    image_id: UUID,
    user: Annotated[User, Depends(require_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductOut:
    product = await ProductService(db).enhance_one_image(user, product_id, image_id)
    return ProductOut.model_validate(product)
