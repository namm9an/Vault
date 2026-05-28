import re
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, MultipleResultsFound
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.organization import Organization
from api.models.refresh_token import RefreshToken
from api.models.user import User, UserRole
from api.utils.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)

# Pre-computed at import time so every missing-user login path pays the same bcrypt cost.
_DUMMY_HASH: str = hash_password("__vault_timing_guard_do_not_use__")


_slug_re = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    base = _slug_re.sub("-", name.lower()).strip("-")
    return base or "org"


async def _unique_slug(db: AsyncSession, base: str) -> str:
    slug = base
    counter = 1
    while True:
        existing = await db.execute(select(Organization).where(Organization.slug == slug))
        if existing.scalar_one_or_none() is None:
            return slug
        counter += 1
        slug = f"{base}-{counter}"


async def signup(
    db: AsyncSession,
    *,
    org_name: str,
    email: str,
    password: str,
    full_name: str,
) -> tuple[User, Organization, str, str]:
    # Enforce global email uniqueness at the app layer so login-by-email is unambiguous.
    existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "email already registered")

    slug = await _unique_slug(db, slugify(org_name))
    org = Organization(name=org_name, slug=slug)
    db.add(org)
    await db.flush()

    user = User(
        org_id=org.id,
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "email already in use")

    access = create_access_token(user.id, org.id, user.role.value)
    refresh, expires_at = create_refresh_token(user.id)
    db.add(RefreshToken(user_id=user.id, token_hash=hash_token(refresh), expires_at=expires_at))

    await db.commit()
    await db.refresh(user)
    await db.refresh(org)
    return user, org, access, refresh


async def login(db: AsyncSession, *, email: str, password: str) -> tuple[User, Organization, str, str]:
    try:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
    except MultipleResultsFound:
        user = None

    # Always pay bcrypt cost regardless of whether user exists (timing oracle prevention).
    if user is None:
        verify_password(password, _DUMMY_HASH)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")

    if not verify_password(password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")

    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "user disabled")

    org = (await db.execute(select(Organization).where(Organization.id == user.org_id))).scalar_one()
    user.last_login_at = datetime.now(timezone.utc)

    access = create_access_token(user.id, user.org_id, user.role.value)
    refresh, expires_at = create_refresh_token(user.id)
    db.add(RefreshToken(user_id=user.id, token_hash=hash_token(refresh), expires_at=expires_at))

    await db.commit()
    return user, org, access, refresh


async def refresh_tokens(db: AsyncSession, *, refresh_token: str) -> tuple[str, str]:
    try:
        payload = decode_token(refresh_token)
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid refresh token")
    if payload.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "wrong token type")

    th = hash_token(refresh_token)
    row = (
        await db.execute(
            select(RefreshToken)
            .where(RefreshToken.token_hash == th)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if row is None or row.revoked_at is not None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "refresh token revoked or unknown")

    if row.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "refresh token expired")

    user = (await db.execute(select(User).where(User.id == row.user_id))).scalar_one()

    row.revoked_at = datetime.now(timezone.utc)

    access = create_access_token(user.id, user.org_id, user.role.value)
    new_refresh, expires_at = create_refresh_token(user.id)
    db.add(RefreshToken(user_id=user.id, token_hash=hash_token(new_refresh), expires_at=expires_at))

    await db.commit()
    return access, new_refresh


async def logout(db: AsyncSession, *, refresh_token: str) -> None:
    th = hash_token(refresh_token)
    row = (
        await db.execute(select(RefreshToken).where(RefreshToken.token_hash == th))
    ).scalar_one_or_none()
    if row is not None and row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc)
        await db.commit()


async def get_user_and_org(db: AsyncSession, user_id: UUID) -> tuple[User, Organization]:
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found")
    org = (await db.execute(select(Organization).where(Organization.id == user.org_id))).scalar_one()
    return user, org
