"""Transaction service — state machine, CRUD, and ARQ-based policy engine.

Create flow (Phase 4):
  1. Validate card + RBAC
  2. Create Transaction row (INITIATED)
  3. Write INITIATED event
  4. Transition → POLICY_CHECKED (writes event)
  5. Write audit log
  6. Commit (2 events + audit log land atomically)
  7. Enqueue run_policy_check ARQ job
  8. Return transaction in POLICY_CHECKED state

The ARQ worker picks up run_policy_check, evaluates active policies against
the LLM, and advances the transaction to APPROVED/FLAGGED/BLOCKED.
"""
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import HTTPException, status
from sqlalchemy import select

from api.config import get_settings
from api.deps import OrgScope
from api.models.audit_log import AuditLog
from api.models.card import Card, CardStatus
from api.models.department import Department
from api.models.receipt import Receipt
from sqlalchemy import func

from api.models.transaction import (
    PolicyVerdict,
    Transaction,
    TransactionEvent,
    TransactionPolicyResult,
    TransactionState,
)
from api.schemas.transaction import TransactionCreate, TransactionFilters

# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

LEGAL_TRANSITIONS: dict[TransactionState, set[TransactionState]] = {
    TransactionState.INITIATED:       {TransactionState.POLICY_CHECKED},
    TransactionState.POLICY_CHECKED:  {
        TransactionState.APPROVED, TransactionState.FLAGGED, TransactionState.BLOCKED,
    },
    TransactionState.APPROVED:        {TransactionState.CLEARED},
    TransactionState.FLAGGED:         {TransactionState.APPROVED, TransactionState.BLOCKED},
    TransactionState.BLOCKED:         set(),   # terminal
    TransactionState.CLEARED:         {TransactionState.SETTLED},
    TransactionState.SETTLED:         set(),   # terminal
}


async def transition(
    scope: OrgScope,
    txn: Transaction,
    to_state: TransactionState,
    reason: str | None = None,
    triggered_by_system: bool = False,
) -> Transaction:
    """Validate and apply a state transition.  Writes a TransactionEvent row.
    Does NOT commit — caller is responsible for committing.
    Event row is added to the session BEFORE txn.state is mutated (H1).
    """
    from_state = txn.state
    if to_state not in LEGAL_TRANSITIONS[from_state]:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"illegal state transition: {from_state.value} → {to_state.value}",
        )
    # Add event BEFORE mutating state so both are in-session at the same time (H1)
    event = TransactionEvent(
        transaction_id=txn.id,
        org_id=scope.org_id,
        from_state=from_state,
        to_state=to_state,
        triggered_by_user=None if triggered_by_system else scope.user_id,
        triggered_by_system=triggered_by_system,
        reason=reason,
        event_metadata={
            "from": from_state.value if from_state else None,
            "to": to_state.value,
            "triggered_by": "system" if triggered_by_system else str(scope.user_id),
        },
    )
    scope.db.add(event)
    txn.state = to_state
    return txn


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _load_transaction(
    scope: OrgScope,
    txn_id: UUID,
    for_update: bool = False,
) -> Transaction:
    """Load a transaction scoped to this org.

    Set for_update=True from approve/reject paths to acquire a row-level lock
    and prevent concurrent approvals on the same FLAGGED transaction (H2).
    """
    stmt = select(Transaction).where(
        Transaction.id == txn_id,
        Transaction.org_id == scope.org_id,
    )
    if for_update:
        stmt = stmt.with_for_update()
    txn = (await scope.db.execute(stmt)).scalar_one_or_none()
    if txn is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "transaction not found")
    return txn


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------

