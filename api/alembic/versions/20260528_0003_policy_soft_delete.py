"""add deleted_at to policies for soft-delete

Revision ID: 0003_policy_soft_delete
Revises: 0002_global_email_unique
Create Date: 2026-05-28 00:00:00.000000

Hard-deleting a policy row NULLs out TransactionPolicyResult.matched_policy_id
(FK ondelete=SET NULL) and destroys the audit trail.  Adding a nullable
deleted_at column lets us soft-delete: set is_active=False + deleted_at=NOW()
so FK references survive and the policy_check job naturally excludes them
via the existing is_active filter.

list_policies and get_policy are updated to filter deleted_at IS NULL so
deleted policies are invisible to API consumers.
"""
from alembic import op


# revision identifiers used by Alembic
revision = "0003_policy_soft_delete"
down_revision = "0002_global_email_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE policies ADD COLUMN deleted_at TIMESTAMPTZ NULL"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE policies DROP COLUMN IF EXISTS deleted_at"
    )
