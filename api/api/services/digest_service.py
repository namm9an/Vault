"""Digest service — Phase 6.

Handles weekly spend digest generation:
- aggregate_spend_data: collect DB stats for the period
- call_llm_for_digest: call TIR LLM to produce narrative
- send_digest_email: SMTP email delivery (best-effort; never raises)
- run_digest_generation: full orchestration with idempotency guards
- list_digests / get_digest: read layer
"""
import asyncio
import logging
import smtplib
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select

from api.config import get_settings
from api.deps import OrgScope
from api.llm.llm_client import LLMUnavailableError, LLMValidationError, complete_json
from api.models.audit_log import AuditLog
from api.models.department import Department
from api.models.digest import Digest, DigestStatus
from api.models.notification import NotificationType
from api.models.reimbursement import Reimbursement, ReimbursementStatus
from api.models.transaction import Transaction, TransactionState
from api.models.user import User, UserRole
from api.services.notification_service import notify_all_fms

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LLM response schema (internal validation)
# ---------------------------------------------------------------------------

_DIGEST_SYSTEM_PROMPT = """\
You are a corporate spend analyst. Given aggregated expense data, produce a concise weekly digest in JSON with exactly these keys:
- "headline": one sentence summary (max 15 words)
- "body": 2-3 paragraph narrative covering spend trends, anomalies, and highlights
- "top_recommendations": array of 3 actionable strings for the finance team
- "flagged_items": array of objects with {"description": str, "amount": number, "reason": str} for any anomalies
Respond with ONLY valid JSON, no markdown fences, no extra text."""


class SpendDigest(BaseModel):
    headline: str
    body: str
    top_recommendations: list[str]
    flagged_items: list[dict]


# ---------------------------------------------------------------------------
# aggregate_spend_data
# ---------------------------------------------------------------------------