async def create_transaction(scope: OrgScope, data: TransactionCreate) -> Transaction:
    # 1. Validate card belongs to this org
    card = (
        await scope.db.execute(
            select(Card).where(Card.id == data.card_id, Card.org_id == scope.org_id)
        )
    ).scalar_one_or_none()
    if card is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "card not found in this org")

    # 2. Validate card is ACTIVE
    if card.status != CardStatus.ACTIVE:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"card is {card.status.value.lower()} — cannot create transaction on an inactive card",
        )

    # 3. EMPLOYEE may only create transactions on their own card.
    #    Returns 404 (not 403) so the card's existence is not leaked (C1).
    if scope.role.value == "EMPLOYEE" and card.user_id != scope.user_id:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "card not found in this org",
        )

    # 4. Validate department belongs to this org if provided
    if data.department_id is not None:
        dept = (
            await scope.db.execute(
                select(Department).where(
                    Department.id == data.department_id,
                    Department.org_id == scope.org_id,
                )
            )
        ).scalar_one_or_none()
        if dept is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "department not found in this org")

    # 5. If a receipt_id is provided, verify it belongs to this org (C4 — cross-org guard).
    if data.receipt_id is not None:
        receipt_row = (
            await scope.db.execute(
                select(Receipt).where(
                    Receipt.id == data.receipt_id,
                    Receipt.org_id == scope.org_id,
                )
            )
        ).scalar_one_or_none()
        if receipt_row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "receipt not found in this org")

    # 6. Create the transaction.  Assign id explicitly so event rows can reference
    #    txn.id before the DB INSERT is flushed (required in mock-DB tests).
    txn = Transaction(
        id=uuid4(),
        org_id=scope.org_id,
        user_id=card.user_id,   # transaction belongs to the cardholder
        card_id=data.card_id,
        department_id=data.department_id,
        amount=data.amount,
        currency=data.currency,
        merchant=data.merchant,
        category=data.category,
        description=data.description,
        occurred_at=data.occurred_at or datetime.now(timezone.utc),
        receipt_id=data.receipt_id,
        state=TransactionState.INITIATED,
    )
    scope.db.add(txn)

    # 7. Flush to obtain server-generated timestamps before writing events
    await scope.db.flush()

    # 8. Write the initial INITIATED event (represents "transaction was created")
    scope.db.add(
        TransactionEvent(
            transaction_id=txn.id,
            org_id=scope.org_id,
            from_state=None,
            to_state=TransactionState.INITIATED,
            triggered_by_user=scope.user_id,
            triggered_by_system=False,
            reason="Transaction created",
            event_metadata={
                "from": None,
                "to": TransactionState.INITIATED.value,
                "triggered_by": str(scope.user_id),
                "merchant": txn.merchant,
                "amount": str(txn.amount),
                "category": txn.category.value,
            },
        )
    )

    # 9. Advance to POLICY_CHECKED — the ARQ worker will drive the next transition
    await transition(scope, txn, TransactionState.POLICY_CHECKED, triggered_by_system=True)

    # 10. Audit log (M2)
    scope.db.add(AuditLog(
        org_id=scope.org_id,
        actor_user_id=scope.user_id,
        action="transaction.create",
        entity_type="transaction",
        entity_id=txn.id,
        log_metadata={
            "amount": str(txn.amount),
            "currency": txn.currency,
            "merchant": txn.merchant,
            "category": txn.category.value,
            "initial_state": txn.state.value,
        },
    ))

    # 11. Commit — INITIATED + POLICY_CHECKED events + audit log land atomically
    await scope.db.commit()
    await scope.db.refresh(txn)

    # 12. Enqueue the LLM policy-check job asynchronously
    pool = await create_pool(RedisSettings.from_dsn(get_settings().ARQ_REDIS_URL))
    await pool.enqueue_job("run_policy_check", txn_id=str(txn.id))
    await pool.aclose()

    return txn


async def list_transactions(
    scope: OrgScope,
    filters: TransactionFilters,
) -> list[tuple[Transaction, PolicyVerdict | None]]:
    """Return transactions with the latest policy verdict per row (single batch join)."""
    q = select(Transaction).where(Transaction.org_id == scope.org_id)

    # EMPLOYEE sees only their own transactions.
    # filters.user_id is silently ignored for EMPLOYEE — only ADMIN/FM may filter
    # by arbitrary user (M6 — prevents user_id bypass via query param).
    if scope.role.value == "EMPLOYEE":
        q = q.where(Transaction.user_id == scope.user_id)

    # Optional filters
    if filters.from_date:
        q = q.where(Transaction.occurred_at >= filters.from_date)
    if filters.to_date:
        q = q.where(Transaction.occurred_at <= filters.to_date)
    if filters.category:
        q = q.where(Transaction.category == filters.category)
    if filters.department_id:
        q = q.where(Transaction.department_id == filters.department_id)
    if filters.card_id:
        q = q.where(Transaction.card_id == filters.card_id)
    if filters.user_id and scope.role.value != "EMPLOYEE":
        q = q.where(Transaction.user_id == filters.user_id)
    if filters.state:
        q = q.where(Transaction.state == filters.state)

    # H3: bounded result set — default 50, max 200
    q = q.order_by(Transaction.occurred_at.desc()).limit(filters.limit).offset(filters.offset)
    txns = list((await scope.db.execute(q)).scalars().all())

    if not txns:
        return []

    # Batch-fetch the latest policy verdict for each transaction (single query).
    txn_ids = [t.id for t in txns]
    inner = (
        select(
            TransactionPolicyResult.transaction_id,
            TransactionPolicyResult.verdict,
            func.row_number()
            .over(
                partition_by=TransactionPolicyResult.transaction_id,
                order_by=TransactionPolicyResult.created_at.desc(),
            )
            .label("rn"),
        )
        .where(TransactionPolicyResult.transaction_id.in_(txn_ids))
        .subquery()
    )
    verdict_rows = (
        await scope.db.execute(
            select(inner.c.transaction_id, inner.c.verdict).where(inner.c.rn == 1)
        )
    ).all()
    verdict_map: dict[UUID, PolicyVerdict] = {
        row.transaction_id: row.verdict for row in verdict_rows
    }

    return [(t, verdict_map.get(t.id)) for t in txns]


