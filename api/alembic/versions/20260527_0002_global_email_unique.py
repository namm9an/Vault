"""make users.email globally unique

Revision ID: 0002_global_email_unique
Revises: 0001_baseline
Create Date: 2026-05-27 00:00:00.000000

The baseline created UNIQUE (org_id, email), scoping uniqueness per org.
Login is by email alone, so that constraint permits two users with the same
email in different orgs, which breaks login lookup.  This migration:

  1. Removes any duplicate emails from the dev DB (keeps oldest row per email).
  2. Drops the per-org composite unique constraint.
  3. Adds a global unique constraint on email.
"""
from typing import Union

from alembic import op

revision: str = "0002_global_email_unique"
down_revision: Union[str, None] = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Purge duplicate emails — keep the oldest account per email address.
    #    On a fresh dev DB this is a no-op; protects against manual signup tests.
    op.execute(
        """
        DELETE FROM users
        WHERE id NOT IN (
            SELECT DISTINCT ON (email) id
            FROM users
            ORDER BY email, created_at ASC
        )
        """
    )

    # 2. Drop the per-org composite unique constraint added in 0001_baseline.
    #    Postgres auto-named it users_org_id_email_key.
    op.execute("ALTER TABLE users DROP CONSTRAINT users_org_id_email_key")

    # 3. Add a global unique constraint so the DB enforces the invariant.
    op.execute("ALTER TABLE users ADD CONSTRAINT uq_users_email UNIQUE (email)")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP CONSTRAINT uq_users_email")
    op.execute("ALTER TABLE users ADD CONSTRAINT users_org_id_email_key UNIQUE (org_id, email)")
