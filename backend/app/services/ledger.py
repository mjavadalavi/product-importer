from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InsufficientBalance
from app.core.logging import get_logger
from app.db.models.transaction import GeneralType, ReferenceType, Transaction, TransactionStatus

logger = get_logger(__name__)


async def get_balance(db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await db.execute(
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
    return int(result.scalar() or 0)


async def get_available_balance(db: AsyncSession, user_id: uuid.UUID) -> int:
    completed_net_result = await db.execute(
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

    pending_withdraw_result = await db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.user_id == user_id,
            Transaction.general_type == GeneralType.WITHDRAW,
            Transaction.status == TransactionStatus.PENDING,
        )
    )
    pending_withdraws = int(pending_withdraw_result.scalar() or 0)
    return completed_net - pending_withdraws


async def create_transaction(
    db: AsyncSession,
    user_id: uuid.UUID,
    general_type: GeneralType,
    reference_type: ReferenceType,
    reference_id: int | None,
    amount: int,
    status: TransactionStatus = TransactionStatus.PENDING,
    note: str | None = None,
    idempotency_key: str | None = None,
) -> Transaction:
    if idempotency_key:
        existing_result = await db.execute(
            select(Transaction).where(Transaction.idempotency_key == idempotency_key)
        )
        existing = existing_result.scalar_one_or_none()
        if existing:
            logger.debug("idempotency hit key=%s tx_id=%s", idempotency_key, existing.id)
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
    db.add(tx)
    await db.flush()
    logger.info("created transaction user=%s type=%s ref=%s amount=%s status=%s", user_id, general_type, reference_type, amount, status)
    return tx


async def withdraw(
    db: AsyncSession,
    user_id: uuid.UUID,
    ref_type: ReferenceType,
    ref_id: int | None,
    amount: int,
    idempotency_key: str | None = None,
) -> Transaction:
    # Lock the user's transactions for the duration of this check to prevent races.
    await db.execute(
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .with_for_update()
        .limit(1)
    )
    available = await get_available_balance(db, user_id)
    if available < amount:
        logger.warning("insufficient balance user=%s available=%s required=%s", user_id, available, amount)
        raise InsufficientBalance(required=amount, available=available)

    return await create_transaction(
        db,
        user_id=user_id,
        general_type=GeneralType.WITHDRAW,
        reference_type=ref_type,
        reference_id=ref_id,
        amount=amount,
        status=TransactionStatus.PENDING,
        idempotency_key=idempotency_key,
    )


async def deposit(
    db: AsyncSession,
    user_id: uuid.UUID,
    ref_type: ReferenceType,
    ref_id: int | None,
    amount: int,
    status: TransactionStatus = TransactionStatus.PENDING,
    note: str | None = None,
    idempotency_key: str | None = None,
) -> Transaction:
    return await create_transaction(
        db,
        user_id=user_id,
        general_type=GeneralType.DEPOSIT,
        reference_type=ref_type,
        reference_id=ref_id,
        amount=amount,
        status=status,
        note=note,
        idempotency_key=idempotency_key,
    )


async def complete_transaction(db: AsyncSession, tx_id: uuid.UUID) -> Transaction:
    tx = await db.get(Transaction, tx_id)
    if tx is None:
        raise ValueError(f"transaction {tx_id} not found")
    tx.status = TransactionStatus.COMPLETED
    await db.flush()
    logger.info("completed transaction tx_id=%s", tx_id)
    return tx


async def reverse_transaction(db: AsyncSession, tx_id: uuid.UUID) -> Transaction:
    tx = await db.get(Transaction, tx_id)
    if tx is None:
        raise ValueError(f"transaction {tx_id} not found")
    tx.status = TransactionStatus.REVERSED
    await db.flush()
    logger.info("reversed transaction tx_id=%s", tx_id)
    return tx


async def request_topup(
    db: AsyncSession,
    user_id: uuid.UUID,
    amount: int,
) -> Transaction:
    return await deposit(
        db,
        user_id=user_id,
        ref_type=ReferenceType.REQUEST_AMOUNT,
        ref_id=None,
        amount=amount,
        status=TransactionStatus.PENDING,
        note="درخواست افزایش موجودی",
    )
