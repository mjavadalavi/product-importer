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
from typing import Any
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
from app.services.payment import PaymentService
from app.services.payment.payment_service import PaymentBridgeError
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
        self.payment = PaymentService()
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
        # The bridge requires user_phone for SMS / reconciliation. The User
        # model only stores basalam_user_id (no phone column), so derive a
        # stable phone-shaped identifier from it. When/if a real phone is
        # captured during onboarding, swap this to use user.phone directly.
        user_phone = self._user_phone_for_bridge(user)
        # We store ledger amounts in Toman everywhere internally, but the
        # Iranian payment bridge (pay.ejourney.ir) expects Rial. Convert
        # at the boundary so the user sees Toman and the gateway sees Rial.
        amount_rial = amount * 10
        try:
            bridge_response = await self.payment.create_payment(
                amount=amount_rial,
                callback_url=callback_url,
                user_phone=user_phone,
            )
        except PaymentBridgeError as exc:
            self.logger.error("Payment bridge create failed user=%s err=%s", user.id, exc)
            raise WalletError(
                "خطا در اتصال به درگاه پرداخت. لطفاً مجدداً تلاش کنید.",
                status_code=502,
            ) from exc

        token = (bridge_response or {}).get("token")
        # Bridge returns the redirect URL under `payment_url`; older mocks
        # used `url`, so accept both for forward compatibility.
        url = (bridge_response or {}).get("payment_url") or (bridge_response or {}).get("url")
        if not token or not url:
            raise WalletError("پاسخ درگاه پرداخت معتبر نبود.", status_code=502)

        tx = await self.ledger.create_transaction(
            user_id=user.id,
            general_type=GeneralType.DEPOSIT,
            reference_type=ReferenceType.PAYMENT,
            reference_id=None,
            amount=amount,
            status=TransactionStatus.PENDING,
            note="افزایش موجودی از طریق درگاه پرداخت",
            idempotency_key=str(token),
        )
        await self.session.commit()
        await self.session.refresh(tx)

        return StartTopupResult(
            transaction_id=tx.id,
            token=str(token),
            url=str(url),
            bypass=bool(bridge_response.get("bypass")),
        )

    async def verify_topup(self, authority: str) -> VerifyTopupResult:
        if not authority:
            raise WalletError("شناسهٔ پرداخت ارسال نشده است.", status_code=400)

        tx = await self._find_pending_by_token(authority)
        if tx is None:
            self.logger.warning("verify_topup: no PENDING tx for authority=%s", authority)
            raise WalletError("تراکنش متناظر با این پرداخت یافت نشد.", status_code=404)

        try:
            bridge_response: dict[str, Any] = await self.payment.verify_payment(token=authority)
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

        success = bool((bridge_response or {}).get("status"))
        ref_id = (bridge_response or {}).get("ref_id")

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
            ref_id=str(ref_id) if ref_id else None,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _user_phone_for_bridge(user: User) -> str:
        """Return a phone-shaped string for the payment bridge.

        Until product-importer stores real phone numbers, derive a stable
        11-digit value from the user's basalam_user_id so each user gets a
        unique identifier but the bridge's string-format check still passes.
        """
        suffix = f"{int(user.basalam_user_id):09d}"[-9:]
        return f"09{suffix}"

    async def _find_pending_by_token(self, token: str) -> Transaction | None:
        result = await self.session.execute(
            select(Transaction).where(
                Transaction.idempotency_key == token,
                Transaction.general_type == GeneralType.DEPOSIT,
                Transaction.reference_type == ReferenceType.PAYMENT,
            )
        )
        return result.scalar_one_or_none()
