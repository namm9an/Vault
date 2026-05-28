"""ARQ job: run_reimbursement_policy_check

Phase 1: SUBMITTED → POLICY_CHECKED (commit so FM can see progress)
Phase 2: load policies, call LLM, record verdict.

State transitions:
  APPROVED verdict → keep POLICY_CHECKED  (FM signs off via approve_reimbursement)
  FLAGGED  verdict → keep POLICY_CHECKED  (FM reviews — flagged in notification body)
  BLOCKED  verdict → REJECTED immediately (decided_by=None, decided_at=now)

Idempotency:
  Phase 1 guard: status != SUBMITTED → skip (already processed or retrying past crash)
  Phase 2 guard: status != POLICY_CHECKED → skip (Phase 2 already completed)

Single-commit rule: each phase writes all state + AuditLog + notifications in one commit.
"""
import logging
import re
from datetime import datetime, timezone

from sqlalchemy import select

from api.db.base import get_session_factory
from api.llm.llm_client import LLMUnavailableError, LLMValidationError, complete_json
from api.llm.schemas import PolicyCheckResult
from api.models.audit_log import AuditLog
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

    # -------------------------------------------------------------------------
    # Phase 1: SUBMITTED → POLICY_CHECKED (commit for FM visibility)
    # -------------------------------------------------------------------------
    async with get_session_factory()() as db:
        reimb = (await db.execute(
            select(Reimbursement).where(Reimbursement.id == reimb_id).with_for_update()
        )).scalar_one_or_none()

        if reimb is None:
            logger.warning("run_reimbursement_policy_check: reimb %s not found", reimb_id)
            return

        if reimb.status != ReimbursementStatus.SUBMITTED:
            logger.info(
                "run_reimbursement_policy_check: reimb %s in %s — Phase 1 skip",
                reimb_id, reimb.status,
            )
            # May have already passed Phase 1; fall through to Phase 2 below.
            # If status is beyond POLICY_CHECKED, Phase 2 guard will skip cleanly.
        else:
            reimb.status = ReimbursementStatus.POLICY_CHECKED
            db.add(AuditLog(
                org_id=reimb.org_id,
                actor_user_id=None,
                action="reimbursement.policy_checked",
                entity_type="reimbursement",
                entity_id=reimb.id,
                log_metadata={"job": "run_reimbursement_policy_check"},
            ))
            await db.commit()

    # -------------------------------------------------------------------------
    # Phase 2: load policies, call LLM, write verdict in one commit
    # -------------------------------------------------------------------------
    async with get_session_factory()() as db2:
        reimb2 = (await db2.execute(
            select(Reimbursement).where(Reimbursement.id == reimb_id).with_for_update()
        )).scalar_one()

        # Idempotency guard for Phase 2 — if already past POLICY_CHECKED, bail out
        if reimb2.status != ReimbursementStatus.POLICY_CHECKED:
            logger.info(
                "run_reimbursement_policy_check: reimb %s in %s — Phase 2 skip",
                reimb_id, reimb2.status,
            )
            return

        policies = list((await db2.execute(
            select(Policy).where(
                Policy.org_id == reimb2.org_id,
                Policy.is_active.is_(True),
                Policy.deleted_at.is_(None),
            )
        )).scalars().all())

        if not policies:
            # No policies → leave POLICY_CHECKED for FM sign-off
            db2.add(AuditLog(
                org_id=reimb2.org_id,
                actor_user_id=None,
                action="reimbursement.policy_no_rules",
                entity_type="reimbursement",
                entity_id=reimb2.id,
                log_metadata={"reason": "no active policies — routed to FM"},
            ))
            await notify_all_fms(
                db=db2,
                org_id=reimb2.org_id,
                notification_type=NotificationType.APPROVAL_REQUESTED,
                entity_id=reimb2.id,
                body=(
                    f"Reimbursement of {reimb2.currency} {reimb2.amount} "
                    "needs FM sign-off (no active policies to auto-evaluate)."
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
            # Fail-safe: leave POLICY_CHECKED for FM to review manually
            db2.add(AuditLog(
                org_id=reimb2.org_id,
                actor_user_id=None,
                action="reimbursement.policy_error",
                entity_type="reimbursement",
                entity_id=reimb2.id,
                log_metadata={"error": type(exc).__name__},
            ))
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

        if verdict == PolicyVerdict.BLOCKED:
            # Auto-reject — system actor fills decided_by/decided_at
            reimb2.status = ReimbursementStatus.REJECTED
            reimb2.decision_reason = result.policy_matched or result.reason
            reimb2.decided_by = None   # system-driven
            reimb2.decided_at = datetime.now(timezone.utc)
            db2.add(AuditLog(
                org_id=reimb2.org_id,
                actor_user_id=None,
                action="reimbursement.policy_blocked",
                entity_type="reimbursement",
                entity_id=reimb2.id,
                log_metadata={
                    "verdict": "BLOCKED",
                    "reason": result.reason,
                    "policy_matched": result.policy_matched,
                },
            ))
            await fire_notification(
                db=db2,
                org_id=reimb2.org_id,
                user_id=reimb2.user_id,
                notification_type=NotificationType.APPROVAL_REJECTED,
                entity_id=reimb2.id,
                body=f"Your reimbursement was rejected: {reimb2.decision_reason}",
            )
        else:
            # APPROVED or FLAGGED — keep POLICY_CHECKED, let FM sign off
            action = "reimbursement.policy_approved" if verdict == PolicyVerdict.APPROVED else "reimbursement.policy_flagged"
            flagged_suffix = " (flagged by policy — review required)" if verdict == PolicyVerdict.FLAGGED else ""
            db2.add(AuditLog(
                org_id=reimb2.org_id,
                actor_user_id=None,
                action=action,
                entity_type="reimbursement",
                entity_id=reimb2.id,
                log_metadata={
                    "verdict": verdict.value,
                    "reason": result.reason,
                    "policy_matched": result.policy_matched,
                },
            ))
            await notify_all_fms(
                db=db2,
                org_id=reimb2.org_id,
                notification_type=NotificationType.APPROVAL_REQUESTED,
                entity_id=reimb2.id,
                body=(
                    f"Reimbursement of {reimb2.currency} {reimb2.amount} "
                    f"is ready for FM sign-off{flagged_suffix}."
                ),
            )

        await db2.commit()
