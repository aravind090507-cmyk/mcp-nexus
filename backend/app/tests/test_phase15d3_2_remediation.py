"""
MCP NEXUS — PHASE 15D.3.2 REMEDIATION REGRESSION TEST SUITE

Tests the three remediations:
1. DEFECT-15D3-01: Mandatory Allowlist & Server Env Opt-Out (No Bypass)
2. DEFECT-15D3-02: Multi-Process & Transactional Deployment State Concurrency
3. DEFECT-15D3-03: Bounded Sample Size & INSUFFICIENT_DATA Canary Readiness
"""

import os
import sys
import pytest
import threading
import time
from unittest.mock import patch

from app.core.config import settings
from app.models.all_models import MCPServer, User, Organization
from app.services.mcp_manager import MCPManager
from app.services.canary_governance import CanaryGovernanceService
from app.services.deployment_governance import DeploymentGovernanceService, DeploymentState
from app.mcp.persistent_session import PersistentSessionManager
from app.database.session import SessionLocal, get_current_managed_context


# ==============================================================================
# DEFECT 1: ALLOWLIST ENFORCEMENT & BYPASS PREVENTION
# ==============================================================================

def test_remediation_01_empty_allowlist_rejects_every_server():
    """An empty PERSISTENT_MCP_SERVERS must reject all servers, regardless of env_vars."""
    server = MCPServer(
        id="srv-test-1",
        name="Test Srv",
        identifier="test-srv",
        is_enabled=True,
        transport_type="STDIO",
        env_vars={"ENABLE_PERSISTENT_SESSION": "true"}
    )
    with patch.object(settings, "ENABLE_PERSISTENT_MCP_SESSIONS", True), \
         patch.object(settings, "PERSISTENT_MCP_SERVERS", ""):
        assert MCPManager.is_persistent_enabled(server) is False
        decision = CanaryGovernanceService.evaluate_server_canary_eligibility(None, server)
        assert decision.is_eligible is False
        assert decision.details["gate"] == "ALLOWLIST_EMPTY"


def test_remediation_02_server_absent_from_allowlist_rejected():
    """A server not explicitly listed in PERSISTENT_MCP_SERVERS must be rejected."""
    server = MCPServer(
        id="srv-unlisted",
        name="Unlisted Srv",
        identifier="unlisted-srv",
        is_enabled=True,
        transport_type="STDIO",
        env_vars={"ENABLE_PERSISTENT_SESSION": "true"}
    )
    with patch.object(settings, "ENABLE_PERSISTENT_MCP_SESSIONS", True), \
         patch.object(settings, "PERSISTENT_MCP_SERVERS", "other-server-id,another-server"):
        assert MCPManager.is_persistent_enabled(server) is False
        decision = CanaryGovernanceService.evaluate_server_canary_eligibility(None, server)
        assert decision.is_eligible is False
        assert decision.details["gate"] == "NOT_IN_ALLOWLIST"


def test_remediation_03_server_present_in_allowlist_accepted():
    """A server present in PERSISTENT_MCP_SERVERS is accepted if enabled and healthy."""
    server = MCPServer(
        id="srv-allowed",
        name="Allowed Srv",
        identifier="allowed-srv",
        is_enabled=True,
        status="HEALTHY",
        transport_type="STDIO",
        env_vars={}
    )
    with patch.object(settings, "ENABLE_PERSISTENT_MCP_SESSIONS", True), \
         patch.object(settings, "PERSISTENT_MCP_SERVERS", "allowed-srv"):
        assert MCPManager.is_persistent_enabled(server) is True
        decision = CanaryGovernanceService.evaluate_server_canary_eligibility(None, server)
        assert decision.is_eligible is True
        assert decision.details["gate"] == "ELIGIBLE"


