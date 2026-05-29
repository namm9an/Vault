"""Demo reset endpoint — POST /api/v1/demo/reset.

Only active when DEMO_RESET_ENABLED=true in settings.
Requires ADMIN auth.

What it does:
  1. Deletes all transactional data for the org (transactions, events,
     policy results, reimbursements, receipts, digests, notifications,
     audit log).
  2. Re-seeds transactions + reimbursements + notifications from the
     standard demo seed data.
  3. Busts the Redis dashboard cache for the org.
  4. Returns {"status": "reset", "transactions": N, "reimbursements": N}.

This lets the demo presenter reset state in ~3 seconds from the UI
without SSH-ing into the VM.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete as sa_delete, select
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as aioredis

from api.config import get_settings
from api.db.base import get_db
from api.db.seeds import DEMO_ORG_SLUG, reseed_transactional
from api.deps import OrgScope, get_org_scope, require_role
from api.models.audit_log import AuditLog
from api.models.card import Card
from api.models.department import Department
from api.models.digest import Digest
from api.models.notification import Notification
from api.models.organization import Organization
from api.models.receipt import Receipt
from api.models.reimbursement import Reimbursement
from api.models.transaction import Transaction, TransactionEvent, TransactionPolicyResult
from api.models.user import User, UserRole

router = APIRouter(prefix="/demo", tags=["demo"])

settings = get_settings()

_admin_only = require_role(UserRole.ADMIN)


@router.post("/reset", dependencies=[Depends(_admin_only)])
async def reset_demo(
    scope: OrgScope = Depends(get_org_scope),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Wipe all transactional data for the org and reseed from demo fixtures.

    Guards:
    - 404 if DEMO_RESET_ENABLED is false
    - 403 if caller is not ADMIN (enforced by dependency)
    """
    if not settings.DEMO_RESET_ENABLED:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Demo reset is not enabled on this deployment.",
        )

    org_id = scope.org_id

    # ── 1. Delete transactional rows in FK-safe order ───────────────────────
    # notifications, audit_log, digests have no inbound FKs from other tables
    await db.execute(sa_delete(Notification).where(Notification.org_id == org_id))
    await db.execute(sa_delete(AuditLog).where(AuditLog.org_id == org_id))
    await db.execute(sa_delete(Digest).where(Digest.org_id == org_id))
    # Reimbursements before receipts (reimb.receipt_id → receipts ON DELETE SET NULL)
    await db.execute(sa_delete(Reimbursement).where(Reimbursement.org_id == org_id))
    # Receipts before transactions (receipt.transaction_id → transactions ON DELETE SET NULL)
    await db.execute(sa_delete(Receipt).where(Receipt.org_id == org_id))
    # Transaction child rows first (CASCADE would handle them, but be explicit)
    await db.execute(
        sa_delete(TransactionEvent).where(TransactionEvent.org_id == org_id)
    )
    await db.execute(
        sa_delete(TransactionPolicyResult).where(TransactionPolicyResult.org_id == org_id)
    )
    await db.execute(sa_delete(Transaction).where(Transaction.org_id == org_id))
    await db.flush()

    # ── 2. Reload structural data needed for re-seeding ─────────────────────
    org = (
        await db.execute(select(Organization).where(Organization.slug == DEMO_ORG_SLUG))
    ).scalar_one_or_none()
    if org is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Demo org not found")

    users = (
        await db.execute(
            select(User).where(User.org_id == org_id).order_by(User.created_at)
        )
    ).scalars().all()
    user_map = {u.email: u for u in users}

    naman = user_map["naman.moudgill@e2enetworks.com"]
    felix = user_map["fm@acme.com"]
    bob   = user_map["bob@acme.com"]
    carol = user_map["carol@acme.com"]

    depts = (
        await db.execute(
            select(Department).where(Department.org_id == org_id)
        )
    ).scalars().all()
    dept_map = {d.name: d for d in depts}
    eng_dept = dept_map["Engineering"]
    mkt_dept = dept_map["Marketing"]
    ops_dept = dept_map["Operations"]

    # Load cards in the canonical order expected by reseed_transactional
    card_nicknames = [
        "Bob — Travel",
        "Bob — SaaS",
        "Carol — Ads",
        "Carol — Events",
        "Naman — Corporate",
        "Felix — Operations",
    ]
    all_cards_map: dict[str, Card] = {
        c.nickname: c
        for c in (
            await db.execute(select(Card).where(Card.org_id == org_id))
        ).scalars().all()
    }
    cards = [all_cards_map[n] for n in card_nicknames]

    # ── 3. Re-seed transactional data ────────────────────────────────────────
    stats = await reseed_transactional(
        db, org, naman, felix, bob, carol, eng_dept, mkt_dept, ops_dept, cards,
    )

    # ── 4. Bust Redis dashboard cache for this org ───────────────────────────
    try:
        client = aioredis.from_url(settings.REDIS_URL)
        keys = await client.keys(f"dash:{org_id}:*")
        if keys:
            await client.delete(*keys)
        await client.aclose()
    except Exception:  # noqa: BLE001
        pass  # Cache bust failure is non-fatal — stale data clears in 5 min

    return {
        "status": "reset",
        "transactions": stats["transactions"],
        "reimbursements": stats["reimbursements"],
    }
