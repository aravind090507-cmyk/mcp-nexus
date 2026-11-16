"""
MCP NEXUS — RELEASE BLOCKER REMEDIATION VERIFICATION SUITE
Validates:
- Workstream A: Production Administrator Credential Security & Idempotent Bootstrap.
- Workstream B: Cross-Worker Emergency Shutdown Synchronization via Central Database.
- Workstream C: Persistent Session Reset & Lifecycle Safety.
"""

import os
import sys
import pytest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.security import verify_password
from app.models.all_models import Base, Organization, User, IntegrationConfig
from app.core.permissions import RoleEnum
from app.mcp.persistent_session import PersistentSessionManager


@pytest.fixture(autouse=True)
def clean_persistent_state():
    """Ensure persistent session manager is clean before and after each test."""
    PersistentSessionManager.test_harness_reset()
    yield
    PersistentSessionManager.test_harness_reset()


# ==============================================================================
# WORKSTREAM A: PRODUCTION ADMINISTRATOR CREDENTIAL SECURITY
# ==============================================================================

def test_production_startup_without_bootstrap_password_raises(tmp_path):
    """Production startup must halt if BOOTSTRAP_ADMIN_PASSWORD is missing on fresh deployment."""
    from app.main import startup_seed
    test_db_path = tmp_path / "test_prod_no_pass.db"
    test_engine = create_engine(f"sqlite:///{test_db_path}")
    Base.metadata.create_all(bind=test_engine)
    TestSessionLocal = sessionmaker(bind=test_engine)

    with patch.object(settings, "ENVIRONMENT", "Production"), \
         patch.object(settings, "BOOTSTRAP_ADMIN_PASSWORD", None), \
         patch("app.main.SessionLocal", TestSessionLocal):
        with pytest.raises(RuntimeError) as exc_info:
            import asyncio
            asyncio.run(startup_seed())
        assert "BOOTSTRAP_ADMIN_PASSWORD is required" in str(exc_info.value)


def test_production_startup_with_valid_bootstrap_password_provisions_admin(tmp_path):
    """Production startup provisions Super Admin with hashed credentials, without seeding demo accounts."""
    from app.main import startup_seed
    test_db_path = tmp_path / "test_prod_bootstrap.db"
    test_engine = create_engine(f"sqlite:///{test_db_path}")
    Base.metadata.create_all(bind=test_engine)
    TestSessionLocal = sessionmaker(bind=test_engine)

    secure_password = "ComplexSecureProdPassword2026!#"
    test_email = "custom.admin@corp.enterprise"

    with patch.object(settings, "ENVIRONMENT", "Production"), \
         patch.object(settings, "BOOTSTRAP_ADMIN_PASSWORD", secure_password), \
         patch.object(settings, "BOOTSTRAP_ADMIN_EMAIL", test_email), \
         patch("app.main.SessionLocal", TestSessionLocal):
        import asyncio
        asyncio.run(startup_seed())

    # Verify database contents
    db = TestSessionLocal()
    try:
        admin = db.query(User).filter(User.role == RoleEnum.SUPER_ADMIN.value).first()
        assert admin is not None
        assert admin.email == test_email
        assert verify_password(secure_password, admin.hashed_password) is True

        # Verify NO demo users were seeded in production
        all_users = db.query(User).all()
        assert len(all_users) == 1, f"Production must only contain the bootstrapped admin, found {len(all_users)}"
        assert all_users[0].email == test_email

        # Verify default demo accounts do NOT exist
        demo_emails = ["admin@mcp-nexus.enterprise", "ops.lead@mcp-nexus.enterprise", "dev.arch@mcp-nexus.enterprise"]
        if test_email != "admin@mcp-nexus.enterprise":
            for demo_email in demo_emails:
                assert db.query(User).filter(User.email == demo_email).first() is None
    finally:
        db.close()


