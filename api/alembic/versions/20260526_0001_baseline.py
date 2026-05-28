"""baseline schema

Revision ID: 0001_baseline
Revises:
Create Date: 2026-05-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels = None
depends_on = None


def _run(sql: str) -> None:
    """Split a multi-statement SQL block and execute each piece.

    asyncpg cannot run multiple statements per execute(). We split on
    semicolons that end a line, which is robust for our DDL (CREATE FUNCTION
    bodies are wrapped in $$ ... $$ so internal semicolons don't end lines).
    """
    import re
    statements = []
    buf = []
    in_dollar = False
    for line in sql.splitlines():
        if "$$" in line:
            in_dollar = not in_dollar if line.count("$$") % 2 else in_dollar
        buf.append(line)
        stripped = line.rstrip()
        if stripped.endswith(";") and not in_dollar:
            statements.append("\n".join(buf).strip())
            buf = []
    if buf and "".join(buf).strip():
        statements.append("\n".join(buf).strip())
    for stmt in statements:
        if stmt:
            op.execute(stmt)


def upgrade() -> None:
    _run(
        """
        CREATE EXTENSION IF NOT EXISTS "pgcrypto";
        CREATE EXTENSION IF NOT EXISTS "citext";

        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
          NEW.updated_at = NOW();
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TYPE user_role AS ENUM ('ADMIN', 'FINANCE_MANAGER', 'EMPLOYEE');
        CREATE TYPE card_status AS ENUM ('ACTIVE', 'FROZEN', 'CANCELLED');
        CREATE TYPE transaction_state AS ENUM (
          'INITIATED','POLICY_CHECKED','APPROVED','FLAGGED','BLOCKED','CLEARED','SETTLED'
        );
        CREATE TYPE policy_verdict AS ENUM ('APPROVED','FLAGGED','BLOCKED');
        CREATE TYPE spend_category AS ENUM (
          'TRAVEL','MEALS','SAAS','OFFICE','MARKETING','HARDWARE','PROFESSIONAL_SERVICES','OTHER'
        );
        CREATE TYPE receipt_status AS ENUM (
          'PENDING_UPLOAD','PROCESSING','COMPLETED','NEEDS_REVIEW','FAILED'
        );
        CREATE TYPE reimbursement_status AS ENUM (
          'SUBMITTED','POLICY_CHECKED','APPROVED','REJECTED','PAID'
        );
        CREATE TYPE notification_type AS ENUM (
          'POLICY_FLAGGED','POLICY_BLOCKED','APPROVAL_REQUESTED','APPROVAL_GRANTED',
          'APPROVAL_REJECTED','BUDGET_THRESHOLD','DIGEST_READY','RECEIPT_REVIEW_NEEDED'
        );
        CREATE TYPE digest_status AS ENUM ('PENDING','COMPLETED','FAILED');

        CREATE TABLE organizations (
          id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          name          TEXT NOT NULL,
          slug          CITEXT NOT NULL UNIQUE,
          base_currency CHAR(3) NOT NULL DEFAULT 'INR',
          created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TRIGGER organizations_set_updated_at BEFORE UPDATE ON organizations
          FOR EACH ROW EXECUTE FUNCTION set_updated_at();

        CREATE TABLE users (
          id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          org_id        UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
          email         CITEXT NOT NULL,
          password_hash TEXT NOT NULL,
          full_name     TEXT NOT NULL,
          role          user_role NOT NULL DEFAULT 'EMPLOYEE',
          department_id UUID NULL,
          is_active     BOOLEAN NOT NULL DEFAULT TRUE,
          last_login_at TIMESTAMPTZ NULL,
          created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          UNIQUE (org_id, email)
        );
        CREATE INDEX idx_users_org ON users(org_id);
        CREATE INDEX idx_users_role ON users(org_id, role);
        CREATE INDEX idx_users_department ON users(department_id);
        CREATE TRIGGER users_set_updated_at BEFORE UPDATE ON users
          FOR EACH ROW EXECUTE FUNCTION set_updated_at();

        CREATE TABLE departments (
          id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          org_id              UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
          name                TEXT NOT NULL,
          monthly_budget      NUMERIC(14,2) NOT NULL DEFAULT 0,
          budget_currency     CHAR(3) NOT NULL DEFAULT 'INR',
          alert_threshold_pct INTEGER NOT NULL DEFAULT 80
                              CHECK (alert_threshold_pct BETWEEN 1 AND 100),
          manager_id          UUID NULL REFERENCES users(id) ON DELETE SET NULL,
          created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          UNIQUE (org_id, name)
        );
        CREATE INDEX idx_departments_org ON departments(org_id);
        CREATE INDEX idx_departments_manager ON departments(manager_id);
        CREATE TRIGGER departments_set_updated_at BEFORE UPDATE ON departments
          FOR EACH ROW EXECUTE FUNCTION set_updated_at();

        ALTER TABLE users
          ADD CONSTRAINT fk_users_department
          FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE SET NULL;

        CREATE TABLE cards (
          id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          org_id                UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
          user_id               UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
          department_id         UUID NULL REFERENCES departments(id) ON DELETE SET NULL,
          nickname              TEXT NOT NULL,
          last_four             CHAR(4) NOT NULL,
          status                card_status NOT NULL DEFAULT 'ACTIVE',
          daily_limit           NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (daily_limit >= 0),
          monthly_limit         NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (monthly_limit >= 0),
          total_limit           NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (total_limit >= 0),
          category_restrictions spend_category[] NOT NULL DEFAULT '{}',
          currency              CHAR(3) NOT NULL DEFAULT 'INR',
          frozen_at             TIMESTAMPTZ NULL,
          cancelled_at          TIMESTAMPTZ NULL,
          created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX idx_cards_org ON cards(org_id);
        CREATE INDEX idx_cards_user ON cards(user_id);
        CREATE INDEX idx_cards_status ON cards(org_id, status);
        CREATE INDEX idx_cards_department ON cards(department_id);
        CREATE TRIGGER cards_set_updated_at BEFORE UPDATE ON cards
          FOR EACH ROW EXECUTE FUNCTION set_updated_at();

        CREATE TABLE policies (
          id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          org_id      UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
          text        TEXT NOT NULL,
          is_active   BOOLEAN NOT NULL DEFAULT TRUE,
          created_by  UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
          created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX idx_policies_org_active ON policies(org_id, is_active);
        CREATE INDEX idx_policies_created_by ON policies(created_by);
        CREATE TRIGGER policies_set_updated_at BEFORE UPDATE ON policies
          FOR EACH ROW EXECUTE FUNCTION set_updated_at();

        CREATE TABLE transactions (
          id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          org_id        UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
          user_id       UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
          card_id       UUID NOT NULL REFERENCES cards(id) ON DELETE RESTRICT,
          department_id UUID NULL REFERENCES departments(id) ON DELETE SET NULL,
          amount        NUMERIC(14,2) NOT NULL CHECK (amount > 0),
          currency      CHAR(3) NOT NULL DEFAULT 'INR',
          merchant      TEXT NOT NULL,
          category      spend_category NOT NULL DEFAULT 'OTHER',
          state         transaction_state NOT NULL DEFAULT 'INITIATED',
          description   TEXT NULL,
          occurred_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          receipt_id    UUID NULL,
          created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX idx_txn_org_occurred ON transactions(org_id, occurred_at DESC);
        CREATE INDEX idx_txn_user ON transactions(user_id);
        CREATE INDEX idx_txn_card ON transactions(card_id);
        CREATE INDEX idx_txn_dept ON transactions(department_id);
        CREATE INDEX idx_txn_state ON transactions(org_id, state);
        CREATE INDEX idx_txn_category ON transactions(org_id, category);
        CREATE INDEX idx_txn_merchant ON transactions(org_id, merchant);
        CREATE TRIGGER transactions_set_updated_at BEFORE UPDATE ON transactions
          FOR EACH ROW EXECUTE FUNCTION set_updated_at();

        CREATE TABLE transaction_events (
          id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          transaction_id      UUID NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
          org_id              UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
          from_state          transaction_state NULL,
          to_state            transaction_state NOT NULL,
          triggered_by_user   UUID NULL REFERENCES users(id) ON DELETE SET NULL,
          triggered_by_system BOOLEAN NOT NULL DEFAULT FALSE,
          reason              TEXT NULL,
          metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,
          created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          CHECK (
            (triggered_by_user IS NOT NULL AND triggered_by_system = FALSE)
            OR
            (triggered_by_user IS NULL AND triggered_by_system = TRUE)
          )
        );
        CREATE INDEX idx_txn_events_txn ON transaction_events(transaction_id, created_at);
        CREATE INDEX idx_txn_events_org ON transaction_events(org_id, created_at DESC);

        CREATE TABLE transaction_policy_results (
          id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          org_id                      UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
          transaction_id              UUID NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
          verdict                     policy_verdict NOT NULL,
          reason                      TEXT NOT NULL,
          policy_matched              TEXT NULL,
          matched_policy_id           UUID NULL REFERENCES policies(id) ON DELETE SET NULL,
          requires_approval_from_role user_role NULL,
          raw_llm_response            JSONB NOT NULL,
          llm_model                   TEXT NOT NULL,
          llm_latency_ms              INTEGER NULL,
          created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX idx_tpr_txn ON transaction_policy_results(transaction_id);
        CREATE INDEX idx_tpr_org_verdict ON transaction_policy_results(org_id, verdict);
        CREATE INDEX idx_tpr_policy ON transaction_policy_results(matched_policy_id);

        CREATE TABLE receipts (
          id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          org_id            UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
          uploaded_by       UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
          transaction_id    UUID NULL REFERENCES transactions(id) ON DELETE SET NULL,
          reimbursement_id  UUID NULL,
          object_key        TEXT NOT NULL,
          content_type      TEXT NOT NULL,
          byte_size         BIGINT NULL,
          status            receipt_status NOT NULL DEFAULT 'PENDING_UPLOAD',
          extracted_data    JSONB NULL,
          confidence        NUMERIC(4,3) NULL CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
          llm_error         TEXT NULL,
          created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX idx_receipts_org ON receipts(org_id, created_at DESC);
        CREATE INDEX idx_receipts_txn ON receipts(transaction_id);
        CREATE INDEX idx_receipts_reimb ON receipts(reimbursement_id);
        CREATE INDEX idx_receipts_status ON receipts(org_id, status);
        CREATE TRIGGER receipts_set_updated_at BEFORE UPDATE ON receipts
          FOR EACH ROW EXECUTE FUNCTION set_updated_at();

        ALTER TABLE transactions
          ADD CONSTRAINT fk_transactions_receipt
          FOREIGN KEY (receipt_id) REFERENCES receipts(id) ON DELETE SET NULL;

        CREATE TABLE reimbursements (
          id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          org_id          UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
          user_id         UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
          department_id   UUID NULL REFERENCES departments(id) ON DELETE SET NULL,
          amount          NUMERIC(14,2) NOT NULL CHECK (amount > 0),
          currency        CHAR(3) NOT NULL DEFAULT 'INR',
          category        spend_category NOT NULL DEFAULT 'OTHER',
          description     TEXT NOT NULL,
          receipt_id      UUID NULL REFERENCES receipts(id) ON DELETE SET NULL,
          status          reimbursement_status NOT NULL DEFAULT 'SUBMITTED',
          decision_reason TEXT NULL,
          decided_by      UUID NULL REFERENCES users(id) ON DELETE SET NULL,
          decided_at      TIMESTAMPTZ NULL,
          paid_at         TIMESTAMPTZ NULL,
          created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX idx_reimb_org_status ON reimbursements(org_id, status);
        CREATE INDEX idx_reimb_user ON reimbursements(user_id);
        CREATE INDEX idx_reimb_decided_by ON reimbursements(decided_by);
        CREATE TRIGGER reimbursements_set_updated_at BEFORE UPDATE ON reimbursements
          FOR EACH ROW EXECUTE FUNCTION set_updated_at();

        ALTER TABLE receipts
          ADD CONSTRAINT fk_receipts_reimbursement
          FOREIGN KEY (reimbursement_id) REFERENCES reimbursements(id) ON DELETE SET NULL;

        CREATE TABLE digests (
          id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          org_id              UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
          period_start        DATE NOT NULL,
          period_end          DATE NOT NULL,
          status              digest_status NOT NULL DEFAULT 'PENDING',
          headline            TEXT NULL,
          body                TEXT NULL,
          top_recommendations JSONB NULL,
          flagged_items       JSONB NULL,
          aggregated_input    JSONB NOT NULL,
          raw_llm_response    JSONB NULL,
          llm_error           TEXT NULL,
          created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          UNIQUE (org_id, period_start, period_end)
        );
        CREATE INDEX idx_digests_org_period ON digests(org_id, period_end DESC);
        CREATE TRIGGER digests_set_updated_at BEFORE UPDATE ON digests
          FOR EACH ROW EXECUTE FUNCTION set_updated_at();

        CREATE TABLE notifications (
          id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          org_id      UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
          user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          type        notification_type NOT NULL,
          title       TEXT NOT NULL,
          body        TEXT NOT NULL,
          link        TEXT NULL,
          payload     JSONB NOT NULL DEFAULT '{}'::jsonb,
          read_at     TIMESTAMPTZ NULL,
          created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX idx_notif_user_unread ON notifications(user_id, read_at) WHERE read_at IS NULL;
        CREATE INDEX idx_notif_user_created ON notifications(user_id, created_at DESC);
        CREATE INDEX idx_notif_org ON notifications(org_id);
        CREATE TRIGGER notifications_set_updated_at BEFORE UPDATE ON notifications
          FOR EACH ROW EXECUTE FUNCTION set_updated_at();

        CREATE TABLE refresh_tokens (
          id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          token_hash  TEXT NOT NULL UNIQUE,
          expires_at  TIMESTAMPTZ NOT NULL,
          revoked_at  TIMESTAMPTZ NULL,
          user_agent  TEXT NULL,
          ip          INET NULL,
          created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX idx_refresh_user ON refresh_tokens(user_id);
        CREATE INDEX idx_refresh_expires ON refresh_tokens(expires_at);

        CREATE TABLE audit_log (
          id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          org_id        UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
          actor_user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
          action        TEXT NOT NULL,
          entity_type   TEXT NOT NULL,
          entity_id     UUID NULL,
          metadata      JSONB NOT NULL DEFAULT '{}'::jsonb,
          created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX idx_audit_org_created ON audit_log(org_id, created_at DESC);
        CREATE INDEX idx_audit_entity ON audit_log(entity_type, entity_id);
        CREATE INDEX idx_audit_actor ON audit_log(actor_user_id);
        """
    )


def downgrade() -> None:
    _run(
        """
        DROP TABLE IF EXISTS audit_log CASCADE;
        DROP TABLE IF EXISTS refresh_tokens CASCADE;
        DROP TABLE IF EXISTS notifications CASCADE;
        DROP TABLE IF EXISTS digests CASCADE;
        DROP TABLE IF EXISTS reimbursements CASCADE;
        DROP TABLE IF EXISTS receipts CASCADE;
        DROP TABLE IF EXISTS transaction_policy_results CASCADE;
        DROP TABLE IF EXISTS transaction_events CASCADE;
        DROP TABLE IF EXISTS transactions CASCADE;
        DROP TABLE IF EXISTS policies CASCADE;
        DROP TABLE IF EXISTS cards CASCADE;
        DROP TABLE IF EXISTS departments CASCADE;
        DROP TABLE IF EXISTS users CASCADE;
        DROP TABLE IF EXISTS organizations CASCADE;
        DROP TYPE IF EXISTS digest_status;
        DROP TYPE IF EXISTS notification_type;
        DROP TYPE IF EXISTS reimbursement_status;
        DROP TYPE IF EXISTS receipt_status;
        DROP TYPE IF EXISTS spend_category;
        DROP TYPE IF EXISTS policy_verdict;
        DROP TYPE IF EXISTS transaction_state;
        DROP TYPE IF EXISTS card_status;
        DROP TYPE IF EXISTS user_role;
        DROP FUNCTION IF EXISTS set_updated_at;
        """
    )
