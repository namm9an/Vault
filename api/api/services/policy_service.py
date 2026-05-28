"""Policy service — CRUD for plain-English spend policies.

All functions are scoped by scope.org_id.
AuditLog is written on every create/update/delete, inside the same commit.
"""
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select

from api.deps import OrgScope
from api.models.audit_log import AuditLog
from api.models.policy import Policy
from api.schemas.policy import PolicyCreate, PolicyUpdate


async def list_policies(scope: OrgScope) -> list[Policy]:
    result = await scope.db.execute(
        select(Policy)
        .where(Policy.org_id == scope.org_id)
        .order_by(Policy.created_at.desc())
    )
    return list(result.scalars().all())


async def get_policy(scope: OrgScope, policy_id: UUID) -> Policy:
    policy = (await scope.db.execute(
        select(Policy).where(Policy.id == policy_id, Policy.org_id == scope.org_id)
    )).scalar_one_or_none()
    if policy is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "policy not found")
    return policy


async def create_policy(scope: OrgScope, data: PolicyCreate) -> Policy:
    policy = Policy(
        org_id=scope.org_id,
        policy_text=data.policy_text,
        is_active=data.is_active,
        created_by=scope.user_id,
    )
    scope.db.add(policy)
    await scope.db.flush()

    scope.db.add(AuditLog(
        org_id=scope.org_id,
        actor_user_id=scope.user_id,
        action="policy.create",
        entity_type="policy",
        entity_id=policy.id,
        log_metadata={
            "text_preview": policy.policy_text[:100],
            "is_active": policy.is_active,
        },
    ))
    await scope.db.commit()
    await scope.db.refresh(policy)
    return policy


async def update_policy(scope: OrgScope, policy_id: UUID, data: PolicyUpdate) -> Policy:
    policy = await get_policy(scope, policy_id)

    if data.policy_text is not None:
        policy.policy_text = data.policy_text
    if data.is_active is not None:
        policy.is_active = data.is_active

    scope.db.add(AuditLog(
        org_id=scope.org_id,
        actor_user_id=scope.user_id,
        action="policy.update",
        entity_type="policy",
        entity_id=policy.id,
        log_metadata={
            "is_active": policy.is_active,
            "text_preview": policy.policy_text[:100],
        },
    ))
    await scope.db.commit()
    await scope.db.refresh(policy)
    return policy


async def delete_policy(scope: OrgScope, policy_id: UUID) -> None:
    policy = await get_policy(scope, policy_id)

    scope.db.add(AuditLog(
        org_id=scope.org_id,
        actor_user_id=scope.user_id,
        action="policy.delete",
        entity_type="policy",
        entity_id=policy.id,
        log_metadata={"text_preview": policy.policy_text[:100]},
    ))
    await scope.db.delete(policy)
    await scope.db.commit()