async def aggregate_spend_data(
    scope: OrgScope,
    period_start: Any,
    period_end: Any,
) -> dict:
    """Collect spend statistics for the given date range.

    Returns a plain dict suitable for JSON serialisation and LLM prompting.
    """
    from datetime import date as date_type
    import datetime as _dt

    # Convert dates to aware datetimes at UTC midnight
    if isinstance(period_start, date_type) and not isinstance(period_start, _dt.datetime):
        ps = _dt.datetime(period_start.year, period_start.month, period_start.day, tzinfo=timezone.utc)
    else:
        ps = period_start

    if isinstance(period_end, date_type) and not isinstance(period_end, _dt.datetime):
        # end of day
        pe = _dt.datetime(period_end.year, period_end.month, period_end.day, 23, 59, 59, tzinfo=timezone.utc)
    else:
        pe = period_end

    cleared_states = [TransactionState.CLEARED, TransactionState.SETTLED]
    db = scope.db
    org_id = scope.org_id

    # Total spend + count
    total_result = (await db.execute(
        select(
            func.coalesce(func.sum(Transaction.amount), Decimal("0")).label("total"),
            func.count(Transaction.id).label("cnt"),
        ).where(
            Transaction.org_id == org_id,
            Transaction.state.in_(cleared_states),
            Transaction.occurred_at >= ps,
            Transaction.occurred_at <= pe,
        )
    )).one()
    total_spend = Decimal(str(total_result.total))
    transaction_count = int(total_result.cnt)

    # Top 5 categories
    cat_rows = (await db.execute(
        select(
            Transaction.category.label("category"),
            func.sum(Transaction.amount).label("total"),
        ).where(
            Transaction.org_id == org_id,
            Transaction.state.in_(cleared_states),
            Transaction.occurred_at >= ps,
            Transaction.occurred_at <= pe,
        ).group_by(Transaction.category)
        .order_by(func.sum(Transaction.amount).desc())
        .limit(5)
    )).all()
    top_categories = [
        {"category": r.category.value if hasattr(r.category, "value") else str(r.category), "amount": float(r.total)}
        for r in cat_rows
    ]

    # Top 5 departments by spend
    dept_rows = (await db.execute(
        select(
            Transaction.department_id.label("dept_id"),
            func.sum(Transaction.amount).label("total"),
        ).where(
            Transaction.org_id == org_id,
            Transaction.state.in_(cleared_states),
            Transaction.occurred_at >= ps,
            Transaction.occurred_at <= pe,
            Transaction.department_id.isnot(None),
        ).group_by(Transaction.department_id)
        .order_by(func.sum(Transaction.amount).desc())
        .limit(5)
    )).all()

    dept_ids = [r.dept_id for r in dept_rows]
    dept_names: dict[str, str] = {}
    if dept_ids:
        name_rows = (await db.execute(
            select(Department.id, Department.name).where(
                Department.id.in_(dept_ids),
                Department.org_id == org_id,
            )
        )).all()
        dept_names = {str(r.id): r.name for r in name_rows}
    top_departments = [
        {
            "department_id": str(r.dept_id),
            "department_name": dept_names.get(str(r.dept_id), "Unknown"),
            "amount": float(r.total),
        }
        for r in dept_rows
    ]

    # Top 5 merchants
    merch_rows = (await db.execute(
        select(
            Transaction.merchant.label("merchant"),
            func.count(Transaction.id).label("cnt"),
            func.sum(Transaction.amount).label("total"),
        ).where(
            Transaction.org_id == org_id,
            Transaction.state.in_(cleared_states),
            Transaction.occurred_at >= ps,
            Transaction.occurred_at <= pe,
        ).group_by(Transaction.merchant)
        .order_by(func.sum(Transaction.amount).desc())
        .limit(5)
    )).all()
    top_merchants = [
        {"merchant": r.merchant, "count": int(r.cnt), "amount": float(r.total)}
        for r in merch_rows
    ]

    # Pending approvals (reimbursements with POLICY_CHECKED status)
    pending_approvals = (await db.execute(
        select(func.count(Reimbursement.id)).where(
            Reimbursement.org_id == org_id,
            Reimbursement.status == ReimbursementStatus.POLICY_CHECKED,
        )
    )).scalar_one()

    # Policy-blocked reimbursements in period
    blocked_count = (await db.execute(
        select(func.count(Reimbursement.id)).where(
            Reimbursement.org_id == org_id,
            Reimbursement.status == ReimbursementStatus.REJECTED,
            Reimbursement.created_at >= ps,
            Reimbursement.created_at <= pe,
        )
    )).scalar_one()

    return {
        "period_start": str(period_start),
        "period_end": str(period_end),
        "total_spend": float(total_spend),
        "transaction_count": transaction_count,
        "top_categories": top_categories,
        "top_departments": top_departments,
        "top_merchants": top_merchants,
        "pending_approvals": int(pending_approvals),
        "policy_blocked_count": int(blocked_count),
    }


# ---------------------------------------------------------------------------
# call_llm_for_digest
# ---------------------------------------------------------------------------

async def call_llm_for_digest(aggregated: dict, settings) -> dict:
    """Call the TIR LLM and return a validated digest dict."""
    import json

    user_prompt = (
        "Here is the aggregated spend data for the period "
        f"{aggregated.get('period_start')} to {aggregated.get('period_end')}:\n\n"
        f"{json.dumps(aggregated, indent=2)}\n\n"
        "Produce the weekly digest JSON now."
    )

    result, _ = await complete_json(
        system=_DIGEST_SYSTEM_PROMPT,
        user=user_prompt,
        schema=SpendDigest,
        temperature=0.3,
        max_tokens=900,
    )
    return result.model_dump()


# ---------------------------------------------------------------------------
# send_digest_email
# ---------------------------------------------------------------------------

