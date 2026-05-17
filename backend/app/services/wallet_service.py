"""Wallet top-up flow that talks to the Shopyaar payment bridge.

Two-step flow:

    1. start_topup(user, amount)
        - Asks the payment bridge for a token + redirect URL.
        - Inserts a PENDING DEPOSIT transaction with idempotency_key = token
          so we can look it up at verification time.
        - Returns the URL the browser should be redirected to.

    2. verify_topup(authority)
        - Asks the bridge whether the payment for that authority succeeded.
        - Marks the matching PENDING transaction COMPLETED on success or
          REVERSED on failure.
        - Returns {success, transaction_id} for the frontend callback page.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppException
from app.db.models.transaction import (
    GeneralType,
    ReferenceType,
    Transaction,
    TransactionStatus,
)
from app.db.models.user import User
from app.services.ledger_service import LedgerService
from app.services.payment import (
    PaymentBridge,
    PaymentBridgeError,
    get_payment_bridge,
)
from app.utils.logging import LoggerMixin


class WalletError(AppException):
    """User-facing wallet error (mapped to HTTP 4xx by the route layer)."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass
class StartTopupResult:
    transaction_id: UUID
    token: str
    url: str
    bypass: bool


@dataclass
class VerifyTopupResult:
    transaction_id: UUID | None
    status: TransactionStatus
    success: bool
    amount: int
    ref_id: str | None


class WalletService(LoggerMixin):
    MIN_TOPUP = 1_000
    MAX_TOPUP = 100_000_000

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.ledger = LedgerService(session)
        self.payment: PaymentBridge = get_payment_bridge()
        self._settings = get_settings()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start_topup(self, user: User, amount: int) -> StartTopupResult:
        if amount < self.MIN_TOPUP or amount > self.MAX_TOPUP:
            raise WalletError(
                f"مبلغ باید بین {self.MIN_TOPUP:,} و {self.MAX_TOPUP:,} تومان باشد.",
                status_code=400,
            )

        callback_url = self._settings.payment_bridge_callback_url or None
        try:
            bridge_response = await self.payment.create_payment(
                amount=amount,
                callback_url=callback_url,
                description="افزایش موجودی کیف پول",
            )
        except PaymentBridgeError as exc:
            self.logger.error("Payment bridge create failed user=%s err=%s", user.id, exc)
            raise WalletError(
                "خطا در اتصال به درگاه پرداخت. لطفاً مجدداً تلاش کنید.",
                status_code=502,
            ) from exc

        if not bridge_response.token or not bridge_response.url:
            raise WalletError("پاسخ درگاه پرداخت معتبر نبود.", status_code=502)

        tx = await self.ledger.create_transaction(
            user_id=user.id,
            general_type=GeneralType.DEPOSIT,
            reference_type=ReferenceType.PAYMENT,
            reference_id=None,
            amount=amount,
            status=TransactionStatus.PENDING,
            note="افزایش موجودی از طریق درگاه پرداخت",
            idempotency_key=bridge_response.token,
        )
        await self.session.commit()
        await self.session.refresh(tx)

        return StartTopupResult(
            transaction_id=tx.id,
            token=bridge_response.token,
            url=bridge_response.url,
            bypass=bridge_response.bypass,
        )

    async def verify_topup(self, authority: str) -> VerifyTopupResult:
        if not authority:
            raise WalletError("شناسهٔ پرداخت ارسال نشده است.", status_code=400)

        tx = await self._find_pending_by_token(authority)
        if tx is None:
            self.logger.warning("verify_topup: no PENDING tx for authority=%s", authority)
            raise WalletError("تراکنش متناظر با این پرداخت یافت نشد.", status_code=404)

        try:
            bridge_response = await self.payment.verify_payment(token=authority)
        except PaymentBridgeError as exc:
            self.logger.error(
                "Payment bridge verify failed authority=%s err=%s",
                authority, exc,
            )
            # Bridge failure does NOT auto-reverse — the user can retry verify.
            raise WalletError(
                "خطا در تأیید پرداخت با درگاه. لطفاً کمی بعد دوباره تلاش کنید.",
                status_code=502,
            ) from exc

        success = bridge_response.success
        ref_id = bridge_response.ref_id

        if success:
            await self.ledger.complete_transaction(tx.id)
            if ref_id:
                tx.note = f"{tx.note or ''} | ref_id={ref_id}".strip(" |")
        else:
            await self.ledger.reverse_transaction(tx.id)

        await self.session.commit()
        await self.session.refresh(tx)

        return VerifyTopupResult(
            transaction_id=tx.id,
            status=tx.status,
            success=success,
            amount=int(tx.amount),
            ref_id=ref_id,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _find_pending_by_token(self, token: str) -> Transaction | None:
        result = await self.session.execute(
            select(Transaction).where(
                Transaction.idempotency_key == token,
                Transaction.general_type == GeneralType.DEPOSIT,
                Transaction.reference_type == ReferenceType.PAYMENT,
            )
        )
        return result.scalar_one_or_none()
