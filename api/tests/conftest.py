"""Pytest configuration and shared fixtures for Vault tests.

Env vars are set at the very top — before any app-level imports — because
api.db.base calls get_settings() at module import time (to build the engine).
Tests mock the DB session, so the DATABASE_URL value is never actually used.
"""
import os

# Minimal dummy values so pydantic-settings validates without a real .env file.
# Nothing here touches Postgres or Redis — all DB calls in these tests are mocked.
os.environ.setdefault("APP_SECRET_KEY", "test-only-secret-key-32-chars-minimum-padding")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/testdb")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ARQ_REDIS_URL", "redis://localhost:6379/1")

import pytest  # noqa: E402


@pytest.fixture
def admin_token_payload(acme_org_id, admin_user_id):
    return {
        "sub": str(admin_user_id),
        "org_id": str(acme_org_id),
        "role": "ADMIN",
        "type": "access",
    }
