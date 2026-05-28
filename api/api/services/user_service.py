from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from api.deps import OrgScope
from api.models.audit_log import AuditLog
from api.models.department import Department
from api.models.user import User, UserRole
from api.schemas.user import UserInvite, UserUpdate
from api.utils.security import hash_password


async def _write_audit(scope: OrgScope, action: str, entity_id: UUID, meta: dict) -> None:
    scope.db.add(
        AuditLog(
            org_id=scope.org_id,
            actor_user_id=scope.user_id,
            action=action,
            entity_type="user",
            entity_id=entity_id,
            log_metadata=meta,
        )
    )


async def list_users(scope: OrgScope) -> list[User]:
    result = await scope.db.execute(
        select(User).where(User.org_id == scope.org_id).order_by(User.created_at)
    )
    return list(result.scalars().all())


async def get_user(scope: OrgScope, user_id: UUID) -> User:
    user = (
        await scope.db.execute(
            select(User).where(User.id == user_id, User.org_id == scope.org_id)
        )
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    return user


async def _assert_department_in_org(scope: OrgScope, department_id: UUID) -> None:
    """Raise 404 if department_id does not exist in scope.org_id."""
    dept = (
        await scope.db.execute(
            select(Department).where(
                Department.id == department_id,
                Department.org_id == scope.org_id,
            )
        )
    ).scalar_one_or_none()
    if dept is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "department not found in this org")


async def invite_user(scope: OrgScope, data: UserInvite) -> tuple[User, str]:
    if data.department_id is not None:
        await _assert_department_in_org(scope, data.department_id)

    user = User(
        org_id=scope.org_id,
        email=data.email,
        password_hash=hash_password(data.password),
        full_name=data.full_name,
        role=data.role,
        department_id=data.department_id,
        is_active=True,
    )
    scope.db.add(user)
    try:
        # Flush to trigger the unique-email constraint and get user.id
        # before writing the audit row — both land in one commit
        await scope.db.flush()
    except IntegrityError:
        await scope.db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "email already registered")
    await _write_audit(scope, "user.invite", user.id, {
        "email": data.email,
        "role": data.role.value,
    })
    await scope.db.commit()
    await scope.db.refresh(user)
    invite_token = str(uuid4())
    return user, invite_token


async def update_user(scope: OrgScope, user_id: UUID, data: UserUpdate) -> User:
    user = await get_user(scope, user_id)
    update_data = data.model_dump(exclude_unset=True)

    # Guard: prevent removing the last active admin from the org.
    # Applies regardless of whether the caller is the target user or another admin —
    # either a role demotion OR a deactivation of an active admin triggers this check.
    user_is_active_admin = user.role == UserRole.ADMIN and user.is_active
    will_lose_admin = (
        ("role" in update_data and update_data["role"] != UserRole.ADMIN)
        or ("is_active" in update_data and not update_data["is_active"])
    )
    if user_is_active_admin and will_lose_admin:
        admin_count = (
            await scope.db.execute(
                select(func.count()).select_from(User).where(
                    User.org_id == scope.org_id,
                    User.role == UserRole.ADMIN,
                    User.is_active.is_(True),
                )
            )
        ).scalar_one()
        if admin_count <= 1:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "cannot remove the last admin",
            )

    # Validate cross-org department if being reassigned (null = remove dept, always ok)
    if "department_id" in update_data and update_data["department_id"] is not None:
        await _assert_department_in_org(scope, update_data["department_id"])

    for field, value in update_data.items():
        setattr(user, field, value)
    await _write_audit(scope, "user.update", user_id, {k: str(v) for k, v in update_data.items()})
    await scope.db.commit()
    await scope.db.refresh(user)
    return user
