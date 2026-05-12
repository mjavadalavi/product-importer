from __future__ import annotations

import uuid
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.transaction import GeneralType, ReferenceType, Transaction, TransactionStatus
from app.repositories.base import BaseRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)


class TransactionRepository(BaseRepository[Transaction]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Transaction, session)

    async def find_by_idempotency_key(self, key: str | None) -> Transaction | None:
        """Return the transaction matching the given idempotency key, or None."""
        if key is None:
            return None

        result = await self.session.execute(
            select(Transaction).where(Transaction.idempotency_key == key)
        )
        tx = result.scalar_one_or_none()
        if tx is not None:
            logger.debug("idempotency hit key=%s tx_id=%s", key, tx.id)
        return tx

    async def list_for_user(
        self,
        user_id: UUID,
        *,
        general_type: GeneralType | None = None,
        status: TransactionStatus | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Transaction], int]:
        """
        Return a paginated list of transactions for a user alongside the total count.

        Filters are optional; all matching rows are counted before pagination.
        """
        base_query = select(Transaction).where(Transaction.user_id == user_id)

        if general_type is not None:
            base_query = base_query.where(Transaction.general_type == general_type)
        if status is not None:
            base_query = base_query.where(Transaction.status == status)

        count_query = select(func.count()).select_from(base_query.subquery())
        count_result = await self.session.execute(count_query)
        total: int = count_result.scalar() or 0

        offset = (page - 1) * page_size
        rows_result = await self.session.execute(
            base_query.order_by(Transaction.created_at.desc()).offset(offset).limit(page_size)
        )
        rows = list(rows_result.scalars().all())

        logger.debug(
            "list_for_user user=%s general_type=%s status=%s page=%s page_size=%s total=%s",
            user_id, general_type, status, page, page_size, total,
        )
        return rows, total

    async def compute_balance(self, user_id: UUID) -> int:
        """SUM(amount * sign(general_type)) WHERE status=COMPLETED."""
        result = await self.session.execute(
            select(
                func.coalesce(
                    func.sum(
                        case(
                            (Transaction.general_type == GeneralType.DEPOSIT, Transaction.amount),
                            else_=-Transaction.amount,
                        )
                    ),
                    0,
                )
            ).where(
                Transaction.user_id == user_id,
                Transaction.status == TransactionStatus.COMPLETED,
            )
        )
        balance = int(result.scalar() or 0)
        logger.debug("compute_balance user=%s balance=%s", user_id, balance)
        return balance

    async def compute_available_balance(self, user_id: UUID) -> int:
        """COMPLETED net minus PENDING WITHDRAW total."""
        completed_net_result = await self.session.execute(
            select(
                func.coalesce(
                    func.sum(
                        case(
                            (Transaction.general_type == GeneralType.DEPOSIT, Transaction.amount),
                            else_=-Transaction.amount,
                        )
                    ),
                    0,
                )
            ).where(
                Transaction.user_id == user_id,
                Transaction.status == TransactionStatus.COMPLETED,
            )
        )
        completed_net = int(completed_net_result.scalar() or 0)

        pending_withdraw_result = await self.session.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.user_id == user_id,
                Transaction.general_type == GeneralType.WITHDRAW,
                Transaction.status == TransactionStatus.PENDING,
            )
        )
        pending_withdraws = int(pending_withdraw_result.scalar() or 0)

        available = completed_net - pending_withdraws
        logger.debug(
            "compute_available_balance user=%s completed_net=%s pending_withdraws=%s available=%s",
            user_id, completed_net, pending_withdraws, available,
        )
        return available

    async def lock_user_transactions_for_update(self, user_id: UUID) -> None:
        """
        Acquire a pessimistic row-level lock on one of the user's transactions.

        This serialises concurrent withdraw attempts for the same user.
        Mirrors the FOR UPDATE logic in app/services/ledger.py:withdraw.
        """
        await self.session.execute(
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .with_for_update()
            .limit(1)
        )
        logger.debug("lock_user_transactions_for_update user=%s", user_id)

    async def create_pending_withdraw(
        self,
        *,
        user_id: UUID,
        reference_type: ReferenceType,
        reference_id: int | None,
        amount: int,
        idempotency_key: str | None = None,
        note: str | None = None,
    ) -> Transaction:
        """
        Insert a new WITHDRAW transaction with PENDING status.

        Checks the idempotency key first and returns the existing row when
        a match is found, avoiding duplicate inserts.
        """
        existing = await self.find_by_idempotency_key(idempotency_key)
        if existing is not None:
            return existing

        tx = Transaction(
            user_id=user_id,
            general_type=GeneralType.WITHDRAW,
            reference_type=reference_type,
            reference_id=reference_id,
            amount=amount,
            status=TransactionStatus.PENDING,
            note=note,
            idempotency_key=idempotency_key,
        )
        self.session.add(tx)
        await self.session.flush()
        logger.info(
            "create_pending_withdraw user=%s ref_type=%s ref_id=%s amount=%s",
            user_id, reference_type, reference_id, amount,
        )
        return tx

    async def create_deposit(
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
        """
        Insert a new DEPOSIT transaction.

        Checks the idempotency key first and returns the existing row when
        a match is found, avoiding duplicate inserts.
        """
        existing = await self.find_by_idempotency_key(idempotency_key)
        if existing is not None:
            return existing

        tx = Transaction(
            user_id=user_id,
            general_type=GeneralType.DEPOSIT,
            reference_type=reference_type,
            reference_id=reference_id,
            amount=amount,
            status=status,
            note=note,
            idempotency_key=idempotency_key,
        )
        self.session.add(tx)
        await self.session.flush()
        logger.info(
            "create_deposit user=%s ref_type=%s ref_id=%s amount=%s status=%s",
            user_id, reference_type, reference_id, amount, status,
        )
        return tx

    async def mark_status(self, tx_id: UUID, status: TransactionStatus) -> Transaction:
        """
        Update a transaction's status by primary key.

        Raises ValueError if no transaction with the given id exists.
        """
        tx = await self.session.get(Transaction, tx_id)
        if tx is None:
            raise ValueError(f"تراکنش {tx_id} یافت نشد")
        tx.status = status
        await self.session.flush()
        logger.info("mark_status tx_id=%s new_status=%s", tx_id, status)
        return tx
