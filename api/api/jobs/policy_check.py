"""ARQ job: run_policy_check

Loads all active policies for the transaction's org, formats a plain-text
prompt, and calls the LLM to produce a verdict (APPROVED | FLAGGED | BLOCKED).

Idempotent: guards on transaction.state == POLICY_CHECKED before doing work.
Model is text-only (Llama 3.1 8B). Policies and transaction metadata are
serialised as plain text — no vision, no structured query.
"""
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.base import get_session_factory
from api.llm.llm_client import LLMUnavailableError, LLMValidationError, complete_json
from api.llm.schemas import PolicyCheckResult
from api.models.notification import NotificationType
from api.models.policy import Policy
from api.models.transaction import (
    PolicyVerdict,
    Transaction,
    TransactionEvent,
    TransactionPolicyResult,
    TransactionState,
)
from api.models.user import UserRole
from api.services.notification_service import notify_all_fms
from api.services.transaction_service import LEGAL_TRANSITIONS

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a corporate expense compliance engine for a spend management platform.
You are given a list of plain-English expense policies and a transaction to evaluate.
Respond with JSON only — no explanation, no markdown.

Verdict rules (use the most restrictive that applies):
  BLOCKED  — the transaction clearly and unambiguously violates a hard policy
             (e.g. personal purchases, gambling, non-business vendors, hard INR caps).
  FLAGGED  — the transaction is borderline, unusual, or exceeds a soft threshold
             that requires human sign-off from a Finance Manager or Admin.
  APPROVED — the transaction is clearly compliant with all active policies.