def test_production_startup_idempotence_preserves_existing_password(tmp_path):
    """Subsequent production restarts preserve existing admin credentials and do NOT overwrite them."""
    from app.main import startup_seed
    test_db_path = tmp_path / "test_prod_idempotent.db"
    test_engine = create_engine(f"sqlite:///{test_db_path}")
    Base.metadata.create_all(bind=test_engine)
    TestSessionLocal = sessionmaker(bind=test_engine)

    initial_password = "InitialStrongPassword2026!#"
    new_password_in_env = "DifferentPasswordAttempt2026!#"

    # First run: bootstrap
    with patch.object(settings, "ENVIRONMENT", "Production"), \
         patch.object(settings, "BOOTSTRAP_ADMIN_PASSWORD", initial_password), \
         patch("app.main.SessionLocal", TestSessionLocal):
        import asyncio
        asyncio.run(startup_seed())

    db = TestSessionLocal()
    try:
        admin_first = db.query(User).filter(User.role == RoleEnum.SUPER_ADMIN.value).first()
        original_hash = admin_first.hashed_password
        assert verify_password(initial_password, original_hash) is True
    finally:
        db.close()

    # Second run: restart with different env password
    with patch.object(settings, "ENVIRONMENT", "Production"), \
         patch.object(settings, "BOOTSTRAP_ADMIN_PASSWORD", new_password_in_env), \
         patch("app.main.SessionLocal", TestSessionLocal):
        import asyncio
        asyncio.run(startup_seed())

    # Verify hash is unchanged
    db = TestSessionLocal()
    try:
        admin_second = db.query(User).filter(User.role == RoleEnum.SUPER_ADMIN.value).first()
        assert admin_second.hashed_password == original_hash
        assert verify_password(initial_password, admin_second.hashed_password) is True
        assert verify_password(new_password_in_env, admin_second.hashed_password) is False
    finally:
        db.close()


def test_production_startup_rejects_trivial_or_default_bootstrap_password():
    """Startup validation strictly rejects weak, short, or known default passwords in Production."""
    trivial_passwords = [
        "short",
        "12345678",
        "admin",
        "NexusAdmin@2026",
        "password12345",
        "supersecret123",
        "changeme_now_please"
    ]

    for bad_pw in trivial_passwords:
        with patch.object(settings, "ENVIRONMENT", "Production"), \
             patch.object(settings, "DEBUG", False), \
             patch.object(settings, "BOOTSTRAP_ADMIN_PASSWORD", bad_pw), \
             patch.object(settings, "SECRET_KEY", "A" * 32), \
             patch.object(settings, "DATABASE_URL", "postgresql://user:pass@host:5432/db"), \
             patch.object(settings, "WORKERS", 1):
            with pytest.raises(RuntimeError) as exc_info:
                settings.validate_startup_configuration()
            assert "BOOTSTRAP_ADMIN_PASSWORD" in str(exc_info.value)


# ==============================================================================
# WORKSTREAM B: CROSS-WORKER EMERGENCY SHUTDOWN SYNCHRONIZATION
# ==============================================================================

@pytest.mark.asyncio
async def test_emergency_disable_synchronizes_to_database():
    """emergency_disable() writes an authoritative ENGAGED record to IntegrationConfig."""
    from app.database.session import SessionLocal

    res = await PersistentSessionManager.emergency_disable(
        reason="Security Breach Detected",
        actor_email="security.lead@enterprise.com"
    )
    assert res["emergency_disabled"] is True
    assert res["status"] == "ENGAGED"

    # Verify database record
    db = SessionLocal()
    try:
        record = db.query(IntegrationConfig).filter(
            IntegrationConfig.name == "GLOBAL_EMERGENCY_KILL_SWITCH"
        ).first()
        assert record is not None
        assert record.status == "ENGAGED"
        assert record.system_type == "GOVERNANCE"
        assert record.stats.get("reason") == "Security Breach Detected"
        assert record.stats.get("actor") == "security.lead@enterprise.com"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_cross_worker_discovery_of_emergency_shutdown():
    """A worker that starts with empty local memory detects the active kill switch from the DB."""
    # Worker 1 engages emergency shutdown
    await PersistentSessionManager.emergency_disable(
        reason="Cluster-wide Emergency",
        actor_email="ops@enterprise.com"
    )

    # Worker 2: Simulate another process by resetting local in-memory state only
    PersistentSessionManager._emergency_disabled = False
    PersistentSessionManager._emergency_disabled_at = None
    PersistentSessionManager._emergency_reason = None

    # Worker 2 calls is_emergency_disabled() -> queries DB -> discovers ENGAGED
    is_disabled = PersistentSessionManager.is_emergency_disabled()
    assert is_disabled is True
    assert PersistentSessionManager._emergency_disabled is True
    assert PersistentSessionManager._emergency_reason == "Cluster-wide Emergency"


