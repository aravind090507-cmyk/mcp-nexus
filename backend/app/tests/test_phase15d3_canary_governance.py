"""
MCP NEXUS — PHASE 15D.3 TEST SUITE
Production Canary Readiness & Deployment Governance:
Comprehensive verification of Environment Isolation, Canary Eligibility, Deployment State Governance,
Legacy Fallback, Tenant Defense, Observability Telemetry, and Acceptance Thresholds.
"""

import sys
import os
import asyncio
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from app.main import app
from app.core.config import settings, _resolve_and_load_environment
from app.database.session import SessionLocal
from app.models.all_models import MCPServer, MCPTool, User, Organization
from app.services.mcp_manager import MCPManager
from app.services.deployment_governance import DeploymentGovernanceService, DeploymentState
from app.services.canary_governance import CanaryGovernanceService, CanaryEligibilityDecision
from app.services.observability_service import ObservabilityService
from app.mcp.persistent_session import PersistentSessionManager
from app.mcp.client import MCPConnectionManager
from app.core.permissions import RoleEnum


@pytest.fixture(autouse=True)
def reset_governance_state():
    """Ensures a clean state before and after each test."""
    PersistentSessionManager.emergency_enable()
    ObservabilityService.reset()
    orig_env = settings.ENVIRONMENT
    orig_persistent = settings.ENABLE_PERSISTENT_MCP_SESSIONS
    orig_servers = settings.PERSISTENT_MCP_SERVERS
    yield
    settings.ENVIRONMENT = orig_env
    settings.ENABLE_PERSISTENT_MCP_SESSIONS = orig_persistent
    settings.PERSISTENT_MCP_SERVERS = orig_servers
    PersistentSessionManager.emergency_enable()
    ObservabilityService.reset()
    db = SessionLocal()
    try:
        for s in db.query(MCPServer).all():
            s.is_enabled = True
            s.status = "HEALTHY"
            s.env_vars = {}
        db.commit()
    finally:
        db.close()


# ==============================================================================
# 1. ENVIRONMENT ISOLATION & FAIL-CLOSED STARTUP TESTS (TASK B)
# ==============================================================================

def test_env_isolation_staging_requires_env_file():
    """Staging must fail-fast if .env.staging is absent."""
    with patch.dict(os.environ, {"ENVIRONMENT": "Staging"}):
        with patch("os.path.isfile", return_value=False):
            with pytest.raises(RuntimeError) as exc_info:
                _resolve_and_load_environment()
            assert "could not be located in search paths" in str(exc_info.value)


def test_env_isolation_staging_rejects_development_db():
    """Staging must fail-fast if DATABASE_URL physically points to mcp_nexus.db."""
    with patch.dict(os.environ, {
        "ENVIRONMENT": "Staging",
        "DATABASE_URL": "sqlite:///./mcp_nexus.db"
    }):
        with patch("os.path.isfile", return_value=True):
            with pytest.raises(RuntimeError) as exc_info:
                _resolve_and_load_environment()
            assert "Staging environment DATABASE_URL is misconfigured" in str(exc_info.value)


def test_env_isolation_production_requires_strong_secrets():
    """Production startup must fail-fast if SECRET_KEY is insecure or default."""
    with patch.dict(os.environ, {
        "ENVIRONMENT": "Production",
        "SECRET_KEY": "supersecret-default-key-xyz",
        "DATABASE_URL": "postgresql://user:pass@prod-db:5432/mcp_prod"
    }):
        with pytest.raises(RuntimeError) as exc_info:
            _resolve_and_load_environment()
        assert "Production SECRET_KEY must be a valid, cryptographically secure" in str(exc_info.value)


def test_env_isolation_production_rejects_sqlite():
    """Production startup must fail-fast if SQLite database is configured."""
    with patch.dict(os.environ, {
        "ENVIRONMENT": "Production",
        "SECRET_KEY": "a" * 48,
        "DATABASE_URL": "sqlite:///./production_mcp.db"
    }):
        with pytest.raises(RuntimeError) as exc_info:
            _resolve_and_load_environment()
        assert "Production environment cannot use SQLite database" in str(exc_info.value)


