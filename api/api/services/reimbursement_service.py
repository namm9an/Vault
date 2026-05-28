"""Reimbursement service — Phase 5.

Handles CRUD and state machine for employee reimbursement requests.
Enqueues run_reimbursement_policy_check for LLM-based policy evaluation.
"""
from datetime import datetime, timezone
from uuid import UUID

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import HTTPException, status
from sqlalchemy import select

from api.config import get_settings
from api.deps import OrgScope
from api.models.audit_log import AuditLog
from api.models.notification import NotificationType
from api.models.receipt import Receipt
from api.models.reimbursement import Reimbursement, ReimbursementStatus
from api.models.user import UserRole
from api.schemas.reimbursement import ReimbursementCreate, ReimbursementFilters
from api.services.notification_service import fire_notification


async def create_reimbursement(scope: OrgScope, data: ReimbursementCreate) -> Reimbursement:
    # Validate receipt_id org-scoped if provided (404 on miss)
    if data.receipt_id is not None:
        receipt = (await scope.db.execute(
            select(Receipt).where(
                Receipt.id == data.receipt_id,
                Receipt.org_id == scope.org_id,
            )
        )).scalar_one_or_none()
        if receipt is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "receipt not found in this org")

    reimb = Reimbursement(
        org_id=scope.org_id,
        user_id=scope.user_id,
        department_id=data.department_id,
        amount=data.amount,
        currency=data.currency,
        category=data.category,
        description=data.description,
        receipt_id=data.receipt_id,
        status=ReimbursementStatus.SUBMITTED,
    )
    scope.db.add(reimb)
    await scope.db.commit()
    await scope.db.refresh(reimb)

    # Enqueue policy check job — on failure, mark as REJECTED with reason
    try:
        pool = await create_pool(RedisSettings.from_dsn(get_settings().ARQ_REDIS_URL))
        await pool.enqueue_job("run_reimbursement_policy_check", reimb_id=str(reimb.id))
        await pool.aclose()
    except Exception:
        reimb.status = ReimbursementStatus.REJECTED
        reimb.decision_reason = "Failed to enqueue policy check — please retry."
        await scope.db.commit()
        await scope.db.refresh(reimb)

    return reimb


async def list_reimbursements(scope: OrgScope, filters: ReimbursementFilters) -> list[Reimbursement]:
    q = select(Reimbursement).where(Reimbursement.org_id == scope.org_id)

    # EMPLOYEE sees only their own; FM/ADMIN see org-wide
    if scope.role == UserRole.EMPLOYEE:
        q = q.where(Reimbursement.user_id == scope.user_id)

    if filters.status is not None:
        q = q.where(Reimbursement.status == filters.status)
    if filters.department_id is not None:
        q = q.where(Reimbursement.department_id == filters.department_id)
    if filters.from_date is not None:
        q = q.where(Reimbursement.created_at >= filters.from_date)
    if filters.to_date is not None:
        q = q.where(Reimbursement.created_at <= filters.to_date)

    q = q.order_by(Reimbursement.created_at.desc()).limit(filters.limit).offset(filters.offset)
    result = await scope.db.execute(q)
    return list(result.scalars().all())


async def get_reimbursement(scope: OrgScope, reimb_id: UUID) -> Reimbursement:
    q = select(Reimbursement).where(
        Reimbursement.id == reimb_id,
        Reimbursement.org_id == scope.org_id,
    )
    # EMPLOYEE can only see their own reimbursements
    if scope.role == UserRole.EMPLOYEE:
        q = q.where(Reimbursement.user_id == scope.user_id)
    reimb = (await scope.db.execute(q)).scalar_one_or_none()
    if reimb is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "reimbursement not found")
    return reimb


async def approve_reimbursement(scope: OrgScope, reimb_id: UUID, reason: str | None) -> Reimbursement:
    reimb = (await scope.db.execute(
        select(Reimbursement).where(
            Reimbursement.id == reimb_id,
            Reimbursement.org_id == scope.org_id,
        ).with_for_update()
    )).scalar_one_or_none()
    if reimb is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "reimbursement not found")

    if reimb.status != ReimbursementStatus.POLICY_CHECKED:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "reimbursement is not in POLICY_CHECKED state",
        )

    reimb.status = ReimbursementStatus.APPROVED
    reimb.decided_by = scope.user_id
    reimb.decided_at = datetime.now(timezone.utc)
    reimb.decision_reason = reason

    scope.db.add(AuditLog(
        org_id=scope.org_id,
        actor_user_id=scope.user_id,
        action="reimbursement.approved",
        entity_type="reimbursement",
        entity_id=reimb.id,
        log_metadata={"reason": reason},
    ))
    await fire_notification(
        scope.db,
        org_id=reimb.org_id,
        user_id=reimb.user_id,
        notification_type=NotificationType.APPROVAL_GRANTED,
        entity_id=reimb.id,
        body=f"Your reimbursement of {reimb.currency} {reimb.amount} has been approved.",
    )

    await scope.db.commit()
    await scope.db.refresh(reimb)
    return reimb


async def reject_reimbursement(scope: OrgScope, reimb_id: UUID, reason: str | None) -> Reimbursement:
    reimb = (await scope.db.execute(
        select(Reimbursement).where(
            Reimbursement.id == reimb_id,
            Reimbursement.org_id == scope.org_id,
        ).with_for_update()
    )).scalar_one_or_none()
    if reimb is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "reimbursement not found")

    if reimb.status not in (ReimbursementStatus.POLICY_CHECKED, ReimbursementStatus.APPROVED):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "reimbursement can only be rejected from POLICY_CHECKED or APPROVED state",
        )

    reimb.status = ReimbursementStatus.REJECTED
    reimb.decided_by = scope.user_id
    reimb.decided_at = datetime.now(timezone.utc)
    reimb.decision_reason = reason

    scope.db.add(AuditLog(
        org_id=scope.org_id,
        actor_user_id=scope.user_id,
        action="reimbursement.rejected",
        entity_type="reimbursement",
        entity_id=reimb.id,
        log_metadata={"reason": reason},
    ))
    await fire_notification(
        scope.db,
        org_id=reimb.org_id,
        user_id=reimb.user_id,
        notification_type=NotificationType.APPROVAL_REJECTED,
        entity_id=reimb.id,
        body=f"Your reimbursement of {reimb.currency} {reimb.amount} has been rejected.",
    )

    await scope.db.commit()
    await scope.db.refresh(reimb)
    return reimb


async def mark_paid(scope: OrgScope, reimb_id: UUID) -> Reimbursement:
    reimb = (await scope.db.execute(
        select(Reimbursement).where(
            Reimbursement.id == reimb_id,
            Reimbursement.org_id == scope.org_id,
        ).with_for_update()
    )).scalar_one_or_none()
    if reimb is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "reimbursement not found")

    if reimb.status != ReimbursementStatus.APPROVED:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "reimbursement can only be marked paid from APPROVED state",
        )

    reimb.status = ReimbursementStatus.PAID
    reimb.paid_at = datetime.now(timezone.utc)

    scope.db.add(AuditLog(
        org_id=scope.org_id,
        actor_user_id=scope.user_id,
        action="reimbursement.paid",
        entity_type="reimbursement",
        entity_id=reimb.id,
        log_metadata={},
    ))
    await fire_notification(
        scope.db,
        org_id=reimb.org_id,
        user_id=reimb.user_id,
        notification_type=NotificationType.APPROVAL_GRANTED,
        entity_id=reimb.id,
        body="Your reimbursement has been marked as paid.",
    )

    await scope.db.commit()
    await scope.db.refresh(reimb)
    return reimb