@pytest.mark.asyncio
async def test_emergency_enable_synchronizes_disengagement_to_database():
    """emergency_enable() writes DISENGAGED to IntegrationConfig and synchronizes across workers."""
    from app.database.session import SessionLocal

    # Engage first
    await PersistentSessionManager.emergency_disable(reason="Prep for enable test")
    assert PersistentSessionManager.is_emergency_disabled() is True

    # Disengage
    res = PersistentSessionManager.emergency_enable(actor_email="admin@enterprise.com")
    assert res["emergency_disabled"] is False
    assert res["status"] == "DISENGAGED"

    # Verify database
    db = SessionLocal()
    try:
        record = db.query(IntegrationConfig).filter(
            IntegrationConfig.name == "GLOBAL_EMERGENCY_KILL_SWITCH"
        ).first()
        assert record is not None
        assert record.status == "DISENGAGED"
        assert record.stats.get("actor") == "admin@enterprise.com"
    finally:
        db.close()

    # Another worker process queries and confirms disengagement
    PersistentSessionManager._emergency_disabled = True  # Worker 2 had it cached
    assert PersistentSessionManager.is_emergency_disabled() is False
    assert PersistentSessionManager._emergency_disabled is False


def test_emergency_disabled_fails_closed_when_database_unreachable():
    """Fail-Closed: If the central database is unreachable, is_emergency_disabled() returns True."""
    # Ensure memory is clean
    PersistentSessionManager._emergency_disabled = False

    # Simulate database connection failure
    with patch("app.database.session.SessionLocal", side_effect=Exception("Database Connection Timeout")):
        is_disabled = PersistentSessionManager.is_emergency_disabled()
        assert is_disabled is True, "Must fail-closed and return True if authoritative store is unreachable"


# ==============================================================================
# WORKSTREAM C: PERSISTENT SESSION RESET & LIFECYCLE SAFETY
# ==============================================================================

@pytest.mark.asyncio
async def test_persistent_session_reset_defaults_to_preserve_emergency():
    """PersistentSessionManager.reset() defaults to clear_emergency=False, preserving emergency shutdown."""
    await PersistentSessionManager.emergency_disable(reason="Operator Halt")
    assert PersistentSessionManager.is_emergency_disabled() is True

    # Calling reset without arguments must preserve emergency state
    PersistentSessionManager.reset()

    assert PersistentSessionManager.is_emergency_disabled() is True
    assert PersistentSessionManager._emergency_disabled is True
    assert PersistentSessionManager._emergency_reason == "Operator Halt"


@pytest.mark.asyncio
async def test_test_harness_reset_clears_emergency_and_database():
    """test_harness_reset() explicitly clears memory state and database record for test isolation."""
    from app.database.session import SessionLocal

    await PersistentSessionManager.emergency_disable(reason="Temporary Test Disablement")
    assert PersistentSessionManager.is_emergency_disabled() is True

    # Call test_harness_reset()
    PersistentSessionManager.test_harness_reset()

    assert PersistentSessionManager.is_emergency_disabled() is False
    assert PersistentSessionManager._emergency_disabled is False
    assert PersistentSessionManager._emergency_reason is None

    # Verify DB record was cleaned up
    db = SessionLocal()
    try:
        record = db.query(IntegrationConfig).filter(
            IntegrationConfig.name == "GLOBAL_EMERGENCY_KILL_SWITCH"
        ).first()
        assert record is None
    finally:
        db.close()


@pytest.mark.asyncio
async def test_get_session_rejects_when_database_emergency_engaged():
    """get_session() raises RuntimeError when emergency kill switch is engaged in DB."""
    await PersistentSessionManager.emergency_disable(reason="Active Emergency")

    # Clear only local memory flag to test DB-backed rejection
    PersistentSessionManager._emergency_disabled = False

    with pytest.raises(RuntimeError) as exc_info:
        PersistentSessionManager.get_session(
            server_id="test-srv-blocked",
            server_name="Blocked Server",
            command="python"
        )
    assert "Global emergency kill switch is engaged" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_existing_session_returns_none_when_emergency_engaged():
    """get_existing_session() returns None when emergency kill switch is engaged."""
    await PersistentSessionManager.emergency_disable(reason="Active Emergency")

    # Clear only local memory flag to test DB-backed rejection
    PersistentSessionManager._emergency_disabled = False

    result = PersistentSessionManager.get_existing_session("any-server-id")
    assert result is None
