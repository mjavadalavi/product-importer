"""CLI script to approve a pending topup transaction.

Usage:
    # Approve a specific transaction:
    python -m scripts.approve_topup <user_id> <tx_id>

    # List all pending topups for a user:
    python -m scripts.approve_topup <user_id>
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import uuid

from sqlalchemy import select

from app.db.models.transaction import GeneralType, ReferenceType, Transaction, TransactionStatus
from app.db.session import AsyncSessionLocal
from app.services import ledger


def _parse_uuid(value: str, label: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        print(f"ERROR: {label} '{value}' is not a valid UUID.", file=sys.stderr)
        sys.exit(1)


async def _list_pending_topups(user_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Transaction)
            .where(
                Transaction.user_id == user_id,
                Transaction.general_type == GeneralType.DEPOSIT,
                Transaction.reference_type == ReferenceType.REQUEST_AMOUNT,
                Transaction.status == TransactionStatus.PENDING,
            )
            .order_by(Transaction.created_at.asc())
        )
        rows = result.scalars().all()

    if not rows:
        print(f"No PENDING topups found for user {user_id}.")
        return

    print(f"PENDING topups for user {user_id}:")
    for tx in rows:
        print(f"  {tx.id}  amount={int(tx.amount)}  created_at={tx.created_at.isoformat()}")


async def _approve_topup(user_id: uuid.UUID, tx_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as db:
        tx = await db.get(Transaction, tx_id)

        if tx is None:
            print(f"ERROR: transaction {tx_id} not found.", file=sys.stderr)
            sys.exit(1)

        if tx.user_id != user_id:
            print(
                f"ERROR: transaction {tx_id} does not belong to user {user_id}.",
                file=sys.stderr,
            )
            sys.exit(1)

        if tx.general_type != GeneralType.DEPOSIT:
            print(
                f"ERROR: transaction {tx_id} general_type is {tx.general_type.value}, expected DEPOSIT.",
                file=sys.stderr,
            )
            sys.exit(1)

        if tx.reference_type != ReferenceType.REQUEST_AMOUNT:
            print(
                f"ERROR: transaction {tx_id} reference_type is {tx.reference_type.value}, expected REQUEST_AMOUNT.",
                file=sys.stderr,
            )
            sys.exit(1)

        if tx.status != TransactionStatus.PENDING:
            print(
                f"ERROR: transaction {tx_id} status is {tx.status.value}, expected PENDING.",
                file=sys.stderr,
            )
            sys.exit(1)

        await ledger.complete_transaction(db, tx_id)
        await db.commit()

        new_balance = await ledger.get_balance(db, user_id)

    print(f"OK: tx {tx_id} marked COMPLETED. New balance: {new_balance}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Approve a pending topup transaction or list pending topups for a user."
    )
    parser.add_argument("user_id", help="UUID of the user")
    parser.add_argument(
        "tx_id",
        nargs="?",
        default=None,
        help="UUID of the transaction to approve. Omit to list pending topups.",
    )
    args = parser.parse_args()

    user_id = _parse_uuid(args.user_id, "user_id")

    if args.tx_id is None:
        asyncio.run(_list_pending_topups(user_id))
    else:
        tx_id = _parse_uuid(args.tx_id, "tx_id")
        asyncio.run(_approve_topup(user_id, tx_id))


if __name__ == "__main__":
    main()
