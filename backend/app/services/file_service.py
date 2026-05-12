"""Service layer for generic file upload and retrieval.

Responsibilities:
- Cap incoming uploads at ``settings.max_upload_mb``.
- Compute SHA-256 fingerprint for deduplication/integrity checks.
- Persist the raw bytes under a sharded directory structure:
  ``<storage_dir>/<sha256[:2]>/<sha256[2:4]>/<sha256>__<safe_filename>``.
- Insert a ``File`` ORM row and return it to the caller.
- Provide helpers for reading bytes back from disk and producing
  data-URL strings (needed by the existing ``product_images.original_url``
  compatibility layer in Wave B).
"""
from __future__ import annotations

import base64
import hashlib
import re
import uuid
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.file import File, FileStatus
from app.db.models.user import User
from app.repositories.file_repo import FileRepository
from app.utils.logging import LoggerMixin


def _safe_filename(name: str) -> str:
    """Strip path separators and reduce to a filesystem-safe basename.

    Replaces any character that is not alphanumeric, dash, dot, or underscore
    with an underscore.  Limits length to 200 characters so the full sharded
    path stays well under the 255-byte filename limit.
    """
    basename = Path(name).name  # drop any directory components
    safe = re.sub(r"[^\w\-.]", "_", basename, flags=re.UNICODE)
    return safe[:200] or "file"


