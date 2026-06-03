"""Digest router — Phase 6.

GET  /digest              → list digests (FM/ADMIN)
GET  /digest/{digest_id}  → single digest (FM/ADMIN)
POST /digest/generate     → trigger generation (ADMIN only)

POST /digest/generate returns immediately after committing the PENDING row.
The LLM call runs in a BackgroundTask with its own DB session so the HTTP
response is never blocked by a 60-second inference call.
"""
import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends

from api.db.base import get_session_factory
from api.deps import OrgScope, get_org_scope, require_role
from api.models.digest import DigestStatus
from api.models.user import UserRole
from api.schemas.digest import DigestGenerateRequest, DigestOut
from api.services.digest_service import (
    delete_digest,
    get_digest,
    get_or_create_pending_digest,
    list_digests,
    run_digest_generation,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/digest", tags=["digest"])


# ---------------------------------------------------------------------------
# Background task helper — opens own session, independent of request scope
# ---------------------------------------------------------------------------

async def _bg_generate(org_id, user_id, digest_id, period_start, period_end) -> None:
    async with get_session_factory()() as db:
        from api.deps import OrgScope as _OrgScope
        bg_scope = _OrgScope(db=db, org_id=org_id, user_id=user_id, role=UserRole.ADMIN)
        try:
            await run_digest_generation(bg_scope, period_start, period_end, digest_id=digest_id)
        except Exception as exc:  # noqa: BLE001
            logger.error("background digest generation failed for org %s: %s", org_id, exc)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

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


@router.delete("/{digest_id}", status_code=204)
async def delete_digest_route(
    digest_id: UUID,
    scope: OrgScope = Depends(get_org_scope),
    _=Depends(require_role(UserRole.ADMIN)),
):
    await delete_digest(scope, digest_id)


@router.post("/generate", response_model=DigestOut, status_code=202)
async def generate_digest_route(
    body: DigestGenerateRequest,
    background_tasks: BackgroundTasks,
    scope: OrgScope = Depends(get_org_scope),
    _=Depends(require_role(UserRole.ADMIN)),
):
    """Commit the PENDING row and return immediately (HTTP 202 Accepted).

    The LLM call + notifications + email run in a background task.
    The caller can poll GET /digest/{id} to watch status change from
    PENDING → COMPLETED (or FAILED).

    Idempotent: returns the existing COMPLETED digest if one already exists.
    """
    digest = await get_or_create_pending_digest(scope, body.period_start, body.period_end)

    if digest.status == DigestStatus.COMPLETED:
        # Already done — return immediately without scheduling another background task
        return digest

    # PENDING row committed; schedule LLM work in the background
    background_tasks.add_task(
        _bg_generate,
        scope.org_id,
        scope.user_id,
        digest.id,
        body.period_start,
        body.period_end,
    )
    return digest
