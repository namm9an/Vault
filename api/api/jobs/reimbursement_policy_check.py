"""ARQ job: run_reimbursement_policy_check

Loads all active (non-deleted) policies for the reimbursement's org, formats
a sanitized plain-text prompt, and calls the LLM for a verdict:
APPROVED | FLAGGED | BLOCKED.

Idempotent: guards on reimb.status == SUBMITTED (with FOR UPDATE).
Single-commit rule: state transition + notifications land in one db.commit().

Verdict mapping (no FLAGGED/BLOCKED in reimbursement_status):
  APPROVED → status=APPROVED, notify FMs (APPROVAL_REQUESTED)
  FLAGGED  → status=APPROVED (FM reviews), notify FMs with "(flagged by policy)"
  BLOCKED  → status=REJECTED, notify employee (APPROVAL_REJECTED)
"""
import logging
import re

from sqlalchemy import select

from api.db.base import get_session_factory
from api.llm.llm_client import LLMUnavailableError, LLMValidationError, complete_json
from api.llm.schemas import PolicyCheckResult
from api.models.notification import NotificationType
from api.models.policy import Policy
from api.models.reimbursement import Reimbursement, ReimbursementStatus
from api.models.transaction import PolicyVerdict
from api.services.notification_service import fire_notification, notify_all_fms

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a corporate expense compliance engine for a spend management platform.
You are given a list of plain-English expense policies and a reimbursement request to evaluate.
Respond with JSON only — no explanation, no markdown.

Verdict rules (use the most restrictive that applies):
  BLOCKED  — the request clearly and unambiguously violates a hard policy
             (e.g. personal purchases, gambling, non-business vendors, hard INR caps).
  FLAGGED  — the request is borderline, unusual, or exceeds a soft threshold
             that requires human sign-off from a Finance Manager or Admin.
  APPROVED — the request is clearly compliant with all active policies.

Output fields:
  verdict                  : "APPROVED" | "FLAGGED" | "BLOCKED"
  reason                   : concise explanation (max 1000 chars)
  policy_matched           : verbatim text of the triggered policy, or null
  requires_approval_from   : "FINANCE_MANAGER" | "ADMIN" | null  (only when FLAGGED)"""


def _sanitize(value: str, max_len: int = 500) -> str:
    """Strip control characters and cap length on user-supplied strings."""
    sanitized = re.sub(r"[\x00-\x1f\x7f]", " ", str(value))
    return sanitized[:max_len].strip()


def _build_reimbursement_prompt(reimb: Reimbursement, policies: list[Policy]) -> str:
    policy_lines = "\n".join(
        f"  {i+1}. {_sanitize(p.policy_text, 2000)}" for i, p in enumerate(policies)
    )
    return (
        f"Active policies ({len(policies)} total):\n{policy_lines}\n\n"
        f"Reimbursement request to evaluate:\n"
        f"  <description>{_sanitize(reimb.description, 1000)}</description>\n"
        f"  <amount>{reimb.amount} {reimb.currency}</amount>\n"
        f"  <category>{reimb.category.value}</category>\n\n"
        "Return JSON only."
    )


async def run_reimbursement_policy_check(ctx: dict, *, reimb_id: str) -> None:  # noqa: ARG001
    """ARQ job entry point. ctx is the ARQ worker context dict."""

    # Phase 1: mark as POLICY_CHECKED and commit so FM can see progress
    async with get_session_factory()() as db:
        reimb = (await db.execute(
            select(Reimbursement).where(Reimbursement.id == reimb_id).with_for_update()
        )).scalar_one_or_none()

        if reimb is None:
            logger.warning("run_reimbursement_policy_check: reimb %s not found", reimb_id)
            return

        if reimb.status != ReimbursementStatus.SUBMITTED:
            logger.info(
                "run_reimbursement_policy_check: reimb %s in %s — skipping",
                reimb_id, reimb.status,
            )
            return

        # Mark as POLICY_CHECKED so FM can see it's being processed
        reimb.status = ReimbursementStatus.POLICY_CHECKED
        await db.commit()

    # Phase 2: reload with FOR UPDATE for the verdict write
    async with get_session_factory()() as db2:
        reimb2 = (await db2.execute(
            select(Reimbursement).where(Reimbursement.id == reimb_id).with_for_update()
        )).scalar_one()

        policies = list((await db2.execute(
            select(Policy).where(
                Policy.org_id == reimb2.org_id,
                Policy.is_active.is_(True),
                Policy.deleted_at.is_(None),
            )
        )).scalars().all())

        if not policies:
            reimb2.status = ReimbursementStatus.APPROVED
            await notify_all_fms(
                db=db2,
                org_id=reimb2.org_id,
                notification_type=NotificationType.APPROVAL_REQUESTED,
                entity_id=reimb2.id,
                body=(
                    f"Reimbursement of {reimb2.currency} {reimb2.amount} "
                    "auto-approved (no active policies)."
                ),
            )
            await db2.commit()
            return

        user_prompt = _build_reimbursement_prompt(reimb2, policies)

        try:
            result, _ = await complete_json(
                system=_SYSTEM_PROMPT,
                user=user_prompt,
                schema=PolicyCheckResult,
                temperature=0.0,
                max_tokens=600,
            )
        except (LLMValidationError, LLMUnavailableError) as exc:
            # Fail-safe: route to FM for manual review
            reimb2.status = ReimbursementStatus.APPROVED
            await notify_all_fms(
                db=db2,
                org_id=reimb2.org_id,
                notification_type=NotificationType.APPROVAL_REQUESTED,
                entity_id=reimb2.id,
                body=(
                    f"Reimbursement needs manual review — policy engine error "
                    f"({type(exc).__name__})."
                ),
            )
            await db2.commit()
            return

        try:
            verdict = PolicyVerdict(result.verdict)
        except ValueError:
            verdict = PolicyVerdict.FLAGGED

        if verdict == PolicyVerdict.APPROVED:
            reimb2.status = ReimbursementStatus.APPROVED
            await notify_all_fms(
                db=db2,
                org_id=reimb2.org_id,
                notification_type=NotificationType.APPROVAL_REQUESTED,
                entity_id=reimb2.id,
                body=(
                    f"Reimbursement of {reimb2.currency} {reimb2.amount} approved by policy. "
                    "Ready for FM sign-off."
                ),
            )

        elif verdict == PolicyVerdict.FLAGGED:
            # No FLAGGED status in reimbursement_status — route to FM as APPROVED
            reimb2.status = ReimbursementStatus.APPROVED
            await notify_all_fms(
                db=db2,
                org_id=reimb2.org_id,
                notification_type=NotificationType.APPROVAL_REQUESTED,
                entity_id=reimb2.id,
                body=(
                    f"Reimbursement flagged by policy: {result.reason}. "
                    "Manual review required."
                ),
            )

        else:  # BLOCKED
            reimb2.status = ReimbursementStatus.REJECTED
            reimb2.decision_reason = result.policy_matched or result.reason
            await fire_notification(
                db=db2,
                org_id=reimb2.org_id,
                user_id=reimb2.user_id,
                notification_type=NotificationType.APPROVAL_REJECTED,
                entity_id=reimb2.id,
                body=f"Your reimbursement was rejected: {reimb2.decision_reason}",
            )

        await db2.commit()
