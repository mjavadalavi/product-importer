"""Backward-compatibility shim.

All module-level functions delegate to ``LedgerService``.  Existing callers
(including tests) that use ``await ledger.<fn>(db, ...)`` continue to work
without modification.
"""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.transaction import GeneralType, ReferenceType, Transaction, TransactionStatus
from app.services.ledger_service import LedgerService


async def get_balance(db: AsyncSession, user_id: uuid.UUID) -> int:
    return await LedgerService(db).get_balance(user_id)


async def get_available_balance(db: AsyncSession, user_id: uuid.UUID) -> int:
    return await LedgerService(db).get_available_balance(user_id)


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
    return await LedgerService(db).create_transaction(
        user_id=user_id,
        general_type=general_type,
        reference_type=reference_type,
        reference_id=reference_id,
        amount=amount,
        status=status,
        note=note,
        idempotency_key=idempotency_key,
    )


async def withdraw(
    db: AsyncSession,
    user_id: uuid.UUID,
    ref_type: ReferenceType,
    ref_id: int | None,
    amount: int,
    idempotency_key: str | None = None,
) -> Transaction:
    return await LedgerService(db).withdraw(
        user_id=user_id,
        reference_type=ref_type,
        reference_id=ref_id,
        amount=amount,
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
    return await LedgerService(db).deposit(
        user_id=user_id,
        reference_type=ref_type,
        reference_id=ref_id,
        amount=amount,
        status=status,
        idempotency_key=idempotency_key,
        note=note,
    )


async def complete_transaction(db: AsyncSession, tx_id: uuid.UUID) -> Transaction:
    return await LedgerService(db).complete_transaction(tx_id)


async def reverse_transaction(db: AsyncSession, tx_id: uuid.UUID) -> Transaction:
    return await LedgerService(db).reverse_transaction(tx_id)


async def request_topup(
    db: AsyncSession,
    user_id: uuid.UUID,
    amount: int,
) -> Transaction:
    return await LedgerService(db).request_topup(user_id, amount)