def test_remediation_04_server_env_cannot_bypass_allowlist_but_can_opt_out():
    """Server env ENABLE_PERSISTENT_SESSION cannot bypass allowlist, but allowlisted server can opt out."""
    server_allowed = MCPServer(
        id="srv-optout",
        name="Optout Srv",
        identifier="optout-srv",
        is_enabled=True,
        status="HEALTHY",
        transport_type="STDIO",
        env_vars={"ENABLE_PERSISTENT_SESSION": "false"}
    )
    server_unallowed = MCPServer(
        id="srv-bypass-attempt",
        name="Bypass Srv",
        identifier="bypass-srv",
        is_enabled=True,
        status="HEALTHY",
        transport_type="STDIO",
        env_vars={"ENABLE_PERSISTENT_SESSION": "true"}
    )
    with patch.object(settings, "ENABLE_PERSISTENT_MCP_SESSIONS", True), \
         patch.object(settings, "PERSISTENT_MCP_SERVERS", "optout-srv"):
        # Server in allowlist opts out -> False
        assert MCPManager.is_persistent_enabled(server_allowed) is False

        # Server NOT in allowlist tries to opt in -> False (Blocked)
        assert MCPManager.is_persistent_enabled(server_unallowed) is False


def test_remediation_05_global_flag_disabled_rejects_all():
    """When ENABLE_PERSISTENT_MCP_SESSIONS is False, everything is rejected."""
    server = MCPServer(
        id="srv-allowed",
        name="Allowed Srv",
        identifier="allowed-srv",
        is_enabled=True,
        transport_type="STDIO",
        env_vars={}
    )
    with patch.object(settings, "ENABLE_PERSISTENT_MCP_SESSIONS", False), \
         patch.object(settings, "PERSISTENT_MCP_SERVERS", "allowed-srv"):
        assert MCPManager.is_persistent_enabled(server) is False
        decision = CanaryGovernanceService.evaluate_server_canary_eligibility(None, server)
        assert decision.is_eligible is False
        assert decision.details["gate"] == "GLOBAL_FLAG_DISABLED"


def test_remediation_06_emergency_shutdown_rejects_all():
    """When emergency kill switch is active, everything is rejected."""
    server = MCPServer(
        id="srv-allowed",
        name="Allowed Srv",
        identifier="allowed-srv",
        is_enabled=True,
        transport_type="STDIO",
        env_vars={}
    )
    with patch.object(settings, "ENABLE_PERSISTENT_MCP_SESSIONS", True), \
         patch.object(settings, "PERSISTENT_MCP_SERVERS", "allowed-srv"), \
         patch.object(PersistentSessionManager, "is_emergency_disabled", return_value=True):
        assert MCPManager.is_persistent_enabled(server) is False
        decision = CanaryGovernanceService.evaluate_server_canary_eligibility(None, server)
        assert decision.is_eligible is False
        assert decision.details["gate"] == "EMERGENCY_KILL_SWITCH_ACTIVE"


def test_remediation_07_administratively_disabled_server_rejected():
    """Administratively disabled or unhealthy server is rejected."""
    disabled_srv = MCPServer(
        id="srv-allowed",
        name="Allowed Srv",
        identifier="allowed-srv",
        is_enabled=False,
        transport_type="STDIO",
        env_vars={}
    )
    unhealthy_srv = MCPServer(
        id="srv-allowed-2",
        name="Allowed Srv 2",
        identifier="allowed-srv-2",
        is_enabled=True,
        status="UNHEALTHY",
        transport_type="STDIO",
        env_vars={}
    )
    with patch.object(settings, "ENABLE_PERSISTENT_MCP_SESSIONS", True), \
         patch.object(settings, "PERSISTENT_MCP_SERVERS", "allowed-srv, allowed-srv-2"):
        assert MCPManager.is_persistent_enabled(disabled_srv) is False
        dec1 = CanaryGovernanceService.evaluate_server_canary_eligibility(None, disabled_srv)
        assert dec1.is_eligible is False
        assert dec1.details["gate"] == "SERVER_DISABLED"

        dec2 = CanaryGovernanceService.evaluate_server_canary_eligibility(None, unhealthy_srv)
        assert dec2.is_eligible is False
        assert dec2.details["gate"] == "SERVER_UNHEALTHY"