def test_env_isolation_production_rejects_wildcard_persistent_servers():
    """Production startup must fail-fast if wildcard persistent session allowlist is specified."""
    with patch.dict(os.environ, {
        "ENVIRONMENT": "Production",
        "SECRET_KEY": "b" * 48,
        "DATABASE_URL": "postgresql://user:pass@prod-db:5432/mcp_prod",
        "PERSISTENT_MCP_SERVERS": "*"
    }):
        with pytest.raises(RuntimeError) as exc_info:
            _resolve_and_load_environment()
        assert "Wildcard PERSISTENT_MCP_SERVERS='*' is strictly forbidden in Production" in str(exc_info.value)


def test_env_isolation_invalid_environment_name_fails_closed():
    """Unknown or ambiguous environment names must fail-closed."""
    with patch.dict(os.environ, {"ENVIRONMENT": "InvalidOrAmbiguous"}):
        with pytest.raises(RuntimeError) as exc_info:
            _resolve_and_load_environment()
        assert "Invalid or ambiguous ENVIRONMENT" in str(exc_info.value)


# ==============================================================================
# 2. CANARY ELIGIBILITY & ALLOWLIST EVALUATION TESTS (TASK C)
# ==============================================================================

def test_canary_eligibility_global_flag_disabled():
    """When ENABLE_PERSISTENT_MCP_SESSIONS is False, server is ineligible."""
    db = SessionLocal()
    try:
        server = db.query(MCPServer).first()
        settings.ENABLE_PERSISTENT_MCP_SESSIONS = False
        decision = CanaryGovernanceService.evaluate_server_canary_eligibility(db, server)
        assert decision.is_eligible is False
        assert "GLOBAL_FLAG_DISABLED" in decision.details.get("gate", "")
    finally:
        db.close()


def test_canary_eligibility_allowlist_empty_rejects_all():
    """When PERSISTENT_MCP_SERVERS is empty, all servers are ineligible."""
    db = SessionLocal()
    try:
        server = db.query(MCPServer).first()
        settings.ENABLE_PERSISTENT_MCP_SESSIONS = True
        settings.PERSISTENT_MCP_SERVERS = ""
        decision = CanaryGovernanceService.evaluate_server_canary_eligibility(db, server)
        assert decision.is_eligible is False
        assert "ALLOWLIST_EMPTY" in decision.details.get("gate", "")
    finally:
        db.close()


def test_canary_eligibility_wildcard_forbidden_in_staging():
    """Wildcard allowlist '*' is strictly rejected in Staging."""
    db = SessionLocal()
    try:
        server = db.query(MCPServer).first()
        settings.ENABLE_PERSISTENT_MCP_SESSIONS = True
        settings.PERSISTENT_MCP_SERVERS = "*"
        settings.ENVIRONMENT = "Staging"
        decision = CanaryGovernanceService.evaluate_server_canary_eligibility(db, server)
        assert decision.is_eligible is False
        assert "WILDCARD_ALLOWLIST_FORBIDDEN" in decision.details.get("gate", "")
    finally:
        db.close()


def test_canary_eligibility_disabled_server_rejected():
    """Administratively disabled server is ineligible."""
    db = SessionLocal()
    try:
        server = db.query(MCPServer).first()
        orig_enabled = server.is_enabled
        server.is_enabled = False
        settings.ENABLE_PERSISTENT_MCP_SESSIONS = True
        settings.PERSISTENT_MCP_SERVERS = server.identifier

        decision = CanaryGovernanceService.evaluate_server_canary_eligibility(db, server)
        assert decision.is_eligible is False
        assert "SERVER_DISABLED" in decision.details.get("gate", "")
        server.is_enabled = orig_enabled
    finally:
        db.close()


def test_canary_eligibility_cross_tenant_rejected():
    """Server belonging to Org A evaluated against User belonging to Org B is rejected."""
    db = SessionLocal()
    try:
        server = db.query(MCPServer).first()
        user = db.query(User).first()

        # Create foreign user
        foreign_user = User(
            id="foreign-user-id",
            organization_id="foreign-org-id",
            email="foreign@example.com",
            full_name="Foreign Operator",
            hashed_password="hash",
            role=RoleEnum.OPERATOR.value
        )
        settings.ENABLE_PERSISTENT_MCP_SESSIONS = True
        settings.PERSISTENT_MCP_SERVERS = server.identifier

        decision = CanaryGovernanceService.evaluate_server_canary_eligibility(db, server, user=foreign_user)
        assert decision.is_eligible is False
        assert "CROSS_TENANT_REJECTED" in decision.details.get("gate", "")
    finally:
        db.close()


