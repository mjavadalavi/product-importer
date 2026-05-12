from __future__ import annotations

import uuid
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InsufficientBalance
from app.db.models.transaction import GeneralType, ReferenceType, Transaction, TransactionStatus
from app.repositories.financial import TransactionRepository
from app.utils.logging import LoggerMixin


class LedgerService(LoggerMixin):
    """Service layer for all ledger / wallet operations.

    All mutating methods call ``await session.flush()`` internally but never
    commit.  The caller is responsible for committing (or rolling back) the
    surrounding unit-of-work.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.tx_repo = TransactionRepository(session)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def list_transactions(
        self,
        user_id: UUID,
        *,
        general_type: GeneralType | None = None,
        status: TransactionStatus | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Transaction], int]:
        return await self.tx_repo.list_for_user(
            user_id,
            general_type=general_type,
            status=status,
            page=page,
            page_size=page_size,
        )

    async def get_balance(self, user_id: UUID) -> int:
        """Return the settled (COMPLETED) net balance for *user_id*."""
        balance = await self.tx_repo.compute_balance(user_id)
        self.logger.debug("get_balance user=%s balance=%s", user_id, balance)
        return balance

    async def get_available_balance(self, user_id: UUID) -> int:
        """Return the available balance (settled minus pending withdraws)."""
        available = await self.tx_repo.compute_available_balance(user_id)
        self.logger.debug("get_available_balance user=%s available=%s", user_id, available)
        return available

    # ------------------------------------------------------------------
    # Generic create (used by the backward-compat shim)
    # ------------------------------------------------------------------

    async def create_transaction(
        self,
        user_id: UUID,
        general_type: GeneralType,
        reference_type: ReferenceType,
        reference_id: int | None,
        amount: int,
        status: TransactionStatus = TransactionStatus.PENDING,
        note: str | None = None,
        idempotency_key: str | None = None,
    ) -> Transaction:
        """Insert a transaction of any general_type.

        Idempotency-key check is performed first; if a matching row already
        exists it is returned without creating a duplicate.
        """
        if idempotency_key:
            existing = await self.tx_repo.find_by_idempotency_key(idempotency_key)
            if existing is not None:
                return existing

        tx = Transaction(
            user_id=user_id,
            general_type=general_type,
            reference_type=reference_type,
            reference_id=reference_id,
            amount=amount,
            status=status,
            note=note,
            idempotency_key=idempotency_key,
        )
        self.session.add(tx)
        await self.session.flush()
        self.logger.info(
            "create_transaction user=%s general_type=%s ref_type=%s amount=%s status=%s",
            user_id, general_type, reference_type, amount, status,
        )
        return tx

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    async def withdraw(
        self,
        *,
        user_id: UUID,
        reference_type: ReferenceType,
        reference_id: int | None,
        amount: int,
        idempotency_key: str | None = None,
    ) -> Transaction:
        """Lock the user's rows, verify available >= amount, insert PENDING WITHDRAW.

        Raises ``InsufficientBalance`` when the available balance is too low.
        """
        await self.tx_repo.lock_user_transactions_for_update(user_id)
        available = await self.get_available_balance(user_id)
        if available < amount:
            self.logger.warning(
                "insufficient balance user=%s available=%s required=%s",
                user_id, available, amount,
            )
            raise InsufficientBalance(required=amount, available=available)

        return await self.tx_repo.create_pending_withdraw(
            user_id=user_id,
            reference_type=reference_type,
            reference_id=reference_id,
            amount=amount,
            idempotency_key=idempotency_key,
        )

    async def deposit(
        self,
        *,
        user_id: UUID,
        reference_type: ReferenceType,
        reference_id: int | None,
        amount: int,
        status: TransactionStatus = TransactionStatus.PENDING,
        idempotency_key: str | None = None,
        note: str | None = None,
    ) -> Transaction:
        """Insert a DEPOSIT transaction with the given status."""
        return await self.tx_repo.create_deposit(
            user_id=user_id,
            reference_type=reference_type,
            reference_id=reference_id,
            amount=amount,
            status=status,
            idempotency_key=idempotency_key,
            note=note,
        )

    async def complete_transaction(self, tx_id: UUID) -> Transaction:
        """Set the transaction status to COMPLETED."""
        tx = await self.tx_repo.mark_status(tx_id, TransactionStatus.COMPLETED)
        self.logger.info("complete_transaction tx_id=%s", tx_id)
        return tx

    async def reverse_transaction(self, tx_id: UUID) -> Transaction:
        """Set the transaction status to REVERSED."""
        tx = await self.tx_repo.mark_status(tx_id, TransactionStatus.REVERSED)
        self.logger.info("reverse_transaction tx_id=%s", tx_id)
        return tx

    async def request_topup(self, user_id: UUID, amount: int) -> Transaction:
        """Create a PENDING deposit for a user top-up request."""
        return await self.deposit(
            user_id=user_id,
            reference_type=ReferenceType.REQUEST_AMOUNT,
            reference_id=None,
            amount=amount,
            status=TransactionStatus.PENDING,
            note="درخواست افزایش موجودی",
        )
