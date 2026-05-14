"""Persist per-request AI usage and cost records.

Used right after each OpenRouter call (analyze / enhance) so we can attribute
spend to a user/product and audit cost per generation. Failures to write the
audit row never fail the calling operation — we log and swallow.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ai_call import AiCall, AiCallKind, AiCallStatus
from app.utils.logging import LoggerMixin


class AiCallService(LoggerMixin):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record_success(
        self,
        *,
        user_id: UUID,
        product_id: UUID | None,
        kind: AiCallKind,
        usage: dict[str, Any] | None,
    ) -> AiCall | None:
        """Insert one SUCCESS row from an OpenRouterService.last_usage dict."""
        if not usage:
            return None
        return await self._insert(
            user_id=user_id,
            product_id=product_id,
            kind=kind,
            status=AiCallStatus.SUCCESS,
            model=str(usage.get("model") or "unknown"),
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
            cost_usd=float(usage.get("cost_usd") or 0),
            generation_id=usage.get("generation_id"),
            error_message=None,
        )

    async def record_error(
        self,
        *,
        user_id: UUID,
        product_id: UUID | None,
        kind: AiCallKind,
        model: str,
        error_message: str,
    ) -> AiCall:
        return await self._insert(
            user_id=user_id,
            product_id=product_id,
            kind=kind,
            status=AiCallStatus.ERROR,
            model=model,
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            cost_usd=0,
            generation_id=None,
            error_message=error_message[:2000],
        )

    async def _insert(self, **fields: Any) -> AiCall:
        row = AiCall(**fields)
        self.session.add(row)
        try:
            await self.session.flush()
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("AiCallService insert failed: %s", exc)
        return row