def test_canary_eligibility_approved_server_passes():
    """Allowlisted, enabled, healthy server with matching tenant passes eligibility."""
    db = SessionLocal()
    try:
        server = db.query(MCPServer).first()
        user = db.query(User).filter(User.organization_id == server.organization_id).first()

        # Prepare server deployment state
        server.env_vars = {"DEPLOYMENT_STATE": DeploymentState.PREPARED.value}
        server.is_enabled = True
        server.status = "HEALTHY"
        db.commit()

        settings.ENABLE_PERSISTENT_MCP_SESSIONS = True
        settings.PERSISTENT_MCP_SERVERS = server.identifier

        decision = CanaryGovernanceService.evaluate_server_canary_eligibility(db, server, user=user)
        assert decision.is_eligible is True
        assert decision.details.get("gate") == "ELIGIBLE"
    finally:
        db.close()


# ==============================================================================
# 3. DEPLOYMENT GOVERNANCE STATE MACHINE TESTS (TASK D)
# ==============================================================================

def test_deployment_governance_valid_state_transitions():
    """Valid transitions: DISABLED -> PREPARED -> ELIGIBLE."""
    db = SessionLocal()
    try:
        server = db.query(MCPServer).first()
        admin = db.query(User).filter(User.role == RoleEnum.ADMIN.value, User.organization_id == server.organization_id).first()
        if not admin:
            admin = db.query(User).filter(User.role == RoleEnum.ADMIN.value).first()
            admin.organization_id = server.organization_id
            db.commit()

        # Reset to DISABLED
        server.env_vars = {"DEPLOYMENT_STATE": DeploymentState.DISABLED.value}
        db.commit()

        # Step 1: DISABLED -> PREPARED
        ok, msg, state = DeploymentGovernanceService.transition_state(
            db, server, DeploymentState.PREPARED, admin, "Infrastructure verification complete"
        )
        assert ok is True
        assert state == DeploymentState.PREPARED
        assert DeploymentGovernanceService.get_server_state(server) == DeploymentState.PREPARED

        # Step 2: PREPARED -> ELIGIBLE
        ok, msg, state = DeploymentGovernanceService.transition_state(
            db, server, DeploymentState.ELIGIBLE, admin, "Passed health check and canary eligibility"
        )
        assert ok is True
        assert state == DeploymentState.ELIGIBLE
    finally:
        db.close()


def test_deployment_governance_invalid_transition_rejected():
    """Invalid transitions (e.g. DISABLED -> CANARY_AUTHORIZED) are rejected."""
    db = SessionLocal()
    try:
        server = db.query(MCPServer).first()
        admin = db.query(User).filter(User.role == RoleEnum.ADMIN.value, User.organization_id == server.organization_id).first()
        server.env_vars = {"DEPLOYMENT_STATE": DeploymentState.DISABLED.value}
        db.commit()

        ok, msg, state = DeploymentGovernanceService.transition_state(
            db, server, DeploymentState.CANARY_AUTHORIZED, admin, "Attempt skip"
        )
        assert ok is False
        assert "Invalid transition" in msg
        assert state == DeploymentState.DISABLED
    finally:
        db.close()


def test_deployment_governance_canary_active_gated_in_phase15d3():
    """CANARY_ACTIVE is strictly gated and forbidden in Phase 15D.3 (Readiness only)."""
    db = SessionLocal()
    try:
        server = db.query(MCPServer).first()
        admin = db.query(User).filter(User.role == RoleEnum.ADMIN.value, User.organization_id == server.organization_id).first()
        server.env_vars = {"DEPLOYMENT_STATE": DeploymentState.CANARY_AUTHORIZED.value}
        db.commit()

        ok, msg, state = DeploymentGovernanceService.transition_state(
            db, server, DeploymentState.CANARY_ACTIVE, admin, "Attempt canary activation"
        )
        assert ok is False
        assert "CANARY_ACTIVE is gated and strictly forbidden in Phase 15D.3" in msg
    finally:
        db.close()


