"""Idempotent demo seed.

Run inside the api container:
    docker compose exec api python -m api.db.seeds
"""
import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from api.db.base import get_session_factory
from api.deps import OrgScope
from api.models.card import Card, CardStatus, SpendCategory
from api.models.department import Department
from api.models.organization import Organization
from api.models.reimbursement import Reimbursement, ReimbursementStatus
from api.models.user import User, UserRole
from api.schemas.transaction import TransactionCreate
from api.services import transaction_service
from api.utils.security import hash_password


DEMO_ORG_SLUG = "acme"
DEMO_PASSWORD = "vault-demo-pass"

DEMO_USERS = [
    ("admin@acme.com", "Alice Sharma", UserRole.ADMIN),
    ("fm@acme.com", "Felix Mehta", UserRole.FINANCE_MANAGER),
    ("bob@acme.com", "Bob Patel", UserRole.EMPLOYEE),
    ("carol@acme.com", "Carol Singh", UserRole.EMPLOYEE),
]

DEMO_DEPARTMENTS = [
    ("Engineering", Decimal("500000")),
    ("Marketing", Decimal("300000")),
]

# Demo transactions: (card_index, amount, merchant, category, description, days_ago)
# card indices: 0=Bob Travel, 1=Bob SaaS, 2=Carol Ads, 3=Carol Events
#
# Policy stub thresholds:
#   > ₹1,00,000 → BLOCKED
#   > ₹50,000   → FLAGGED (awaits FM approval — demo path)
#   otherwise   → CLEARED
DEMO_TRANSACTIONS = [
    # --- 5 CLEARED (normal amounts) ---
    (0, "2450.00",  "Blue Tokai Coffee",      SpendCategory.MEALS,        "Team coffee",             25),
    (1, "8900.00",  "GitHub Teams",            SpendCategory.SAAS,         "Dev tools monthly",       20),
    (2, "15000.00", "Meta Ads",                SpendCategory.MARKETING,    "Q2 Facebook campaign",    18),
    (0, "3200.00",  "Ola Business",            SpendCategory.TRAVEL,       "Client site visit",       10),
    (3, "6750.00",  "Staples India",           SpendCategory.OFFICE,       "Office supplies",          5),
    # --- 2 FLAGGED (50k < amount ≤ 1L — awaits FM approval) ---
    (0, "65000.00", "MakeMyTrip",              SpendCategory.TRAVEL,       "Conference package",       8),
    (2, "85000.00", "XYZ Creative Agency",     SpendCategory.MARKETING,    "Agency retainer — June",   3),
    # --- 1 BLOCKED (amount > 1L — terminal) ---
    (0, "150000.00", "Apple India",            SpendCategory.HARDWARE,     "MacBook Pro 14 M3",        2),
]