Output fields:
  verdict                  : "APPROVED" | "FLAGGED" | "BLOCKED"
  reason                   : concise explanation (max 1000 chars)
  policy_matched           : verbatim text of the triggered policy, or null
  requires_approval_from   : "FINANCE_MANAGER" | "ADMIN" | null  (only when FLAGGED)"""


def _build_user_prompt(txn: Transaction, policies: list[Policy]) -> str:
    policy_lines = "\n".join(f"  {i + 1}. {p.policy_text}" for i, p in enumerate(policies))
    return (
        f"Active policies ({len(policies)} total):\n"
        f"{policy_lines}\n\n"
        f"Transaction:\n"
        f"  Merchant   : {txn.merchant}\n"
        f"  Amount     : {txn.amount} {txn.currency}\n"
        f"  Category   : {txn.category.value}\n"
        f"  Description: {txn.description or '(none)'}\n\n"
        "Return JSON only."
    )


def _write_transition(
    db: AsyncSession,
    txn: Transaction,
    to_state: TransactionState,
    org_id: UUID,
    reason: str | None = None,
) -> None:
    """Append a TransactionEvent and mutate txn.state.  No commit — caller commits."""
    from_state = txn.state
    if to_state not in LEGAL_TRANSITIONS[from_state]:
        raise ValueError(
            f"run_policy_check: illegal transition {from_state.value} → {to_state.value}"
        )
    db.add(
        TransactionEvent(
            transaction_id=txn.id,
            org_id=org_id,
            from_state=from_state,
            to_state=to_state,
            triggered_by_user=None,
            triggered_by_system=True,
            reason=reason,
            event_metadata={
                "from": from_state.value if from_state else None,
                "to": to_state.value,
                "triggered_by": "system",
            },
        )
    )
    txn.state = to_state


async def run_policy_check(ctx: dict, *, txn_id: str) -> None:  # noqa: ARG001
    """ARQ job entry point.  ctx is the ARQ worker context dict."""
    async with get_session_factory()() as db:
        txn = (
            await db.execute(select(Transaction).where(Transaction.id == txn_id))
        ).scalar_one_or_none()

        if txn is None:
            logger.warning("run_policy_check: txn %s not found — skipping", txn_id)
            return

        if txn.state != TransactionState.POLICY_CHECKED:
            logger.info(
                "run_policy_check: txn %s is in %s state — idempotent skip",
                txn_id,
                txn.state.value,
            )
            return

        logger.info("run_policy_check: starting policy check for txn %s", txn_id)

        # Load every active policy scoped to this org
        policies = list(
            (
                await db.execute(
                    select(Policy).where(
                        Policy.org_id == txn.org_id,
                        Policy.is_active.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )

        # ------------------------------------------------------------------ #
        # Fast path: no active policies → auto-approve straight to CLEARED
        # ------------------------------------------------------------------ #
        if not policies:
            logger.info(
                "run_policy_check: no active policies for org %s — auto-approving txn %s",
                txn.org_id,
                txn_id,
            )
            db.add(
                TransactionPolicyResult(
                    org_id=txn.org_id,
                    transaction_id=txn.id,
                    verdict=PolicyVerdict.APPROVED,
                    reason="No active policies — transaction automatically approved.",
                    policy_matched=None,
                    raw_llm_response={},
                    llm_model="none",
                    llm_latency_ms=None,
                )
            )
            _write_transition(
                db, txn, TransactionState.APPROVED, txn.org_id,
                reason="No active policies — auto-approved",
            )
            _write_transition(
                db, txn, TransactionState.CLEARED, txn.org_id,
                reason="Auto-cleared after approval",
            )
            await db.commit()
            return

        # ------------------------------------------------------------------ #
        # LLM path: evaluate against active policies
        # ------------------------------------------------------------------ #
        user_prompt = _build_user_prompt(txn, policies)

        try:
            result, latency_ms = await complete_json(
                system=_SYSTEM_PROMPT,
                user=user_prompt,
                schema=PolicyCheckResult,
                temperature=0.0,
                max_tokens=600,
            )
        except (LLMValidationError, LLMUnavailableError) as exc:
            logger.error(
                "run_policy_check: LLM error for txn %s: %s", txn_id, exc
            )
            # Fail safe: flag the transaction so a human can review it
            db.add(
                TransactionPolicyResult(
                    org_id=txn.org_id,
                    transaction_id=txn.id,
                    verdict=PolicyVerdict.FLAGGED,
                    reason=(
                        f"Policy engine unavailable — flagged for manual review. "
                        f"({type(exc).__name__})"
                    ),
                    policy_matched=None,
                    requires_approval_from_role=UserRole.FINANCE_MANAGER,
                    raw_llm_response={"error": str(exc)},
                    llm_model="error",
                    llm_latency_ms=None,
                )
            )
            _write_transition(
                db, txn, TransactionState.FLAGGED, txn.org_id,
                reason="LLM policy engine error — flagged for manual review",
            )
            await db.commit()
            await notify_all_fms(
                db=db,
                org_id=txn.org_id,
                notification_type=NotificationType.POLICY_FLAGGED,
                entity_id=txn.id,
                body=(
                    f"Transaction flagged: policy engine unavailable "
                    f"({type(exc).__name__}). Manual review required."
                ),
            )
            await db.commit()
            return

        # Map LLM role string → UserRole enum
        requires_role: UserRole | None = None
        if result.requires_approval_from == "FINANCE_MANAGER":
            requires_role = UserRole.FINANCE_MANAGER
        elif result.requires_approval_from == "ADMIN":
            requires_role = UserRole.ADMIN

        verdict = PolicyVerdict(result.verdict)

        db.add(
            TransactionPolicyResult(
                org_id=txn.org_id,
                transaction_id=txn.id,
                verdict=verdict,
                reason=result.reason,
                policy_matched=result.policy_matched,
                requires_approval_from_role=requires_role,
                raw_llm_response={
                    "verdict": result.verdict,
                    "reason": result.reason,
                    "policy_matched": result.policy_matched,
                    "requires_approval_from": result.requires_approval_from,
                },
                llm_model="meta-llama/Llama-3.1-8B-Instruct",
                llm_latency_ms=latency_ms,
            )
        )

        if verdict == PolicyVerdict.APPROVED:
            logger.info(
                "run_policy_check: txn %s APPROVED → CLEARED (latency %dms)",
                txn_id, latency_ms,
            )
            _write_transition(
                db, txn, TransactionState.APPROVED, txn.org_id,
                reason=result.reason,
            )
            _write_transition(
                db, txn, TransactionState.CLEARED, txn.org_id,
                reason="Auto-cleared after policy approval",
            )
            await db.commit()

        elif verdict == PolicyVerdict.FLAGGED:
            logger.info(
                "run_policy_check: txn %s FLAGGED — notifying FMs (latency %dms)",
                txn_id, latency_ms,
            )
            _write_transition(
                db, txn, TransactionState.FLAGGED, txn.org_id,
                reason=result.reason,
            )
            await db.commit()
            await notify_all_fms(
                db=db,
                org_id=txn.org_id,
                notification_type=NotificationType.POLICY_FLAGGED,
                entity_id=txn.id,
                body=f"Transaction flagged for review: {result.reason}",
            )
            await db.commit()

        else:  # BLOCKED
            logger.info(
                "run_policy_check: txn %s BLOCKED (latency %dms)", txn_id, latency_ms
            )
            _write_transition(
                db, txn, TransactionState.BLOCKED, txn.org_id,
                reason=result.reason,
            )
            await db.commit()
            await notify_all_fms(
                db=db,
                org_id=txn.org_id,
                notification_type=NotificationType.POLICY_BLOCKED,
                entity_id=txn.id,
                body=f"Transaction blocked by policy: {result.reason}",
            )
            await db.commit()
