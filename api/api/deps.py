from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.base import get_db
from api.models.user import User, UserRole
from api.utils.security import decode_token

bearer = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    user_id: UUID
    org_id: UUID
    role: UserRole


@dataclass
class OrgScope:
    """Bundles db session + authenticated identity so routes need one dependency."""
    db: AsyncSession
    org_id: UUID
    user_id: UUID
    role: UserRole


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    try:
        payload = decode_token(creds.credentials)
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")
    if payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "wrong token type")

    try:
        user_id = UUID(payload["sub"])
        org_id = UUID(payload["org_id"])
        role = UserRole(payload["role"])
    except (KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "malformed token")

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None or not user.is_active or user.org_id != org_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user invalid")

    return CurrentUser(user_id=user_id, org_id=org_id, role=role)


def require_role(*allowed: UserRole):
    def _checker(cu: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if cu.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "insufficient role")
        return cu

    return _checker


async def get_org_scope(
    cu: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrgScope:
    return OrgScope(db=db, org_id=cu.org_id, user_id=cu.user_id, role=cu.role)
