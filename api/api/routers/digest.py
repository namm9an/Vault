"""Digest router — Phase 6.

GET  /digest              → list digests (FM/ADMIN)
GET  /digest/{digest_id}  → single digest (FM/ADMIN)
POST /digest/generate     → trigger generation (ADMIN only)
"""
from uuid import UUID

from fastapi import APIRouter, Depends

from api.deps import OrgScope, get_org_scope, require_role
from api.models.user import UserRole
from api.schemas.digest import DigestGenerateRequest, DigestOut
from api.services.digest_service import (
    get_digest,
    list_digests,
    run_digest_generation,
)

router = APIRouter(prefix="/digest", tags=["digest"])


@router.get("", response_model=list[DigestOut])
async def list_digests_route(
    scope: OrgScope = Depends(get_org_scope),
    _=Depends(require_role(UserRole.FINANCE_MANAGER, UserRole.ADMIN)),
):
    return await list_digests(scope)


@router.get("/{digest_id}", response_model=DigestOut)
async def get_digest_route(
    digest_id: UUID,
    scope: OrgScope = Depends(get_org_scope),
    _=Depends(require_role(UserRole.FINANCE_MANAGER, UserRole.ADMIN)),
):
    return await get_digest(scope, digest_id)


@router.post("/generate", response_model=DigestOut)
async def generate_digest_route(
    body: DigestGenerateRequest,
    scope: OrgScope = Depends(get_org_scope),
    _=Depends(require_role(UserRole.ADMIN)),
):
    """Trigger digest generation synchronously and return the result.

    The LLM call takes ~5–10 s which is acceptable for a demo.
    Idempotent: returns existing COMPLETED digest if one already exists.
    """
    return await run_digest_generation(scope, body.period_start, body.period_end)