async def get_transaction(
    scope: OrgScope,
    txn_id: UUID,
) -> tuple[Transaction, list[TransactionEvent], TransactionPolicyResult | None]:
    # TODO (Phase 5): replace 3 round-trips with selectinload for events + policy result
    txn = await _load_transaction(scope, txn_id)

    # EMPLOYEE can only view their own transactions
    if scope.role.value == "EMPLOYEE" and txn.user_id != scope.user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "transaction not found")

    # Load events in chronological order
    events = list(
        (
            await scope.db.execute(
                select(TransactionEvent)
                .where(TransactionEvent.transaction_id == txn_id)
                .order_by(TransactionEvent.created_at.asc())
            )
        )
        .scalars()
        .all()
    )

    # Load the most recent policy result (if any)
    policy_result = (
        await scope.db.execute(
            select(TransactionPolicyResult)
            .where(TransactionPolicyResult.transaction_id == txn_id)
            .order_by(TransactionPolicyResult.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    return txn, events, policy_result


async def approve_transaction(
    scope: OrgScope,
    txn_id: UUID,
    reason: str,
) -> Transaction:
    # H2: SELECT FOR UPDATE prevents concurrent approvals on the same FLAGGED txn
    txn = await _load_transaction(scope, txn_id, for_update=True)
    if txn.state != TransactionState.FLAGGED:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"can only approve a FLAGGED transaction (current state: {txn.state.value})",
        )
    # FLAGGED → APPROVED → CLEARED
    await transition(scope, txn, TransactionState.APPROVED, reason=reason)
    await transition(scope, txn, TransactionState.CLEARED, triggered_by_system=True)

    # Audit log (M2)
    scope.db.add(AuditLog(
        org_id=scope.org_id,
        actor_user_id=scope.user_id,
        action="transaction.approve",
        entity_type="transaction",
        entity_id=txn_id,
        log_metadata={"reason": reason, "from_state": "FLAGGED", "to_state": "CLEARED"},
    ))

    await scope.db.commit()
    await scope.db.refresh(txn)
    return txn


async def reject_transaction(
    scope: OrgScope,
    txn_id: UUID,
    reason: str,
) -> Transaction:
    # H2: SELECT FOR UPDATE prevents concurrent rejects on the same FLAGGED txn
    txn = await _load_transaction(scope, txn_id, for_update=True)
    if txn.state != TransactionState.FLAGGED:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"can only reject a FLAGGED transaction (current state: {txn.state.value})",
        )
    # FLAGGED → BLOCKED (terminal)
    await transition(scope, txn, TransactionState.BLOCKED, reason=reason)

    # Audit log (M2)
    scope.db.add(AuditLog(
        org_id=scope.org_id,
        actor_user_id=scope.user_id,
        action="transaction.reject",
        entity_type="transaction",
        entity_id=txn_id,
        log_metadata={"reason": reason, "from_state": "FLAGGED", "to_state": "BLOCKED"},
    ))

    await scope.db.commit()
    await scope.db.refresh(txn)
    return txn


async def list_events(
    scope: OrgScope,
    txn_id: UUID,
) -> list[TransactionEvent]:
    txn = await _load_transaction(scope, txn_id)

    # EMPLOYEE can only see events for their own transactions
    if scope.role.value == "EMPLOYEE" and txn.user_id != scope.user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "transaction not found")

    events = list(
        (
            await scope.db.execute(
                select(TransactionEvent)
                .where(TransactionEvent.transaction_id == txn_id)
                .order_by(TransactionEvent.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    return events