class FileService(LoggerMixin):
    """Business logic for the generic file upload subsystem."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = FileRepository(session)

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------

    async def upload(
        self,
        *,
        user: User,
        upload: UploadFile,
        kind: str,
        target_type: str | None = None,
        target_id: UUID | None = None,
        metadata: dict | None = None,
    ) -> File:
        """Persist an uploaded file and return the new ``File`` row.

        Steps:
        1. Read bytes; reject if larger than ``settings.max_upload_mb``.
        2. Compute SHA-256 fingerprint.
        3. Build sharded path: ``<sha[:2]>/<sha[2:4]>/<sha>__<safe_filename>``.
        4. Write bytes to disk under ``settings.file_storage_dir``.
        5. Insert the ``File`` row with ``status=READY`` and a self-referential
           ``public_url`` pointing to the download endpoint.
        6. Commit and return the persisted row.

        Args:
            user: The authenticated user who owns this file.
            upload: The incoming multipart ``UploadFile``.
            kind: Semantic kind (must be in ``settings.allowed_upload_kinds``).
            target_type: Optional domain entity type this file belongs to.
            target_id: Optional domain entity UUID this file belongs to.
            metadata: Optional free-form dict stored on the row.

        Returns:
            The persisted ``File`` ORM instance.

        Raises:
            HTTPException 400: When ``kind`` is not allowed.
            HTTPException 413: When the file exceeds the size cap.
        """
        settings = get_settings()

        # Validate kind early so we fail fast
        if kind not in settings.allowed_upload_kinds:
            raise HTTPException(
                status_code=400,
                detail=f"نوع فایل مجاز نیست. مقادیر مجاز: {', '.join(settings.allowed_upload_kinds)}",
            )

        max_bytes = settings.max_upload_mb * 1024 * 1024

        # Read the entire upload into memory (one read, bounded by the cap).
        # We read max_bytes + 1 so we can detect an oversize payload without
        # consuming an unbounded stream.
        raw = await upload.read(max_bytes + 1)
        if len(raw) > max_bytes:
            self.logger.warning(
                "upload size_exceeded user_id=%s kind=%s size=%s limit_mb=%s",
                user.id, kind, len(raw), settings.max_upload_mb,
            )
            raise HTTPException(
                status_code=413,
                detail=f"حجم فایل بیش از حد مجاز است. حداکثر مجاز: {settings.max_upload_mb} مگابایت",
            )

        mime = (upload.content_type or "application/octet-stream").strip()
        original_name = upload.filename or "upload"
        return await self._store_bytes(
            user=user,
            raw=raw,
            original_name=original_name,
            mime=mime,
            kind=kind,
            target_type=target_type,
            target_id=target_id,
            metadata=metadata,
        )

    async def upload_from_bytes(
        self,
        *,
        user: User,
        raw: bytes,
        filename: str,
        mime: str,
        kind: str,
        target_type: str | None = None,
        target_id: UUID | None = None,
        metadata: dict | None = None,
    ) -> File:
        """Persist raw bytes directly (no UploadFile required) and return the new ``File`` row.

        Useful for server-side image extraction from ZIP archives.

        Args:
            user: The authenticated user who owns this file.
            raw: Raw file bytes to persist.
            filename: Original filename (used for safe storage name).
            mime: MIME type string (e.g. ``"image/jpeg"``).
            kind: Semantic kind (must be in ``settings.allowed_upload_kinds``).
            target_type: Optional domain entity type this file belongs to.
            target_id: Optional domain entity UUID this file belongs to.
            metadata: Optional free-form dict stored on the row.

        Returns:
            The persisted ``File`` ORM instance.

        Raises:
            HTTPException 400: When ``kind`` is not allowed.
            HTTPException 413: When the file exceeds the size cap.
        """
        settings = get_settings()

        if kind not in settings.allowed_upload_kinds:
            raise HTTPException(
                status_code=400,
                detail=f"نوع فایل مجاز نیست. مقادیر مجاز: {', '.join(settings.allowed_upload_kinds)}",
            )

        max_bytes = settings.max_upload_mb * 1024 * 1024
        if len(raw) > max_bytes:
            self.logger.warning(
                "upload_from_bytes size_exceeded user_id=%s kind=%s size=%s limit_mb=%s",
                user.id, kind, len(raw), settings.max_upload_mb,
            )
            raise HTTPException(
                status_code=413,
                detail=f"حجم فایل بیش از حد مجاز است. حداکثر مجاز: {settings.max_upload_mb} مگابایت",
            )

        return await self._store_bytes(
            user=user,
            raw=raw,
            original_name=filename,
            mime=mime,
            kind=kind,
            target_type=target_type,
            target_id=target_id,
            metadata=metadata,
        )

    async def _store_bytes(
        self,
        *,
        user: User,
        raw: bytes,
        original_name: str,
        mime: str,
        kind: str,
        target_type: str | None,
        target_id: UUID | None,
        metadata: dict | None,
    ) -> File:
        """Shared storage helper: compute hash, write to disk, insert File row, commit.

        This is the common implementation used by both ``upload`` (which reads
        from an ``UploadFile``) and ``upload_from_bytes`` (which receives raw
        bytes directly).
        """
        settings = get_settings()
        size_bytes = len(raw)
        sha256 = hashlib.sha256(raw).hexdigest()

        safe_name = _safe_filename(original_name)
        shard_a, shard_b = sha256[:2], sha256[2:4]
        relative_path = f"{shard_a}/{shard_b}/{sha256}__{safe_name}"

        storage_root = Path(settings.file_storage_dir)
        dest = storage_root / relative_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)

        self.logger.debug(
            "store_bytes user_id=%s kind=%s sha256=%s path=%s size=%s",
            user.id, kind, sha256[:16], relative_path, size_bytes,
        )

        file_id = uuid.uuid4()
        public_url = f"/api/v1/files/{file_id}/download"

        file = File(
            id=file_id,
            user_id=user.id,
            kind=kind,
            target_type=target_type,
            target_id=target_id,
            storage_path=relative_path,
            public_url=public_url,
            mime=mime,
            size_bytes=size_bytes,
            sha256=sha256,
            filename=original_name[:512],
            status=FileStatus.READY,
            file_metadata=metadata or {},
        )
        self.session.add(file)
        await self.session.flush()
        await self.session.refresh(file)
        await self.session.commit()

        self.logger.info(
            "store_bytes complete file_id=%s user_id=%s kind=%s sha256=%s size=%s",
            file.id, user.id, kind, sha256[:16], size_bytes,
        )
        return file

    # ------------------------------------------------------------------
    # Retrieval helpers
    # ------------------------------------------------------------------

    async def get_for_user(self, file_id: UUID, user: User) -> File:
        """Return the ``File`` owned by ``user`` or raise HTTP 404.

        Args:
            file_id: UUID of the requested file.
            user: The authenticated user requesting the file.

        Returns:
            The ``File`` ORM instance.

        Raises:
            HTTPException 404: When the file does not exist or is not owned by
                the user.
        """
        file = await self.repo.get_for_user(file_id, user.id)
        if file is None:
            self.logger.debug(
                "get_for_user not found file_id=%s user_id=%s", file_id, user.id
            )
            raise HTTPException(status_code=404, detail="فایل یافت نشد")
        return file

    async def delete_for_user(self, file_id: UUID, user: User) -> None:
        """Soft-delete the file owned by ``user``.

        Sets ``status=DELETED`` without removing the file from disk.  Wave B
        can sweep orphaned disk files as a background job.

        Args:
            file_id: UUID of the file to delete.
            user: The authenticated user performing the deletion.

        Raises:
            HTTPException 404: When the file does not exist or is not owned by
                the user.
        """
        file = await self.get_for_user(file_id, user)
        await self.repo.mark_deleted(file.id)
        await self.session.commit()
        self.logger.info(
            "delete_for_user file_id=%s user_id=%s", file_id, user.id
        )

    async def read_bytes(self, file: File) -> bytes:
        """Read and return the raw bytes for ``file`` from the storage directory.

        Args:
            file: A persisted ``File`` ORM instance.

        Returns:
            Raw file bytes.

        Raises:
            HTTPException 404: When the file is missing from disk.
        """
        settings = get_settings()
        path = Path(settings.file_storage_dir) / file.storage_path
        if not path.exists():
            self.logger.error(
                "read_bytes missing from disk file_id=%s path=%s", file.id, path
            )
            raise HTTPException(status_code=404, detail="فایل روی دیسک یافت نشد")
        return path.read_bytes()

    async def data_url(self, file: File) -> str:
        """Return a ``data:<mime>;base64,<b64>`` string for the file.

        Used by the existing product-image compatibility layer (Wave B) which
        stores data-URLs in ``product_images.original_url``.

        Args:
            file: A persisted ``File`` ORM instance.

        Returns:
            Base64-encoded data URL string.
        """
        raw = await self.read_bytes(file)
        b64 = base64.b64encode(raw).decode("ascii")
        return f"data:{file.mime};base64,{b64}"

    async def attach_to_target(
        self,
        file: File,
        target_type: str,
        target_id: UUID,
    ) -> File:
        """Bind an existing file to a domain resource and persist the change.

        Args:
            file: The ``File`` row to update.
            target_type: Domain entity type (e.g. ``"product"``).
            target_id: Domain entity UUID.

        Returns:
            The updated ``File`` ORM instance.
        """
        file.target_type = target_type
        file.target_id = target_id
        self.session.add(file)
        await self.session.flush()
        await self.session.refresh(file)
        await self.session.commit()
        self.logger.info(
            "attach_to_target file_id=%s target_type=%s target_id=%s",
            file.id, target_type, target_id,
        )
        return file