async def run() -> None:
    async with get_session_factory()() as db:
        existing = (
            await db.execute(select(Organization).where(Organization.slug == DEMO_ORG_SLUG))
        ).scalar_one_or_none()
        if existing is not None:
            print(f"Seed already present (org slug='{DEMO_ORG_SLUG}'). Nothing to do.")
            return

        # ------------------------------------------------------------------ Org
        org = Organization(name="Acme Corp", slug=DEMO_ORG_SLUG)
        db.add(org)
        await db.flush()

        # ----------------------------------------------------------------- Users
        user_records: list[User] = []
        for email, name, role in DEMO_USERS:
            u = User(
                org_id=org.id,
                email=email,
                password_hash=hash_password(DEMO_PASSWORD),
                full_name=name,
                role=role,
                is_active=True,
            )
            db.add(u)
            user_records.append(u)
        await db.flush()

        admin_user = user_records[0]
        bob_user   = user_records[2]
        carol_user = user_records[3]

        # -------------------------------------------------------------- Departments
        dept_records: list[Department] = []
        for dept_name, budget in DEMO_DEPARTMENTS:
            d = Department(
                org_id=org.id,
                name=dept_name,
                monthly_budget=budget,
                budget_currency="INR",
                alert_threshold_pct=80,
                manager_id=admin_user.id,
            )
            db.add(d)
            dept_records.append(d)
        await db.flush()

        eng_dept = dept_records[0]
        mkt_dept = dept_records[1]

        # --------------------------------------------------------------- Cards
        cards = [
            Card(
                org_id=org.id,
                user_id=bob_user.id,
                department_id=eng_dept.id,
                nickname="Bob — Travel",
                last_four="1001",
                status=CardStatus.ACTIVE,
                daily_limit=Decimal("10000"),
                monthly_limit=Decimal("200000"),   # raised to allow the seeded FLAGGED txn
                total_limit=Decimal("0"),
                currency="INR",
            ),
            Card(
                org_id=org.id,
                user_id=bob_user.id,
                department_id=eng_dept.id,
                nickname="Bob — SaaS",
                last_four="1002",
                status=CardStatus.ACTIVE,
                daily_limit=Decimal("5000"),
                monthly_limit=Decimal("20000"),
                total_limit=Decimal("0"),
                currency="INR",
            ),
            Card(
                org_id=org.id,
                user_id=carol_user.id,
                department_id=mkt_dept.id,
                nickname="Carol — Ads",
                last_four="2001",
                status=CardStatus.ACTIVE,
                daily_limit=Decimal("20000"),
                monthly_limit=Decimal("200000"),
                total_limit=Decimal("0"),
                currency="INR",
            ),
            Card(
                org_id=org.id,
                user_id=carol_user.id,
                department_id=mkt_dept.id,
                nickname="Carol — Events",
                last_four="2002",
                status=CardStatus.ACTIVE,
                daily_limit=Decimal("15000"),
                monthly_limit=Decimal("75000"),
                total_limit=Decimal("0"),
                currency="INR",
            ),
        ]
        for card in cards:
            db.add(card)

        # Commit all structural data before creating transactions
        await db.commit()

        # -------------------------------------------------------- Transactions (M1)
        # Each create_transaction() call commits its own unit of work.
        # Use ADMIN scope so the card-ownership EMPLOYEE check is skipped — we're
        # seeding on behalf of the cardholders.
        now = datetime.now(timezone.utc)
        txn_count = 0

        for card_idx, amount, merchant, category, description, days_ago in DEMO_TRANSACTIONS:
            card = cards[card_idx]
            scope = OrgScope(
                db=db,
                org_id=org.id,
                user_id=card.user_id,   # record as the cardholder's transaction
                role=UserRole.ADMIN,    # ADMIN bypasses EMPLOYEE ownership check
            )
            try:
                await transaction_service.create_transaction(
                    scope,
                    TransactionCreate(
                        card_id=card.id,
                        amount=Decimal(amount),
                        merchant=merchant,
                        category=category,
                        description=description,
                        occurred_at=now - timedelta(days=days_ago),
                    ),
                )
                txn_count += 1
            except Exception as exc:  # noqa: BLE001
                print(f"  WARNING: failed to seed transaction '{merchant}': {exc}")

        # ---------------------------------------------------- Reimbursements (Phase 5)
        # Seed 3 demo reimbursements directly (no service — outside request context)
        demo_reimbs = [
            Reimbursement(
                org_id=org.id,
                user_id=carol_user.id,
                department_id=mkt_dept.id,
                amount=Decimal("1200.00"),
                currency="INR",
                category=SpendCategory.MEALS,
                description="Team lunch — client meeting",
                status=ReimbursementStatus.APPROVED,
                decision_reason="Approved — within meal policy",
                decided_by=admin_user.id,
                decided_at=now - timedelta(days=3),
            ),
            Reimbursement(
                org_id=org.id,
                user_id=bob_user.id,
                department_id=eng_dept.id,
                amount=Decimal("850.00"),
                currency="INR",
                category=SpendCategory.TRAVEL,
                description="Auto-rickshaw to client office",
                status=ReimbursementStatus.SUBMITTED,
            ),
            Reimbursement(
                org_id=org.id,
                user_id=carol_user.id,
                department_id=mkt_dept.id,
                amount=Decimal("15000.00"),
                currency="INR",
                category=SpendCategory.SAAS,
                description="Annual SaaS subscription renewal",
                status=ReimbursementStatus.REJECTED,
                decision_reason="Amount exceeds per-request limit — raise a PO instead",
                decided_by=admin_user.id,
                decided_at=now - timedelta(days=1),
            ),
        ]
        for r in demo_reimbs:
            db.add(r)
        await db.commit()

        print("Seed complete.")
        print(f"  Org:          {org.name} (slug={org.slug})")
        print(f"  Password:     {DEMO_PASSWORD}")
        for email, name, role in DEMO_USERS:
            print(f"  - {role.value:<16} {email}  ({name})")
        print(f"  Departments:  {', '.join(d.name for d in dept_records)}")
        print(f"  Cards:        {len(cards)} seeded")
        print(f"  Transactions: {txn_count} seeded (5 CLEARED, 2 FLAGGED, 1 BLOCKED)")
        print(f"  Reimbursements: {len(demo_reimbs)} seeded (1 APPROVED, 1 SUBMITTED, 1 REJECTED)")


if __name__ == "__main__":
    asyncio.run(run())
