"""
Unit tests for app.services.ledger — all database operations only, no HTTP.
"""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InsufficientBalance
from app.db.models.transaction import GeneralType, ReferenceType, Transaction, TransactionStatus
from app.services import ledger


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _completed_deposit(db: AsyncSession, user_id, amount: int) -> Transaction:
    return await ledger.deposit(
        db,
        user_id=user_id,
        ref_type=ReferenceType.GIFT,
        ref_id=None,
        amount=amount,
        status=TransactionStatus.COMPLETED,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_balance_zero_for_new_user(db_session: AsyncSession, make_user):
    user = await make_user()
    balance = await ledger.get_balance(db_session, user.id)
    assert balance == 0


async def test_completed_deposit_adds_to_balance(db_session: AsyncSession, make_user):
    user = await make_user()
    await _completed_deposit(db_session, user.id, 10)
    balance = await ledger.get_balance(db_session, user.id)
    assert balance == 10


async def test_pending_deposit_does_not_count(db_session: AsyncSession, make_user):
    user = await make_user()
    await ledger.deposit(
        db_session,
        user_id=user.id,
        ref_type=ReferenceType.GIFT,
        ref_id=None,
        amount=10,
        status=TransactionStatus.PENDING,
    )
    balance = await ledger.get_balance(db_session, user.id)
    assert balance == 0


async def test_completed_withdraw_subtracts(db_session: AsyncSession, make_user):
    user = await make_user()
    await _completed_deposit(db_session, user.id, 10)

    tx = await ledger.withdraw(
        db_session,
        user_id=user.id,
        ref_type=ReferenceType.PRODUCT,
        ref_id=None,
        amount=3,
    )
    # Complete the pending withdraw so it counts against balance.
    await ledger.complete_transaction(db_session, tx.id)

    balance = await ledger.get_balance(db_session, user.id)
    assert balance == 7


async def test_withdraw_raises_on_insufficient(db_session: AsyncSession, make_user):
    user = await make_user()
    with pytest.raises(InsufficientBalance):
        await ledger.withdraw(
            db_session,
            user_id=user.id,
            ref_type=ReferenceType.PRODUCT,
            ref_id=None,
            amount=1,
        )


async def test_pending_withdraw_reduces_available_but_not_balance(
    db_session: AsyncSession, make_user
):
    user = await make_user()
    await _completed_deposit(db_session, user.id, 10)

    # Withdraw leaves a PENDING transaction — reduces available but not settled balance.
    await ledger.withdraw(
        db_session,
        user_id=user.id,
        ref_type=ReferenceType.PRODUCT,
        ref_id=None,
        amount=3,
    )

    available = await ledger.get_available_balance(db_session, user.id)
    balance = await ledger.get_balance(db_session, user.id)

    assert available == 7
    assert balance == 10  # PENDING withdraw is not yet COMPLETED, so settled balance unchanged


async def test_reversed_withdraw_restores_available(db_session: AsyncSession, make_user):
    user = await make_user()
    await _completed_deposit(db_session, user.id, 10)

    tx = await ledger.withdraw(
        db_session,
        user_id=user.id,
        ref_type=ReferenceType.PRODUCT,
        ref_id=None,
        amount=3,
    )

    # Available should be 7 after pending withdraw.
    assert await ledger.get_available_balance(db_session, user.id) == 7

    # Reversing the pending withdraw should free the held amount.
    await ledger.reverse_transaction(db_session, tx.id)

    assert await ledger.get_available_balance(db_session, user.id) == 10


async def test_idempotency_key_returns_existing(db_session: AsyncSession, make_user):
    user = await make_user()
    await _completed_deposit(db_session, user.id, 50)

    key = "idempotency-test-key-x"
    tx1 = await ledger.deposit(
        db_session,
        user_id=user.id,
        ref_type=ReferenceType.PAYMENT,
        ref_id=None,
        amount=20,
        status=TransactionStatus.COMPLETED,
        idempotency_key=key,
    )
    tx2 = await ledger.deposit(
        db_session,
        user_id=user.id,
        ref_type=ReferenceType.PAYMENT,
        ref_id=None,
        amount=20,
        status=TransactionStatus.COMPLETED,
        idempotency_key=key,
    )

    # Both calls should return the same transaction object.
    assert tx1.id == tx2.id

    # Only one extra deposit should exist (the idempotent one), not two.
    from sqlalchemy import select, func
    count_result = await db_session.execute(
        select(func.count(Transaction.id)).where(
            Transaction.user_id == user.id,
            Transaction.idempotency_key == key,
        )
    )
    assert count_result.scalar() == 1