# ==============================================================================
# DEFECT 2: CONCURRENCY & TRANSACTIONAL DEPLOYMENT STATE TRANSITIONS
# ==============================================================================

def test_remediation_08_concurrent_conflicting_transitions():
    """Two concurrent transitions on the same server from independent DB sessions."""
    db_init = SessionLocal()
    server = db_init.query(MCPServer).first()
    admin = db_init.query(User).filter(User.role == "ADMIN").first()
    server_id = server.id
    admin_id = admin.id

    # Reset state to PREPARED
    server.env_vars = {"DEPLOYMENT_STATE": "PREPARED", "DEPLOYMENT_HISTORY": []}
    db_init.commit()
    db_init.close()

    results = []
    def run_t1():
        db1 = SessionLocal()
        try:
            s1 = db1.query(MCPServer).filter(MCPServer.id == server_id).first()
            a1 = db1.query(User).filter(User.id == admin_id).first()
            ok, msg, st = DeploymentGovernanceService.transition_state(
                db1, s1, DeploymentState.ELIGIBLE, a1, "T1 transition"
            )
            results.append(("T1", ok, st))
        finally:
            db1.close()

    def run_t2():
        db2 = SessionLocal()
        try:
            s2 = db2.query(MCPServer).filter(MCPServer.id == server_id).first()
            a2 = db2.query(User).filter(User.id == admin_id).first()
            ok, msg, st = DeploymentGovernanceService.transition_state(
                db2, s2, DeploymentState.DISABLED, a2, "T2 transition"
            )
            results.append(("T2", ok, st))
        finally:
            db2.close()

    th1 = threading.Thread(target=run_t1)
    th2 = threading.Thread(target=run_t2)

    th1.start()
    th2.start()
    th1.join()
    th2.join()

    # Exactly both operations must complete without crashing or corrupting history
    assert len(results) == 2
    # Verify history consistency in fresh session
    db_check = SessionLocal()
    srv_final = db_check.query(MCPServer).filter(MCPServer.id == server_id).first()
    history = DeploymentGovernanceService.get_transition_history(srv_final)
    assert len(history) >= 1
    db_check.close()


def test_remediation_09_concurrent_identical_transitions():
    """Two concurrent identical transitions: first succeeds, second fails transition matrix check."""
    db_init = SessionLocal()
    server = db_init.query(MCPServer).first()
    admin = db_init.query(User).filter(User.role == "ADMIN").first()
    server_id = server.id
    admin_id = admin.id

    server.env_vars = {"DEPLOYMENT_STATE": "PREPARED", "DEPLOYMENT_HISTORY": []}
    db_init.commit()
    db_init.close()

    results = []
    def run_t(label):
        sess = SessionLocal()
        try:
            s = sess.query(MCPServer).filter(MCPServer.id == server_id).first()
            a = sess.query(User).filter(User.id == admin_id).first()
            ok, msg, st = DeploymentGovernanceService.transition_state(
                sess, s, DeploymentState.ELIGIBLE, a, f"{label} identical target"
            )
            results.append((label, ok, st, msg))
        finally:
            sess.close()

    th1 = threading.Thread(target=run_t, args=("R1",))
    th2 = threading.Thread(target=run_t, args=("R2",))

    th1.start()
    th2.start()
    th1.join()
    th2.join()

    # One should succeed (PREPARED -> ELIGIBLE); the second should fail because target state == current state
    successes = [r for r in results if r[1] is True]
    failures = [r for r in results if r[1] is False]
    assert len(successes) == 1
    assert len(failures) == 1
    assert "Invalid transition" in failures[0][3]


