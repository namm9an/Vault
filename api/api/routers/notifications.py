"""Notifications router — Phase 6 read layer.

GET  /notifications              → list for current user (last 50, newest first)
GET  /notifications/unread-count → {"count": int}
POST /notifications/{id}/read    → mark single read
POST /notifications/read-all     → mark all unread read
"""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import CurrentUser, OrgScope, get_current_user, get_db, get_org_scope
from api.models.notification import Notification

router = APIRouter(prefix="/notifications", tags=["notifications"])


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

class NotificationOut(BaseModel):
    id: UUID
    type: str
    title: str
    body: str
    link: str | None = None
    payload: dict
    read_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("", response_model=list[NotificationOut])
async def list_notifications_route(
    cu: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(Notification)
        .where(
            Notification.user_id == cu.user_id,
            Notification.org_id == cu.org_id,
        )
        .order_by(Notification.created_at.desc())
        .limit(50)
    )).scalars().all()
    return list(rows)


@router.get("/unread-count")
async def unread_count_route(
    cu: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    count = (await db.execute(
        select(func.count(Notification.id)).where(
            Notification.user_id == cu.user_id,
            Notification.org_id == cu.org_id,
            Notification.read_at.is_(None),
        )
    )).scalar_one()
    return {"count": int(count)}


@router.post("/{notification_id}/read", status_code=204)
async def mark_read_route(
    notification_id: UUID,
    cu: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    notif = (await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == cu.user_id,
            Notification.org_id == cu.org_id,
        )
    )).scalar_one_or_none()
    if notif is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="notification not found")
    if notif.read_at is None:
        notif.read_at = datetime.now(timezone.utc)
        await db.commit()


@router.post("/read-all", status_code=204)
async def mark_all_read_route(
    cu: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    unread = (await db.execute(
        select(Notification).where(
            Notification.user_id == cu.user_id,
            Notification.org_id == cu.org_id,
            Notification.read_at.is_(None),
        )
    )).scalars().all()
    now = datetime.now(timezone.utc)
    for notif in unread:
        notif.read_at = now
    if unread:
        await db.commit()
