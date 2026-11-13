"""
MCP NEXUS — PHASE 15D.4.1 PRODUCTION HARDENING TEST SUITE

Tests the production environment hardening requirements:
1. Production configuration fail-closed validation (insecure SECRET_KEY, DEBUG mode, invalid environments).
2. Database fallback prevention (rejection of mcp_nexus.db and staging databases in production).
3. Multi-worker SQLite rejection (WORKERS / WEB_CONCURRENCY > 1 cannot use SQLite).
4. Persistent session safety (disabled by default, production activation rejected, allowlist enforcement).
5. Emergency shutdown prevention of accidental persistent session re-activation.
6. Tenant isolation and administrative RBAC persistence.
"""

import os
import sys
import pytest
from unittest.mock import patch

from app.core.config import Settings, _resolve_and_load_environment, settings
from app.mcp.persistent_session import PersistentSessionManager
from app.services.mcp_manager import MCPManager
from app.models.all_models import MCPServer, User
from app.services.deployment_governance import DeploymentGovernanceService, DeploymentState
from app.database.session import SessionLocal


# ==============================================================================
# 1. PRODUCTION CONFIGURATION FAIL-CLOSED VALIDATION
# ==============================================================================

def test_production_insecure_secret_key_rejected(monkeypatch):
    """Production must reject default, trivial, or short secret keys."""
    monkeypatch.setenv("ENVIRONMENT", "Production")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/mcp_prod")
    monkeypatch.setenv("DEBUG", "False")

    # Empty secret key
    monkeypatch.setenv("SECRET_KEY", "")
    with pytest.raises(RuntimeError) as exc:
        _resolve_and_load_environment()
    assert "Production SECRET_KEY must be a valid" in str(exc.value)

    # Insecure default keyword in key
    monkeypatch.setenv("SECRET_KEY", "mcp-nexus-enterprise-vault-supersecret-key-2026-xyz")
    with pytest.raises(RuntimeError) as exc:
        _resolve_and_load_environment()
    assert "Production SECRET_KEY must be a valid" in str(exc.value)

    # Short secret key (< 32 chars)
    monkeypatch.setenv("SECRET_KEY", "short-secret-key-12345")
    with pytest.raises(RuntimeError) as exc:
        _resolve_and_load_environment()
    assert "Production SECRET_KEY must be a valid" in str(exc.value)


def test_production_debug_mode_strictly_rejected(monkeypatch):
    """Production configuration must reject DEBUG=True to prevent info leakage."""
    monkeypatch.setenv("ENVIRONMENT", "Production")
    monkeypatch.setenv("SECRET_KEY", "c" * 32 + "-cryptographically-secure-key-999")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/mcp_prod")
    monkeypatch.setenv("DEBUG", "True")

    with pytest.raises(RuntimeError) as exc:
        _resolve_and_load_environment()
    assert "DEBUG mode cannot be enabled in Production" in str(exc.value)


def test_production_wildcard_persistent_allowlist_rejected(monkeypatch):
    """Production must reject wildcard PERSISTENT_MCP_SERVERS='*'."""
    monkeypatch.setenv("ENVIRONMENT", "Production")
    monkeypatch.setenv("SECRET_KEY", "c" * 32 + "-cryptographically-secure-key-999")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/mcp_prod")
    monkeypatch.setenv("DEBUG", "False")
    monkeypatch.setenv("PERSISTENT_MCP_SERVERS", "*")

    with pytest.raises(RuntimeError) as exc:
        _resolve_and_load_environment()
    assert "Wildcard PERSISTENT_MCP_SERVERS='*' is strictly forbidden in Production" in str(exc.value)


# ==============================================================================
# 2. DATABASE FALLBACK PREVENTION & MULTI-WORKER REJECTION
# ==============================================================================

def test_production_sqlite_rejected(monkeypatch):
    """Production environment must strictly reject SQLite database URLs."""
    monkeypatch.setenv("ENVIRONMENT", "Production")
    monkeypatch.setenv("SECRET_KEY", "c" * 32 + "-cryptographically-secure-key-999")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./prod_test.db")
    monkeypatch.setenv("DEBUG", "False")

    with pytest.raises(RuntimeError) as exc:
        _resolve_and_load_environment()
    assert "cannot use SQLite" in str(exc.value)


def test_production_development_db_fallback_rejected(monkeypatch):
    """Production must reject URLs pointing to development mcp_nexus.db or staging databases."""
    monkeypatch.setenv("ENVIRONMENT", "Production")
    monkeypatch.setenv("SECRET_KEY", "c" * 32 + "-cryptographically-secure-key-999")
    monkeypatch.setenv("DEBUG", "False")

    # Erroneous dev DB
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/mcp_nexus.db")
    with pytest.raises(RuntimeError) as exc:
        _resolve_and_load_environment()
    assert "cannot use development or staging databases" in str(exc.value)

    # Erroneous staging DB
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/mcp_nexus_staging")
    with pytest.raises(RuntimeError) as exc:
        _resolve_and_load_environment()
    assert "cannot use development or staging databases" in str(exc.value)