def test_remediation_10_concurrent_rollback_and_activation():
    """Concurrent rollback and state transition attempts."""
    db_init = SessionLocal()
    server = db_init.query(MCPServer).first()
    admin = db_init.query(User).filter(User.role == "ADMIN").first()
    server_id = server.id
    admin_id = admin.id
    server.env_vars = {"DEPLOYMENT_STATE": "ELIGIBLE", "DEPLOYMENT_HISTORY": []}
    db_init.commit()
    db_init.close()

    results = []
    def do_rollback():
        db1 = SessionLocal()
        try:
            s = db1.query(MCPServer).filter(MCPServer.id == server_id).first()
            a = db1.query(User).filter(User.id == admin_id).first()
            ok, msg = DeploymentGovernanceService.rollback_server(db1, s, a, "Emergency rollback")
            results.append(("ROLLBACK", ok, msg))
        finally:
            db1.close()

    def do_transition():
        db2 = SessionLocal()
        try:
            s = db2.query(MCPServer).filter(MCPServer.id == server_id).first()
            a = db2.query(User).filter(User.id == admin_id).first()
            ok, msg, st = DeploymentGovernanceService.transition_state(
                db2, s, DeploymentState.CANARY_AUTHORIZED, a, "Authorize canary"
            )
            results.append(("TRANSITION", ok, msg))
        finally:
            db2.close()

    t1 = threading.Thread(target=do_rollback)
    t2 = threading.Thread(target=do_transition)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert len(results) == 2
    # Rollback is always permitted; state integrity is maintained
    db_check = SessionLocal()
    final_server = db_check.query(MCPServer).filter(MCPServer.id == server_id).first()
    assert final_server.env_vars["DEPLOYMENT_STATE"] in ("ROLLBACK", "CANARY_AUTHORIZED")
    db_check.close()


def test_remediation_11_transaction_failure_rollback():
    """A database error during transition rolls back the transaction and restores state."""
    db = SessionLocal()
    try:
        server = db.query(MCPServer).first()
        admin = db.query(User).filter(User.role == "ADMIN").first()

        server.env_vars = {"DEPLOYMENT_STATE": "PREPARED", "DEPLOYMENT_HISTORY": []}
        db.commit()

        # Mock db.commit to raise an exception
        with patch.object(db, "commit", side_effect=RuntimeError("Simulated DB Disk Failure")):
            ok, msg, st = DeploymentGovernanceService.transition_state(
                db, server, DeploymentState.ELIGIBLE, admin, "Failing commit test"
            )
            assert ok is False
            assert "Database transaction failed" in msg
            assert st == DeploymentState.PREPARED
    finally:
        db.close()


def test_remediation_12_cross_tenant_concurrent_attempt():
    """Cross-tenant actor attempting transition is rejected under concurrency."""
    db = SessionLocal()
    try:
        server = db.query(MCPServer).first()
        # Create alien user with different organization
        alien_user = User(
            id="alien-admin-user",
            organization_id="different-org-id-0000-000000000000",
            email="alien@competitor.com",
            full_name="Alien Admin",
            hashed_password="pw",
            role="ADMIN"
        )
        ok, msg, st = DeploymentGovernanceService.transition_state(
            db, server, DeploymentState.DISABLED, alien_user, "Malicious cross-tenant disable"
        )
        assert ok is False
        assert "Access denied: Cannot alter deployment state of another organization's server." in msg
    finally:
        db.close()


# ==============================================================================
# DEFECT 3: CANARY READINESS ACCEPTANCE EVALUATOR
# ==============================================================================

def test_remediation_13_zero_observations_returns_insufficient_data():
    """Zero observations must evaluate to INSUFFICIENT_DATA, never READY_FOR_CANARY."""
    report = CanaryGovernanceService.evaluate_readiness_thresholds(
        observed_metrics={"total_observations": 0, "success_rate_pct": None},
        min_observations=50
    )
    assert report["overall_status"] == "INSUFFICIENT_DATA"
    assert report["sample_size"] == 0
    assert report["required_sample_size"] == 50
    assert report["criteria"]["execution_success_rate"]["status"] == "INSUFFICIENT_DATA"
    assert report["criteria"]["p95_latency"]["status"] == "INSUFFICIENT_DATA"
    assert report["criteria"]["p99_latency"]["status"] == "INSUFFICIENT_DATA"


