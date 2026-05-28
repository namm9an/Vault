"""Notification service — write-only in Phase 4.

Read endpoints (GET /notifications, mark-read) are Phase 6.
All functions add rows to the session but do NOT commit — the caller commits.
"""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.notification import Notification, NotificationType
from api.models.user import User, UserRole


async def fire_notification(
    db: AsyncSession,
    org_id: UUID,
    user_id: UUID,
    notification_type: NotificationType,
    entity_id: UUID | None,
    body: str,
    title: str | None = None,
) -> None:
    """Add a single Notification row to the session. Caller must commit."""
    db.add(Notification(
        org_id=org_id,
        user_id=user_id,
        type=notification_type,
        title=title or notification_type.value.replace("_", " ").title(),
        body=body,
        link=None,
        payload={"entity_id": str(entity_id) if entity_id else None},
    ))


async def notify_all_fms(
    db: AsyncSession,
    org_id: UUID,
    notification_type: NotificationType,
    entity_id: UUID,
    body: str,
) -> None:
    """Fire a notification for every active FINANCE_MANAGER in the org.

    Intended for POLICY_FLAGGED / POLICY_BLOCKED events so the FM queue
    is populated as soon as the policy engine returns a non-APPROVED verdict.
    Caller must commit after this returns.
    """
    fms = (await db.execute(
        select(User).where(
            User.org_id == org_id,
            User.role == UserRole.FINANCE_MANAGER,
            User.is_active.is_(True),
        )
    )).scalars().all()
    for fm in fms:
        await fire_notification(
            db=db,
            org_id=org_id,
            user_id=fm.id,
            notification_type=notification_type,
            entity_id=entity_id,
            body=body,
        )