def test_multi_worker_sqlite_rejected(monkeypatch):
    """Multi-worker deployment (WORKERS > 1 or WEB_CONCURRENCY > 1) cannot use SQLite."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")

    # WORKERS > 1
    monkeypatch.setenv("WORKERS", "4")
    with pytest.raises(RuntimeError) as exc:
        _resolve_and_load_environment()
    assert "Multi-worker deployment (WORKERS=4) cannot use SQLite" in str(exc.value)

    # WEB_CONCURRENCY > 1
    monkeypatch.delenv("WORKERS", raising=False)
    monkeypatch.setenv("WEB_CONCURRENCY", "2")
    with pytest.raises(RuntimeError) as exc:
        _resolve_and_load_environment()
    assert "Multi-worker deployment (WORKERS=2) cannot use SQLite" in str(exc.value)


def test_validate_startup_configuration_multi_worker_sqlite():
    """Settings.validate_startup_configuration() fails fast on multi-worker SQLite."""
    test_settings = Settings()
    test_settings.WORKERS = 4
    test_settings.DATABASE_URL = "sqlite:///./test_mw.db"

    with pytest.raises(RuntimeError) as exc:
        test_settings.validate_startup_configuration()
    assert "Multi-worker deployment (WORKERS=4) cannot use SQLite" in str(exc.value)


# ==============================================================================
# 3. PERSISTENT SESSION SAFETY IN PRODUCTION
# ==============================================================================

def test_production_persistent_session_activation_rejected(monkeypatch):
    """Production must strictly reject ENABLE_PERSISTENT_MCP_SESSIONS=true in Phase 15D.4.1."""
    monkeypatch.setenv("ENVIRONMENT", "Production")
    monkeypatch.setenv("SECRET_KEY", "c" * 32 + "-cryptographically-secure-key-999")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/mcp_prod")
    monkeypatch.setenv("DEBUG", "False")
    monkeypatch.setenv("ENABLE_PERSISTENT_MCP_SESSIONS", "true")

    with pytest.raises(RuntimeError) as exc:
        _resolve_and_load_environment()
    assert "Persistent MCP sessions are not authorized in Production" in str(exc.value)


def test_persistent_sessions_default_disabled(monkeypatch):
    """Default configuration must have persistent sessions disabled."""
    fresh_settings = Settings()
    assert fresh_settings.ENABLE_PERSISTENT_MCP_SESSIONS is False

    monkeypatch.delenv("PERSISTENT_MCP_SERVERS", raising=False)
    unconfigured_settings = Settings()
    assert unconfigured_settings.PERSISTENT_MCP_SERVERS == ""
    assert unconfigured_settings.ENABLE_PERSISTENT_MCP_SESSIONS is False


# ==============================================================================
# 4. EMERGENCY SHUTDOWN PERSISTENT SESSION RE-ACTIVATION PREVENTION
# ==============================================================================

def test_emergency_shutdown_prevents_get_session():
    """When emergency shutdown is engaged, get_session() must raise RuntimeError and not create session."""
    PersistentSessionManager._emergency_disabled = True
    try:
        with pytest.raises(RuntimeError) as exc:
            PersistentSessionManager.get_session("srv-blocked", "Blocked Server", "echo", ["arg"])
        assert "Global emergency kill switch is engaged" in str(exc.value)
        assert PersistentSessionManager.get_existing_session("srv-blocked") is None
    finally:
        PersistentSessionManager._emergency_disabled = False


@pytest.mark.asyncio
async def test_emergency_shutdown_prevents_execute_tool():
    """When emergency shutdown is engaged, execute_tool() must raise RuntimeError without executing."""
    PersistentSessionManager._emergency_disabled = True
    try:
        with pytest.raises(RuntimeError) as exc:
            await PersistentSessionManager.execute_tool(
                "srv-blocked", "Blocked Server", "echo", ["arg"], {}, None, "some_tool", {}
            )
        assert "Global emergency kill switch is engaged" in str(exc.value)
    finally:
        PersistentSessionManager._emergency_disabled = False


# ==============================================================================
# 5. TENANT ISOLATION & ADMINISTRATIVE RBAC PERSISTENCE
# ==============================================================================

def test_tenant_isolation_preserved():
    """Verify tenant boundary enforcement in deployment state transitions."""
    db = SessionLocal()
    try:
        server = db.query(MCPServer).first()
        cross_tenant_actor = User(
            id="usr-cross-org",
            email="other@corp.io",
            full_name="Other User",
            role="ADMIN",
            organization_id="org-foreign-999"
        )
        ok, msg, _ = DeploymentGovernanceService.transition_state(
            db, server, DeploymentState.DISABLED, cross_tenant_actor, "Cross tenant test"
        )
        assert ok is False
        assert "Cannot alter deployment state of another organization" in msg
    finally:
        db.close()


def test_administrative_rbac_preserved():
    """Verify unauthorized role cannot perform deployment state transitions."""
    db = SessionLocal()
    try:
        server = db.query(MCPServer).first()
        developer = User(
            id="usr-dev",
            email="dev@mcp-nexus.enterprise",
            full_name="Developer",
            role="DEVELOPER",
            organization_id=server.organization_id
        )
        ok, msg, _ = DeploymentGovernanceService.transition_state(
            db, server, DeploymentState.DISABLED, developer, "Unauthorized attempt"
        )
        assert ok is False
        assert "Access denied: Role 'DEVELOPER' is not authorized" in msg
    finally:
        db.close()