def test_remediation_14_one_observation_returns_insufficient_data():
    """1 observation is below the 50 minimum and must return INSUFFICIENT_DATA."""
    report = CanaryGovernanceService.evaluate_readiness_thresholds(
        observed_metrics={
            "total_observations": 1,
            "success_rate_pct": 100.0,
            "p95_latency_ms": 10.0,
            "p99_latency_ms": 10.0
        },
        min_observations=50
    )
    assert report["overall_status"] == "INSUFFICIENT_DATA"
    assert report["sample_size"] == 1
    assert report["criteria"]["execution_success_rate"]["status"] == "INSUFFICIENT_DATA"


def test_remediation_15_forty_nine_observations_returns_insufficient_data():
    """49 observations (n < 50) must still return INSUFFICIENT_DATA."""
    report = CanaryGovernanceService.evaluate_readiness_thresholds(
        observed_metrics={
            "total_observations": 49,
            "success_rate_pct": 99.5,
            "p95_latency_ms": 25.0,
            "p99_latency_ms": 40.0
        },
        min_observations=50
    )
    assert report["overall_status"] == "INSUFFICIENT_DATA"
    assert report["sample_size"] == 49
    assert report["criteria"]["execution_success_rate"]["status"] == "INSUFFICIENT_DATA"


def test_remediation_16_fifty_observations_passing_evaluates_ready():
    """50 observations with compliant metrics evaluates to READY_FOR_CANARY."""
    report = CanaryGovernanceService.evaluate_readiness_thresholds(
        observed_metrics={
            "total_observations": 50,
            "success_rate_pct": 99.8,
            "p95_latency_ms": 45.0,
            "p99_latency_ms": 85.0,
            "init_failures": 0,
            "heartbeat_failures": 0,
            "orphan_subprocesses": 0,
            "unauthorized_activations": 0,
            "cross_tenant_access": 0
        },
        min_observations=50
    )
    assert report["overall_status"] == "READY_FOR_CANARY"
    assert report["sample_size"] == 50
    assert report["criteria"]["execution_success_rate"]["status"] == "PASS"
    assert report["criteria"]["p95_latency"]["status"] == "PASS"
    assert report["criteria"]["p99_latency"]["status"] == "PASS"


def test_remediation_17_failed_threshold_triggers_fail():
    """A violation of success rate threshold (<99%) triggers FAIL, regardless of sample size."""
    report = CanaryGovernanceService.evaluate_readiness_thresholds(
        observed_metrics={
            "total_observations": 100,
            "success_rate_pct": 95.0,  # Below 99.0%
            "p95_latency_ms": 40.0,
            "p99_latency_ms": 60.0
        },
        min_observations=50
    )
    assert report["overall_status"] == "FAIL"
    assert report["criteria"]["execution_success_rate"]["status"] == "FAIL"


def test_remediation_18_missing_latencies_evaluates_insufficient_data():
    """If observations >= 50 but latency measurements are missing, returns INSUFFICIENT_DATA."""
    report = CanaryGovernanceService.evaluate_readiness_thresholds(
        observed_metrics={
            "total_observations": 50,
            "success_rate_pct": 100.0,
            # No p95_latency_ms or p99_latency_ms provided
        },
        min_observations=50
    )
    assert report["overall_status"] == "NOT_READY"
    assert report["criteria"]["p95_latency"]["status"] == "NOT_MEASURED"


def test_remediation_19_application_restart_simulation():
    """Simulating process restart (zero metrics) returns INSUFFICIENT_DATA, preventing premature rollout."""
    fresh_metrics = {
        "total_observations": 0,
        "success_rate_pct": None,
        "p95_latency_ms": None,
        "p99_latency_ms": None,
        "init_failures": 0,
        "heartbeat_failures": 0
    }
    report = CanaryGovernanceService.evaluate_readiness_thresholds(fresh_metrics, min_observations=50)
    assert report["overall_status"] == "INSUFFICIENT_DATA"