def test_deployment_governance_unauthorized_role_rejected():
    """VIEWER and OPERATOR cannot alter deployment state."""
    db = SessionLocal()
    try:
        server = db.query(MCPServer).first()
        viewer = db.query(User).filter(User.role == RoleEnum.VIEWER.value).first()
        if not viewer:
            viewer = User(id="v1", organization_id=server.organization_id, email="v@ex.com", full_name="Viewer", hashed_password="h", role=RoleEnum.VIEWER.value)
            db.add(viewer)
            db.commit()

        ok, msg, state = DeploymentGovernanceService.transition_state(
            db, server, DeploymentState.PREPARED, viewer, "Viewer transition attempt"
        )
        assert ok is False
        assert "Access denied" in msg
    finally:
        db.close()


def test_deployment_governance_history_audit_trail_and_persistence():
    """Deployment state and transition history persist across application restarts."""
    db = SessionLocal()
    try:
        server = db.query(MCPServer).first()
        admin = db.query(User).filter(User.role == RoleEnum.ADMIN.value, User.organization_id == server.organization_id).first()
        server.env_vars = {"DEPLOYMENT_STATE": DeploymentState.DISABLED.value, "DEPLOYMENT_HISTORY": []}
        db.commit()

        DeploymentGovernanceService.transition_state(db, server, DeploymentState.PREPARED, admin, "Initial prep")
        DeploymentGovernanceService.transition_state(db, server, DeploymentState.ELIGIBLE, admin, "Verified ready")

        # Reload server from database
        db.expire_all()
        reloaded = db.query(MCPServer).filter(MCPServer.id == server.id).first()

        assert DeploymentGovernanceService.get_server_state(reloaded) == DeploymentState.ELIGIBLE
        history = DeploymentGovernanceService.get_transition_history(reloaded)
        assert len(history) == 2
        assert history[0]["to_state"] == "PREPARED"
        assert history[1]["to_state"] == "ELIGIBLE"
    finally:
        db.close()


def test_deployment_governance_rollback_and_recovery():
    """Server-specific rollback disables persistent transport and recovery restores state."""
    db = SessionLocal()
    try:
        server = db.query(MCPServer).first()
        admin = db.query(User).filter(User.role == RoleEnum.ADMIN.value, User.organization_id == server.organization_id).first()

        # Rollback server
        ok, msg = DeploymentGovernanceService.rollback_server(db, server, admin, "High error rate observed")
        assert ok is True
        assert DeploymentGovernanceService.get_server_state(server) == DeploymentState.ROLLBACK

        # When rolled back, is_persistent_enabled must return False
        settings.ENABLE_PERSISTENT_MCP_SESSIONS = True
        settings.PERSISTENT_MCP_SERVERS = server.identifier
        assert MCPManager.is_persistent_enabled(server) is False

        # Recover server back to PREPARED
        rec_ok, rec_msg, new_state = DeploymentGovernanceService.transition_state(
            db, server, DeploymentState.PREPARED, admin, "Issue resolved, recovering server"
        )
        assert rec_ok is True
        assert new_state == DeploymentState.PREPARED
    finally:
        db.close()


# ==============================================================================
# 4. PERSISTENT SESSION SAFETY & LEGACY FALLBACK TESTS (TASK C3)
# ==============================================================================

@pytest.mark.asyncio
async def test_persistent_session_legacy_fallback_on_failure():
    """If a persistent session fails, execution safely falls back to legacy transport without crashing."""
    db = SessionLocal()
    try:
        server = db.query(MCPServer).first()
        tool = db.query(MCPTool).filter(MCPTool.server_id == server.id).first()

        # Mock PersistentSessionManager.execute_tool to raise an error
        with patch("app.mcp.persistent_session.PersistentSessionManager.execute_tool", side_effect=RuntimeError("Simulated persistent pipe crash")):
            with patch("app.services.mcp_manager.MCPManager.is_persistent_enabled", return_value=True):
                with patch("app.mcp.client.MCPClient.call_tool", return_value=({"fallback_result": "success"}, 12.5)):
                    res, dur, ok, err = await MCPManager.execute_tool(db, server, tool, {"test": 123})
                    assert ok is True
                    assert res.get("fallback_result") == "success"
                    assert MCPManager.get_fallback_counts().get(server.id, 0) >= 1
    finally:
        db.close()


