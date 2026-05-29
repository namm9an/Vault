"""Idempotent demo seed — Phase 7 rewrite.

Run inside the api container:
    docker compose -f docker-compose.prod.yml exec api python -m api.db.seeds

The seed creates:
  - 1 org (acme)
  - 4 users (ADMIN, FINANCE_MANAGER, 2x EMPLOYEE)
  - 3 departments (Engineering, Marketing, Operations)
  - 6 cards
  - 5 active policies
  - 40 transactions across 28 days (direct insert — deterministic final state)
  - 6 reimbursements
  - 4 unread notifications for Naman

Idempotency: checks Organization.slug == "acme" before seeding.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.base import get_session_factory
from api.models.audit_log import AuditLog
from api.models.card import Card, CardStatus, SpendCategory
from api.models.department import Department
from api.models.notification import Notification, NotificationType
from api.models.organization import Organization
from api.models.policy import Policy
from api.models.reimbursement import Reimbursement, ReimbursementStatus
from api.models.transaction import (
    PolicyVerdict,
    Transaction,
    TransactionEvent,
    TransactionPolicyResult,
    TransactionState,
)
from api.models.user import User, UserRole
from api.utils.security import hash_password


DEMO_ORG_SLUG = "acme"
DEMO_PASSWORD = "vault-demo-pass"
_LLM_MODEL = "meta-llama/Llama-3.1-8B-Instruct"

# Policies — 5 active rules used by the policy engine
POLICY_TEXTS = [
    "No alcohol or bar purchases above ₹500",                                          # 0 (unused)
    "All SaaS tool purchases above ₹10,000 require Finance Manager approval",          # 1
    "Travel bookings above ₹50,000 must have prior approval",                          # 2
    "Marketing agency payments above ₹75,000 require CFO sign-off",                   # 3
    "No hardware purchases above ₹1,00,000 without executive approval",                # 4
]

_POLICY_REASONS: dict[int | str, str] = {
    1: "SaaS purchase above ₹10,000 requires Finance Manager approval",
    2: "Travel booking above ₹50,000 requires prior approval",
    3: "Marketing agency payment above ₹75,000 requires CFO sign-off",
    4: "Hardware purchase above ₹1,00,000 is blocked — executive approval required",
    "blocked_mkt": "Marketing agency payment of ₹1,20,000 exceeds policy threshold — blocked",
}

# Transaction seed data:
# (card_idx, amount, merchant, category, days_ago, final_state, policy_key)
#
# card_idx:   0=Bob Travel  1=Bob SaaS  2=Carol Ads  3=Carol Events
#             4=Naman Corporate  5=Felix Operations
# policy_key: None → CLEARED   int → FLAGGED by POLICY_TEXTS[int]
#             "blocked_mkt" → BLOCKED (marketing over threshold)
_SEED_TXNS: list[tuple[int, str, str, SpendCategory, int, TransactionState, int | str | None]] = [
    # ── Week 4 (days 22–28, oldest) — all CLEARED ────────────────────────────
    (0, "3200.00",   "Ola Business",              SpendCategory.TRAVEL,    22, TransactionState.CLEARED, None),
    (0, "8500.00",   "IndiGo Airlines",           SpendCategory.TRAVEL,    25, TransactionState.CLEARED, None),
    (1, "4999.00",   "Notion",                    SpendCategory.SAAS,      24, TransactionState.CLEARED, None),
    (2, "22000.00",  "Meta Ads",                  SpendCategory.MARKETING, 23, TransactionState.CLEARED, None),
    (2, "18500.00",  "Google Ads",                SpendCategory.MARKETING, 26, TransactionState.CLEARED, None),
    (3, "9200.00",   "Eventbrite India",          SpendCategory.OFFICE,    27, TransactionState.CLEARED, None),
    (4, "12000.00",  "Blue Tokai Coffee",         SpendCategory.MEALS,     28, TransactionState.CLEARED, None),
    (5, "6500.00",   "Staples India",             SpendCategory.OFFICE,    22, TransactionState.CLEARED, None),
    (0, "1800.00",   "Uber Business",             SpendCategory.TRAVEL,    24, TransactionState.CLEARED, None),
    (2, "31000.00",  "LinkedIn Ads",              SpendCategory.MARKETING, 25, TransactionState.CLEARED, None),
    # ── Week 3 (days 15–21) — CLEARED + FLAGGED ─────────────────────────────
    (1, "14500.00",  "GitHub Teams",              SpendCategory.SAAS,      15, TransactionState.FLAGGED, 1),
    (0, "62000.00",  "MakeMyTrip Conference",     SpendCategory.TRAVEL,    16, TransactionState.FLAGGED, 2),
    (2, "88000.00",  "XYZ Creative Agency",       SpendCategory.MARKETING, 17, TransactionState.FLAGGED, 3),
    (4, "25000.00",  "AWS India",                 SpendCategory.SAAS,      18, TransactionState.CLEARED, None),
    (3, "14000.00",  "Taj Hotels",                SpendCategory.TRAVEL,    19, TransactionState.CLEARED, None),
    (5, "4200.00",   "JioMart Business",          SpendCategory.OFFICE,    20, TransactionState.CLEARED, None),
    (0, "2900.00",   "Rapido Business",           SpendCategory.TRAVEL,    21, TransactionState.CLEARED, None),
    (2, "45000.00",  "Hotstar Ads",               SpendCategory.MARKETING, 15, TransactionState.CLEARED, None),
    (4, "8800.00",   "Swiggy Catering",           SpendCategory.MEALS,     16, TransactionState.CLEARED, None),
    (1, "3500.00",   "Figma",                     SpendCategory.SAAS,      17, TransactionState.CLEARED, None),
    # ── Week 2 (days 8–14) — BLOCKED + FLAGGED + CLEARED ────────────────────
    (4, "155000.00", "Apple India MacBook",       SpendCategory.HARDWARE,   8, TransactionState.BLOCKED, 4),
    (0, "72000.00",  "Air India Business",        SpendCategory.TRAVEL,     9, TransactionState.FLAGGED, 2),
    (2, "95000.00",  "WPP India Agency",          SpendCategory.MARKETING, 10, TransactionState.FLAGGED, 3),
    (5, "11500.00",  "Zoho One",                  SpendCategory.SAAS,      11, TransactionState.FLAGGED, 1),
    (1, "7200.00",   "Slack Pro",                 SpendCategory.SAAS,      12, TransactionState.CLEARED, None),
    (3, "28000.00",  "Hyatt Regency",             SpendCategory.TRAVEL,    13, TransactionState.CLEARED, None),
    (4, "18000.00",  "Dell Monitors x2",          SpendCategory.HARDWARE,  14, TransactionState.CLEARED, None),
    (2, "55000.00",  "Times of India Digital",    SpendCategory.MARKETING,  8, TransactionState.CLEARED, None),
    (0, "4100.00",   "Ola Business Airport",      SpendCategory.TRAVEL,     9, TransactionState.CLEARED, None),
    (4, "6800.00",   "Starbucks Team",            SpendCategory.MEALS,     10, TransactionState.CLEARED, None),
    # ── Week 1 (days 1–7, most recent) — BLOCKED + FLAGGED + CLEARED ────────
    (1, "22000.00",  "Atlassian Jira",            SpendCategory.SAAS,       1, TransactionState.FLAGGED, 1),
    (2, "120000.00", "Dentsu India",              SpendCategory.MARKETING,  2, TransactionState.BLOCKED, "blocked_mkt"),
    (4, "38000.00",  "HP LaserJet",               SpendCategory.HARDWARE,   3, TransactionState.CLEARED, None),
    (0, "5500.00",   "IndiGo Domestic",           SpendCategory.TRAVEL,     4, TransactionState.CLEARED, None),
    (3, "42000.00",  "ITC Hotel",                 SpendCategory.TRAVEL,     5, TransactionState.CLEARED, None),
    (5, "8900.00",   "Amazon Business Supplies",  SpendCategory.OFFICE,     6, TransactionState.CLEARED, None),
    (2, "67000.00",  "Google Ads Q2 Boost",       SpendCategory.MARKETING,  7, TransactionState.FLAGGED, 3),
    (4, "15500.00",  "Microsoft 365",             SpendCategory.SAAS,       1, TransactionState.FLAGGED, 1),
    (0, "3800.00",   "Zoom Pro Annual",           SpendCategory.SAAS,       2, TransactionState.CLEARED, None),
    (2, "29000.00",  "Instagram Reels Campaign",  SpendCategory.MARKETING,  3, TransactionState.CLEARED, None),
]


async def _seed_transaction_direct(
    db: AsyncSession,
    *,
    org_id: UUID,
    user_id: UUID,
    card_id: UUID,
    department_id: UUID | None,
    amount: Decimal,
    merchant: str,
    category: SpendCategory,
    final_state: TransactionState,
    occurred_at: datetime,
    actor_user_id: UUID,
    policy_key: int | str | None,
) -> Transaction:
    """Insert a Transaction directly in its final state with full event chain.

    Bypasses create_transaction() and the ARQ worker so demo data is always in
    its terminal state immediately after seeding — no async resolution needed.
    """
    txn_id = uuid4()

    # Determine policy verdict based on final state
    if final_state == TransactionState.CLEARED:
        verdict = PolicyVerdict.APPROVED
        reason = "No applicable policy"
        policy_matched: str | None = None
        requires_approval_from: UserRole | None = None
    elif final_state == TransactionState.FLAGGED:
        assert isinstance(policy_key, int), "FLAGGED requires int policy_key"
        verdict = PolicyVerdict.FLAGGED
        reason = _POLICY_REASONS[policy_key]
        policy_matched = POLICY_TEXTS[policy_key]
        # Policies 3 (CFO sign-off) and 4 (executive approval) → ADMIN
        requires_approval_from = (
            UserRole.ADMIN if policy_key in (3, 4) else UserRole.FINANCE_MANAGER
        )
    else:  # BLOCKED
        verdict = PolicyVerdict.BLOCKED
        if isinstance(policy_key, int):
            reason = _POLICY_REASONS[policy_key]
            policy_matched = POLICY_TEXTS[policy_key]
        else:
            reason = _POLICY_REASONS.get(str(policy_key), "Transaction blocked by policy")
            policy_matched = POLICY_TEXTS[3]  # marketing policy
        requires_approval_from = None

    # Transaction row in final state
    txn = Transaction(
        id=txn_id,
        org_id=org_id,
        user_id=user_id,
        card_id=card_id,
        department_id=department_id,
        amount=amount,
        currency="INR",
        merchant=merchant,
        category=category,
        state=final_state,
        occurred_at=occurred_at,
        created_at=occurred_at,
        updated_at=occurred_at,
    )
    db.add(txn)

    # Build event chain — append-only audit trail
    base_meta = {"merchant": merchant, "amount": str(amount), "category": category.value}
    t0 = occurred_at
    t1 = occurred_at + timedelta(seconds=1)
    t2 = occurred_at + timedelta(seconds=2)
    t3 = occurred_at + timedelta(seconds=3)

    def _evt(
        from_s: TransactionState | None,
        to_s: TransactionState,
        ts: datetime,
        *,
        system: bool = True,
        evt_reason: str | None = None,
    ) -> TransactionEvent:
        return TransactionEvent(
            transaction_id=txn_id,
            org_id=org_id,
            from_state=from_s,
            to_state=to_s,
            triggered_by_user=None if system else actor_user_id,
            triggered_by_system=system,
            reason=evt_reason,
            event_metadata={
                "from": from_s.value if from_s else None,
                "to": to_s.value,
                "triggered_by": "system" if system else str(actor_user_id),
                **base_meta,
            },
            created_at=ts,
        )

    # INITIATED — triggered by user
    db.add(TransactionEvent(
        transaction_id=txn_id,
        org_id=org_id,
        from_state=None,
        to_state=TransactionState.INITIATED,
        triggered_by_user=actor_user_id,
        triggered_by_system=False,
        reason="Transaction created",
        event_metadata={
            "from": None, "to": "INITIATED",
            "triggered_by": str(actor_user_id), **base_meta,
        },
        created_at=t0,
    ))

    db.add(_evt(TransactionState.INITIATED, TransactionState.POLICY_CHECKED, t1,
                evt_reason="Policy check initiated by system"))

    if final_state == TransactionState.CLEARED:
        db.add(_evt(TransactionState.POLICY_CHECKED, TransactionState.APPROVED, t2,
                    evt_reason=f"LLM verdict: APPROVED — {reason}"))
        db.add(_evt(TransactionState.APPROVED, TransactionState.CLEARED, t3,
                    evt_reason="Transaction cleared"))
    elif final_state == TransactionState.FLAGGED:
        db.add(_evt(TransactionState.POLICY_CHECKED, TransactionState.FLAGGED, t2,
                    evt_reason=f"LLM verdict: FLAGGED — {reason}"))
    else:  # BLOCKED
        db.add(_evt(TransactionState.POLICY_CHECKED, TransactionState.BLOCKED, t2,
                    evt_reason=f"LLM verdict: BLOCKED — {reason}"))

    # Policy result row
    db.add(TransactionPolicyResult(
        org_id=org_id,
        transaction_id=txn_id,
        verdict=verdict,
        reason=reason,
        policy_matched=policy_matched,
        matched_policy_id=None,
        requires_approval_from_role=requires_approval_from,
        raw_llm_response={
            "verdict": verdict.value,
            "reason": reason,
            "policy_matched": policy_matched,
            "requires_approval_from": (
                requires_approval_from.value if requires_approval_from else None
            ),
        },
        llm_model=_LLM_MODEL,
        llm_latency_ms=380 + (hash(merchant) % 220),
        created_at=occurred_at + timedelta(seconds=2),
    ))

    return txn


async def reseed_transactional(
    db: AsyncSession,
    org: Organization,
    naman: User,
    felix: User,
    bob: User,
    carol: User,
    eng_dept: Department,
    mkt_dept: Department,
    ops_dept: Department,
    cards: list[Card],
) -> dict[str, int]:
    """Seed transactions, reimbursements, and notifications for an existing org.

    Called by run() on first boot and by the demo reset endpoint on each reset.
    The caller is responsible for committing after this returns.

    cards must be ordered: [BobTravel, BobSaaS, CarolAds, CarolEvents,
                            NamanCorporate, FelixOperations]
    """
    now = datetime.now(timezone.utc)

    # Map card index → (user, department)
    _card_users = [bob, bob, carol, carol, naman, felix]
    _card_depts = [eng_dept, eng_dept, mkt_dept, mkt_dept, eng_dept, ops_dept]

    txn_count = 0
    for card_idx, amount, merchant, category, days_ago, final_state, policy_key in _SEED_TXNS:
        card = cards[card_idx]
        user = _card_users[card_idx]
        dept = _card_depts[card_idx]
        occurred_at = now - timedelta(days=days_ago)

        await _seed_transaction_direct(
            db,
            org_id=org.id,
            user_id=user.id,
            card_id=card.id,
            department_id=dept.id,
            amount=Decimal(amount),
            merchant=merchant,
            category=category,
            final_state=final_state,
            occurred_at=occurred_at,
            actor_user_id=naman.id,
            policy_key=policy_key,
        )
        txn_count += 1

    await db.flush()

    # Reimbursements (6)
    reimbs = [
        Reimbursement(
            org_id=org.id,
            user_id=carol.id,
            department_id=mkt_dept.id,
            amount=Decimal("1200.00"),
            currency="INR",
            category=SpendCategory.MEALS,
            description="Team lunch — client meeting",
            status=ReimbursementStatus.APPROVED,
            decision_reason="Approved — within meal policy",
            decided_by=naman.id,
            decided_at=now - timedelta(days=3),
        ),
        Reimbursement(
            org_id=org.id,
            user_id=bob.id,
            department_id=eng_dept.id,
            amount=Decimal("850.00"),
            currency="INR",
            category=SpendCategory.TRAVEL,
            description="Auto-rickshaw to client office",
            status=ReimbursementStatus.SUBMITTED,
        ),
        Reimbursement(
            org_id=org.id,
            user_id=carol.id,
            department_id=mkt_dept.id,
            amount=Decimal("15000.00"),
            currency="INR",
            category=SpendCategory.SAAS,
            description="Annual SaaS subscription renewal",
            status=ReimbursementStatus.REJECTED,
            decision_reason="Amount exceeds per-request limit — raise a PO instead",
            decided_by=naman.id,
            decided_at=now - timedelta(days=5),
        ),
        Reimbursement(
            org_id=org.id,
            user_id=bob.id,
            department_id=eng_dept.id,
            amount=Decimal("4500.00"),
            currency="INR",
            category=SpendCategory.TRAVEL,
            description="Conference hotel — personal card",
            status=ReimbursementStatus.APPROVED,
            decision_reason="Approved — conference attendance confirmed",
            decided_by=felix.id,
            decided_at=now - timedelta(days=10),
        ),
        Reimbursement(
            org_id=org.id,
            user_id=felix.id,
            department_id=ops_dept.id,
            amount=Decimal("2200.00"),
            currency="INR",
            category=SpendCategory.OFFICE,
            description="Stationery and office supplies",
            status=ReimbursementStatus.SUBMITTED,
        ),
        Reimbursement(
            org_id=org.id,
            user_id=carol.id,
            department_id=mkt_dept.id,
            amount=Decimal("8000.00"),
            currency="INR",
            category=SpendCategory.PROFESSIONAL_SERVICES,
            description="Photography for event",
            status=ReimbursementStatus.POLICY_CHECKED,
        ),
    ]
    for r in reimbs:
        db.add(r)

    # Notifications for Naman — 4 unread on first login
    notifs = [
        Notification(
            org_id=org.id,
            user_id=naman.id,
            type=NotificationType.POLICY_FLAGGED,
            title="High-value SaaS transaction flagged",
            body="Atlassian Jira ₹22,000 — SaaS purchase requires Finance Manager approval",
            link="/transactions",
            payload={"amount": "22000.00", "merchant": "Atlassian Jira"},
        ),
        Notification(
            org_id=org.id,
            user_id=naman.id,
            type=NotificationType.POLICY_BLOCKED,
            title="Transaction blocked — CFO approval needed",
            body="Dentsu India ₹1,20,000 — marketing agency payment exceeds policy threshold",
            link="/transactions",
            payload={"amount": "120000.00", "merchant": "Dentsu India"},
        ),
        Notification(
            org_id=org.id,
            user_id=naman.id,
            type=NotificationType.BUDGET_THRESHOLD,
            title="Marketing budget threshold breached",
            body="Marketing department has exceeded 80% of its ₹3,00,000 monthly budget",
            link="/departments",
            payload={"department": "Marketing", "threshold_pct": 80},
        ),
        Notification(
            org_id=org.id,
            user_id=naman.id,
            type=NotificationType.DIGEST_READY,
            title="Weekly spend digest ready",
            body="Your AI-generated spend digest for the past 7 days is available",
            link="/digest",
            payload={},
        ),
    ]
    for n in notifs:
        db.add(n)

    await db.flush()

    return {
        "transactions": txn_count,
        "reimbursements": len(reimbs),
        "notifications": len(notifs),
    }


async def run() -> None:
    async with get_session_factory()() as db:
        existing = (
            await db.execute(select(Organization).where(Organization.slug == DEMO_ORG_SLUG))
        ).scalar_one_or_none()
        if existing is not None:
            print(f"Seed already present (org slug='{DEMO_ORG_SLUG}'). Nothing to do.")
            return

        # ── Organization ──────────────────────────────────────────────────────
        org = Organization(name="Acme Corp", slug=DEMO_ORG_SLUG)
        db.add(org)
        await db.flush()

        # ── Users ─────────────────────────────────────────────────────────────
        pw = hash_password(DEMO_PASSWORD)
        naman = User(org_id=org.id, email="naman.moudgill@e2enetworks.com",
                     password_hash=pw, full_name="Naman Moudgill",
                     role=UserRole.ADMIN, is_active=True)
        felix = User(org_id=org.id, email="fm@acme.com",
                     password_hash=pw, full_name="Felix Mehta",
                     role=UserRole.FINANCE_MANAGER, is_active=True)
        bob   = User(org_id=org.id, email="bob@acme.com",
                     password_hash=pw, full_name="Bob Patel",
                     role=UserRole.EMPLOYEE, is_active=True)
        carol = User(org_id=org.id, email="carol@acme.com",
                     password_hash=pw, full_name="Carol Singh",
                     role=UserRole.EMPLOYEE, is_active=True)
        for u in [naman, felix, bob, carol]:
            db.add(u)
        await db.flush()

        # ── Departments ───────────────────────────────────────────────────────
        eng_dept = Department(org_id=org.id, name="Engineering",
                              monthly_budget=Decimal("500000"), budget_currency="INR",
                              alert_threshold_pct=80, manager_id=naman.id)
        mkt_dept = Department(org_id=org.id, name="Marketing",
                              monthly_budget=Decimal("300000"), budget_currency="INR",
                              alert_threshold_pct=80, manager_id=felix.id)
        ops_dept = Department(org_id=org.id, name="Operations",
                              monthly_budget=Decimal("150000"), budget_currency="INR",
                              alert_threshold_pct=80, manager_id=naman.id)
        for d in [eng_dept, mkt_dept, ops_dept]:
            db.add(d)
        await db.flush()

        # Assign departments to employees
        bob.department_id   = eng_dept.id
        carol.department_id = mkt_dept.id
        await db.flush()

        # ── Cards (6) ─────────────────────────────────────────────────────────
        cards = [
            Card(org_id=org.id, user_id=bob.id,   department_id=eng_dept.id,
                 nickname="Bob — Travel",     last_four="1001", status=CardStatus.ACTIVE,
                 daily_limit=Decimal("15000"),  monthly_limit=Decimal("200000"),
                 total_limit=Decimal("0"), currency="INR"),
            Card(org_id=org.id, user_id=bob.id,   department_id=eng_dept.id,
                 nickname="Bob — SaaS",       last_four="1002", status=CardStatus.ACTIVE,
                 daily_limit=Decimal("10000"),  monthly_limit=Decimal("100000"),
                 total_limit=Decimal("0"), currency="INR"),
            Card(org_id=org.id, user_id=carol.id, department_id=mkt_dept.id,
                 nickname="Carol — Ads",      last_four="2001", status=CardStatus.ACTIVE,
                 daily_limit=Decimal("25000"),  monthly_limit=Decimal("250000"),
                 total_limit=Decimal("0"), currency="INR"),
            Card(org_id=org.id, user_id=carol.id, department_id=mkt_dept.id,
                 nickname="Carol — Events",   last_four="2002", status=CardStatus.ACTIVE,
                 daily_limit=Decimal("20000"),  monthly_limit=Decimal("150000"),
                 total_limit=Decimal("0"), currency="INR"),
            Card(org_id=org.id, user_id=naman.id, department_id=eng_dept.id,
                 nickname="Naman — Corporate",last_four="3001", status=CardStatus.ACTIVE,
                 daily_limit=Decimal("50000"),  monthly_limit=Decimal("500000"),
                 total_limit=Decimal("0"), currency="INR"),
            Card(org_id=org.id, user_id=felix.id, department_id=ops_dept.id,
                 nickname="Felix — Operations",last_four="4001", status=CardStatus.ACTIVE,
                 daily_limit=Decimal("20000"),  monthly_limit=Decimal("100000"),
                 total_limit=Decimal("0"), currency="INR"),
        ]
        for c in cards:
            db.add(c)

        # ── Policies (5 active) ───────────────────────────────────────────────
        for text in POLICY_TEXTS:
            db.add(Policy(
                org_id=org.id,
                policy_text=text,
                is_active=True,
                created_by=naman.id,
            ))

        await db.commit()

        # ── Transactional data ─────────────────────────────────────────────────
        # Reload cards in correct order after commit (IDs are now set)
        stats = await reseed_transactional(
            db, org, naman, felix, bob, carol, eng_dept, mkt_dept, ops_dept, cards,
        )
        await db.commit()

        print("Seed complete.")
        print(f"  Org:             {org.name} (slug={org.slug})")
        print(f"  Password:        {DEMO_PASSWORD}")
        print("  Users:")
        for email, role in [
            ("naman.moudgill@e2enetworks.com", "ADMIN"),
            ("fm@acme.com", "FINANCE_MANAGER"),
            ("bob@acme.com", "EMPLOYEE"),
            ("carol@acme.com", "EMPLOYEE"),
        ]:
            print(f"    {role:<16} {email}")
        print(f"  Departments:     Engineering, Marketing, Operations")
        print(f"  Cards:           {len(cards)} seeded")
        print(f"  Policies:        {len(POLICY_TEXTS)} active")
        print(f"  Transactions:    {stats['transactions']} seeded")
        print(f"  Reimbursements:  {stats['reimbursements']} seeded")
        print(f"  Notifications:   {stats['notifications']} seeded for Naman")


if __name__ == "__main__":
    asyncio.run(run())