def send_digest_email(digest: Digest, recipients: list[str]) -> None:
    """Send digest email via SMTP. Never raises — errors are logged only."""
    if not recipients:
        return

    try:
        settings = get_settings()
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[Vault] Weekly Spend Digest: {digest.period_start} – {digest.period_end}"
        msg["From"] = settings.SMTP_FROM
        msg["To"] = ", ".join(recipients)

        headline = digest.headline or "Weekly spend digest ready"
        body_text = digest.body or "See your Vault dashboard for details."
        recs = "\n".join(
            f"• {r}" for r in (digest.top_recommendations or [])
        )
        flagged = "\n".join(
            f"• {f.get('description', '')} — ₹{f.get('amount', 0)}: {f.get('reason', '')}"
            for f in (digest.flagged_items or [])
        )

        plain = (
            f"{headline}\n\n"
            f"{body_text}\n\n"
            + (f"Recommendations:\n{recs}\n\n" if recs else "")
            + (f"Flagged items:\n{flagged}\n\n" if flagged else "")
            + "Visit your Vault dashboard to view the full digest."
        )
        msg.attach(MIMEText(plain, "plain"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as smtp:
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            smtp.sendmail(settings.SMTP_FROM, recipients, msg.as_string())

        logger.info("digest email sent to %d recipient(s)", len(recipients))
    except Exception as exc:  # noqa: BLE001
        logger.warning("digest email failed (non-fatal): %s", exc)


# ---------------------------------------------------------------------------
# get_or_create_pending_digest — used by router to respond fast, schedule LLM in bg
# ---------------------------------------------------------------------------

async def get_or_create_pending_digest(
    scope: OrgScope,
    period_start: Any,
    period_end: Any,
) -> Digest:
    """Idempotency check + create/reset the PENDING digest row in one commit.

    Returns an existing COMPLETED digest immediately (caller should short-circuit).
    Raises HTTP 409 if a PENDING digest was created within the last 10 minutes.
    Otherwise creates/resets a PENDING row, writes AuditLog, commits, and returns it.
    """
    db = scope.db
    org_id = scope.org_id

    existing_completed = (await db.execute(
        select(Digest).where(
            Digest.org_id == org_id,
            Digest.period_start == period_start,
            Digest.period_end == period_end,
            Digest.status == DigestStatus.COMPLETED,
        )
    )).scalar_one_or_none()
    if existing_completed is not None:
        return existing_completed

    ten_min_ago = datetime.now(timezone.utc) - timedelta(minutes=10)
    existing_pending = (await db.execute(
        select(Digest).where(
            Digest.org_id == org_id,
            Digest.period_start == period_start,
            Digest.period_end == period_end,
            Digest.status == DigestStatus.PENDING,
            Digest.created_at >= ten_min_ago,
        )
    )).scalar_one_or_none()
    if existing_pending is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="digest generation already in progress",
        )

    existing_any = (await db.execute(
        select(Digest).where(
            Digest.org_id == org_id,
            Digest.period_start == period_start,
            Digest.period_end == period_end,
        )
    )).scalar_one_or_none()

    if existing_any is not None:
        digest = existing_any
        digest.status = DigestStatus.PENDING
        digest.headline = None
        digest.body = None
        digest.top_recommendations = None
        digest.flagged_items = None
        digest.llm_error = None
    else:
        digest = Digest(
            org_id=org_id,
            period_start=period_start,
            period_end=period_end,
            status=DigestStatus.PENDING,
        )
        db.add(digest)

    db.add(AuditLog(
        org_id=org_id,
        actor_user_id=scope.user_id,
        action="digest.started",
        entity_type="digest",
        entity_id=None,
        log_metadata={
            "period_start": str(period_start),
            "period_end": str(period_end),
        },
    ))
    await db.commit()
    await db.refresh(digest)
    return digest


# ---------------------------------------------------------------------------
# run_digest_generation (full orchestration)
# ---------------------------------------------------------------------------

async def run_digest_generation(
    scope: OrgScope,
    period_start: Any,
    period_end: Any,
) -> Digest:
    """Generate a weekly digest for the org.

    Idempotency:
    - COMPLETED digest for same (org_id, period_start, period_end) → return immediately
    - PENDING digest created within last 10 min → raise HTTP 409
    """
    db = scope.db
    org_id = scope.org_id

    # Idempotency check + PENDING row creation (shared with router fast-path)
    digest = await get_or_create_pending_digest(scope, period_start, period_end)
    if digest.status == DigestStatus.COMPLETED:
        logger.info("digest already completed for org %s, period %s–%s", org_id, period_start, period_end)
        return digest

    # Aggregate spend data
    aggregated = await aggregate_spend_data(scope, period_start, period_end)
    digest.aggregated_input = aggregated

    # Call LLM
    settings = get_settings()
    try:
        llm_result = await call_llm_for_digest(aggregated, settings)
        digest.headline = llm_result["headline"]
        digest.body = llm_result["body"]
        digest.top_recommendations = llm_result["top_recommendations"]
        digest.flagged_items = llm_result["flagged_items"]
        digest.raw_llm_response = llm_result
        digest.status = DigestStatus.COMPLETED
        final_action = "digest.completed"
    except (LLMValidationError, LLMUnavailableError, Exception) as exc:
        digest.status = DigestStatus.FAILED
        digest.llm_error = str(exc)
        final_action = "digest.failed"
        logger.error("digest LLM failed for org %s: %s", org_id, exc)

    db.add(AuditLog(
        org_id=org_id,
        actor_user_id=scope.user_id,
        action=final_action,
        entity_type="digest",
        entity_id=digest.id,
        log_metadata={
            "status": digest.status.value,
            "period_start": str(period_start),
            "period_end": str(period_end),
        },
    ))

    # Notifications for FM/ADMIN if completed
    if digest.status == DigestStatus.COMPLETED:
        await notify_all_fms(
            db=db,
            org_id=org_id,
            notification_type=NotificationType.DIGEST_READY,
            entity_id=digest.id,
            body=(
                f"Weekly spend digest is ready: {digest.headline or 'View your digest in the Vault dashboard.'}"
            ),
        )

    await db.commit()
    await db.refresh(digest)

    # Send email (best-effort, after commit)
    if digest.status == DigestStatus.COMPLETED:
        try:
            fm_users = (await db.execute(
                select(User).where(
                    User.org_id == org_id,
                    User.role.in_([UserRole.FINANCE_MANAGER, UserRole.ADMIN]),
                    User.is_active.is_(True),
                )
            )).scalars().all()
            recipients = [u.email for u in fm_users if u.email]
            # run_in_executor so smtplib.SMTP (blocking IO) doesn't stall the event loop
            await asyncio.to_thread(send_digest_email, digest, recipients)
        except Exception as exc:  # noqa: BLE001
            logger.warning("failed to fetch recipients for digest email: %s", exc)

    return digest


# ---------------------------------------------------------------------------
# Read layer
# ---------------------------------------------------------------------------

async def list_digests(scope: OrgScope) -> list[Digest]:
    """Return the most recent 20 digests for the org, newest first."""
    result = await scope.db.execute(
        select(Digest)
        .where(Digest.org_id == scope.org_id)
        .order_by(Digest.period_end.desc())
        .limit(20)
    )
    return list(result.scalars().all())


async def get_digest(scope: OrgScope, digest_id: UUID) -> Digest:
    """Return a single digest by ID. 404 if not found or belongs to another org."""
    digest = (await scope.db.execute(
        select(Digest).where(
            Digest.id == digest_id,
            Digest.org_id == scope.org_id,
        )
    )).scalar_one_or_none()
    if digest is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="digest not found")
    return digest


async def delete_digest(scope: OrgScope, digest_id: UUID) -> None:
    """Delete a digest by ID. 404 if not found or belongs to another org."""
    digest = await get_digest(scope, digest_id)
    await scope.db.delete(digest)
    await scope.db.commit()
