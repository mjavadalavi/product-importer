"""Generic file upload / download / management endpoints.

All routes sit under ``/files`` and are mounted on the v1 router.

Upload flow:
    POST /files   multipart form with ``file``, ``kind``, optional metadata
                  -> returns FileOut JSON

Download flow:
    GET  /files/{file_id}/download  -> StreamingResponse with original mime type

Metadata:
    GET  /files/{file_id}  -> FileOut JSON

Soft delete:
    DELETE /files/{file_id}  -> 204 No Content
"""
from __future__ import annotations

import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, require_user
from app.db.models.user import User
from app.schemas.files import FileOut
from app.services.file_service import FileService
from app.utils.logging import get_logger

router = APIRouter(prefix="/files", tags=["files"])
logger = get_logger(__name__)


@router.post("", response_model=FileOut, status_code=201)
async def upload_file(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_user)],
    file: UploadFile,
    kind: str = Form(...),
    target_type: str | None = Form(default=None),
    target_id: UUID | None = Form(default=None),
    metadata: str | None = Form(default=None),
) -> FileOut:
    """Upload a file and receive a canonical ``FileOut`` record in response.

    The ``metadata`` form field must be a JSON object string when provided;
    invalid JSON will be silently ignored (treated as empty object).
    """
    parsed_metadata: dict = {}
    if metadata:
        try:
            parsed_metadata = json.loads(metadata)
            if not isinstance(parsed_metadata, dict):
                parsed_metadata = {}
        except (json.JSONDecodeError, ValueError):
            logger.debug("upload_file invalid metadata JSON — ignoring user_id=%s", user.id)
            parsed_metadata = {}

    logger.info(
        "upload_file user_id=%s kind=%s target_type=%s target_id=%s filename=%s",
        user.id, kind, target_type, target_id, file.filename,
    )

    service = FileService(db)
    result = await service.upload(
        user=user,
        upload=file,
        kind=kind,
        target_type=target_type,
        target_id=target_id,
        metadata=parsed_metadata,
    )
    return FileOut.model_validate(result)


@router.get("/{file_id}", response_model=FileOut)
async def get_file_metadata(
    file_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_user)],
) -> FileOut:
    """Return the metadata for a file owned by the authenticated user."""
    service = FileService(db)
    file = await service.get_for_user(file_id, user)
    return FileOut.model_validate(file)


@router.get("/{file_id}/download")
async def download_file(
    file_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_user)],
) -> StreamingResponse:
    """Stream the raw file bytes to the client.

    The response uses the original MIME type and sets
    ``Content-Disposition: attachment`` with the original filename so browsers
    save it under the right name.
    """
    service = FileService(db)
    file = await service.get_for_user(file_id, user)
    raw = await service.read_bytes(file)

    logger.debug(
        "download_file file_id=%s user_id=%s mime=%s size=%s",
        file_id, user.id, file.mime, file.size_bytes,
    )

    # Sanitise the filename for the Content-Disposition header
    safe_disposition_name = file.filename.replace('"', '\\"')

    def _iter_bytes():
        yield raw

    return StreamingResponse(
        _iter_bytes(),
        media_type=file.mime,
        headers={
            "Content-Disposition": f'attachment; filename="{safe_disposition_name}"',
            "Content-Length": str(file.size_bytes),
        },
    )


@router.delete("/{file_id}", status_code=204, response_model=None)
async def delete_file(
    file_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_user)],
) -> None:
    """Soft-delete a file owned by the authenticated user.

    The file record is marked as DELETED in the database but the bytes on
    disk are preserved for a future garbage-collection sweep.
    """
    logger.info("delete_file file_id=%s user_id=%s", file_id, user.id)
    service = FileService(db)
    await service.delete_for_user(file_id, user)