# ==============================================================================
# 5. OBSERVABILITY & TELEMETRY TESTS (TASK F)
# ==============================================================================

def test_observability_percentile_latencies_and_bounded_sliding_window():
    """P95 and P99 are computed accurately from real measurements with a bounded window."""
    ObservabilityService.reset()

    # Record 100 executions with predictable latencies 1ms to 100ms
    for lat in range(1, 101):
        ObservabilityService.record_execution(duration_ms=float(lat), success=True)

    metrics = ObservabilityService.calculate_percentiles()
    assert metrics["avg_ms"] == 50.5
    assert metrics["p95_ms"] == 95.0
    assert metrics["p99_ms"] == 99.0

    # Test bounded sliding window (insert 1500 latencies, window size must remain <= 1000)
    for _ in range(1500):
        ObservabilityService.record_execution(duration_ms=25.0, success=True)
    assert len(ObservabilityService._latencies) == 1000


def test_observability_security_event_counters():
    """Security events (unauthorized, cross-tenant, policy denials) increment accurate counters."""
    ObservabilityService.reset()
    ObservabilityService.record_security_event("UNAUTHORIZED_ACTIVATION")
    ObservabilityService.record_security_event("CROSS_TENANT_ACCESS")
    ObservabilityService.record_security_event("POLICY_DENIAL")
    ObservabilityService.record_security_event("EMERGENCY_SHUTDOWN")

    snapshot = ObservabilityService.get_telemetry_snapshot()
    sec = snapshot["security_metrics"]
    assert sec["unauthorized_activation_attempts"] == 1
    assert sec["cross_tenant_access_attempts"] == 1
    assert sec["policy_denials"] == 1
    assert sec["emergency_shutdown_events"] == 1


# ==============================================================================
# 6. CANARY READINESS ACCEPTANCE THRESHOLDS (TASK H)
# ==============================================================================

def test_canary_readiness_thresholds_evaluation():
    """Readiness evaluation reports PASS/FAIL/INSUFFICIENT_DATA/NOT_MEASURED across all 10 criteria."""
    # When no canary traffic is active and observations == 0, status must be INSUFFICIENT_DATA (DEFECT-15D3-03 fix)
    eval_report = CanaryGovernanceService.evaluate_readiness_thresholds()
    assert eval_report["overall_status"] == "INSUFFICIENT_DATA"
    assert eval_report["canary_traffic_active"] is False
    assert eval_report["sample_size"] == 0
    assert eval_report["required_sample_size"] == 50

    criteria = eval_report["criteria"]
    assert criteria["execution_success_rate"]["status"] == "INSUFFICIENT_DATA"
    assert criteria["p95_latency"]["status"] == "INSUFFICIENT_DATA"
    assert criteria["p99_latency"]["status"] == "INSUFFICIENT_DATA"
    assert criteria["session_initialization_failures"]["status"] == "PASS"
    assert criteria["heartbeat_failures"]["status"] == "PASS"
    assert criteria["orphan_subprocesses"]["status"] == "PASS"
    assert criteria["unauthorized_activations"]["status"] == "PASS"
    assert criteria["cross_tenant_access"]["status"] == "PASS"

    # Simulated violation: even with insufficient observations, explicit failures trigger FAIL
    failing_report = CanaryGovernanceService.evaluate_readiness_thresholds({
        "total_observations": 10,
        "success_rate_pct": 85.0,  # Below threshold 99%
        "unauthorized_activations": 2
    })
    assert failing_report["overall_status"] == "FAIL"
    assert failing_report["criteria"]["execution_success_rate"]["status"] == "INSUFFICIENT_DATA"
    assert failing_report["criteria"]["unauthorized_activations"]["status"] == "FAIL"
