"""
MCP NEXUS — PHASE 15D.3.3 CONCURRENCY & ATOMIC AUDIT TEST SUITE

Tests the two Phase 15D.3.3 remediations:
1. DEFECT A: SQLite multi-process concurrency serialization via BEGIN IMMEDIATE
2. DEFECT B: Unified atomic transaction for deployment state transition and audit logging
"""

import os
import sys
import pytest
import threading
import multiprocessing
import time
from unittest.mock import patch

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.all_models import MCPServer, User, AuditLog
from app.services.audit_service import AuditService
from app.services.deployment_governance import DeploymentGovernanceService, DeploymentState
from app.database.session import SessionLocal


# Top-level helper for multiprocessing test (must be picklable on Windows)
def _multiprocess_transition_worker(db_url, server_id, admin_id, target_state_val, reason, result_queue):
    import os
    os.environ["DATABASE_URL"] = db_url
    from app.core.config import settings
    settings.DATABASE_URL = db_url
    from app.database.session import reset_database_engine, SessionLocal, _current_engine
    reset_database_engine(db_url)

    db = SessionLocal()
    try:
        s = db.query(MCPServer).filter(MCPServer.id == server_id).first()
        a = db.query(User).filter(User.id == admin_id).first()
        ok, msg, st = DeploymentGovernanceService.transition_state(
            db, s, DeploymentState(target_state_val), a, reason
        )
        result_queue.put((True, ok, msg, st.value))
    except Exception as e:
        result_queue.put((False, False, str(e), ""))
    finally:
        db.close()
        if _current_engine is not None:
            _current_engine.dispose()


# ==============================================================================
# DEFECT B: ATOMIC STATE TRANSITION AND AUDIT LOGGING TESTS
# ==============================================================================

def test_atomic_state_and_audit_success():
    """Verify that deployment state transition and AuditLog are committed together in one atomic transaction."""
    db = SessionLocal()
    try:
        server = db.query(MCPServer).first()
        admin = db.query(User).filter(User.role == "ADMIN").first()

        # Reset server to PREPARED
        server.env_vars = {"DEPLOYMENT_STATE": "PREPARED", "DEPLOYMENT_HISTORY": []}
        db.commit()

        initial_audit_count = db.query(AuditLog).filter(
            AuditLog.entity_id == server.id,
            AuditLog.action == "DEPLOYMENT_STATE_CHANGE"
        ).count()

        # Execute transition PREPARED -> ELIGIBLE
        ok, msg, new_state = DeploymentGovernanceService.transition_state(
            db, server, DeploymentState.ELIGIBLE, admin, "Promoting to eligible"
        )
        assert ok is True
        assert new_state == DeploymentState.ELIGIBLE

        # Verify state in fresh session
        db_check = SessionLocal()
        try:
            srv_fresh = db_check.query(MCPServer).filter(MCPServer.id == server.id).first()
            assert DeploymentGovernanceService.get_server_state(srv_fresh) == DeploymentState.ELIGIBLE

            # Verify audit log committed in the same transaction
            final_audit_count = db_check.query(AuditLog).filter(
                AuditLog.entity_id == server.id,
                AuditLog.action == "DEPLOYMENT_STATE_CHANGE"
            ).count()
            assert final_audit_count == initial_audit_count + 1

            latest_audit = db_check.query(AuditLog).filter(
                AuditLog.entity_id == server.id,
                AuditLog.action == "DEPLOYMENT_STATE_CHANGE"
            ).order_by(AuditLog.timestamp.desc()).first()

            assert latest_audit.user_name == admin.full_name
            assert latest_audit.role == admin.role
            assert "PREPARED -> ELIGIBLE" in latest_audit.details
            assert latest_audit.diff["from"] == "PREPARED"
            assert latest_audit.diff["to"] == "ELIGIBLE"
        finally:
            db_check.close()
    finally:
        db.close()


def test_atomic_rollback_on_audit_failure():
    """
    Simulate an unexpected failure during audit logging staging.
    Verify that server state update is rolled back and no partial changes or orphaned audits are committed.
    """
    db = SessionLocal()
    try:
        server = db.query(MCPServer).first()
        admin = db.query(User).filter(User.role == "ADMIN").first()

        server.env_vars = {"DEPLOYMENT_STATE": "PREPARED", "DEPLOYMENT_HISTORY": []}
        db.commit()

        initial_audit_count = db.query(AuditLog).filter(
            AuditLog.entity_id == server.id,
            AuditLog.action == "DEPLOYMENT_STATE_CHANGE"
        ).count()

        # Patch AuditService.record to raise an error
        with patch.object(AuditService, "record", side_effect=RuntimeError("Simulated audit disk full")):
            ok, msg, current_state = DeploymentGovernanceService.transition_state(
                db, server, DeploymentState.ELIGIBLE, admin, "Attempt with failing audit"
            )
            assert ok is False
            assert "Database transaction failed" in msg
            assert "Simulated audit disk full" in msg
            assert current_state == DeploymentState.PREPARED

        # Verify that state in DB remains PREPARED (rolled back)
        db_check = SessionLocal()
        try:
            srv_fresh = db_check.query(MCPServer).filter(MCPServer.id == server.id).first()
            assert DeploymentGovernanceService.get_server_state(srv_fresh) == DeploymentState.PREPARED
            assert srv_fresh.env_vars.get("DEPLOYMENT_STATE") == "PREPARED"

            # Verify no audit log was created
            post_audit_count = db_check.query(AuditLog).filter(
                AuditLog.entity_id == server.id,
                AuditLog.action == "DEPLOYMENT_STATE_CHANGE"
            ).count()
            assert post_audit_count == initial_audit_count
        finally:
            db_check.close()
    finally:
        db.close()


def test_atomic_rollback_on_commit_failure():
    """
    Simulate a failure during db.commit().
    Verify that both the server.env_vars update and the audit log are rolled back together.
    """
    db = SessionLocal()
    try:
        server = db.query(MCPServer).first()
        admin = db.query(User).filter(User.role == "ADMIN").first()

        server.env_vars = {"DEPLOYMENT_STATE": "PREPARED", "DEPLOYMENT_HISTORY": []}
        db.commit()

        initial_audit_count = db.query(AuditLog).filter(
            AuditLog.entity_id == server.id,
            AuditLog.action == "DEPLOYMENT_STATE_CHANGE"
        ).count()

        with patch.object(db, "commit", side_effect=RuntimeError("Simulated commit IO error")):
            ok, msg, current_state = DeploymentGovernanceService.transition_state(
                db, server, DeploymentState.ELIGIBLE, admin, "Attempt with failing commit"
            )
            assert ok is False
            assert "Database transaction failed" in msg
            assert "Simulated commit IO error" in msg

        # Verify state in DB remains PREPARED
        db_check = SessionLocal()
        try:
            srv_fresh = db_check.query(MCPServer).filter(MCPServer.id == server.id).first()
            assert DeploymentGovernanceService.get_server_state(srv_fresh) == DeploymentState.PREPARED

            post_audit_count = db_check.query(AuditLog).filter(
                AuditLog.entity_id == server.id,
                AuditLog.action == "DEPLOYMENT_STATE_CHANGE"
            ).count()
            assert post_audit_count == initial_audit_count
        finally:
            db_check.close()
    finally:
        db.close()


def test_audit_service_auto_commit_false_mechanics():
    """Verify that AuditService.record with auto_commit=False stages without committing."""
    db = SessionLocal()
    try:
        log = AuditService.record(
            db,
            action="TEST_ACTION",
            entity_type="TEST_ENTITY",
            entity_id="entity-123",
            user_name="Tester",
            role="ADMIN",
            details="Test details",
            auto_commit=False
        )
        assert log in db.new

        # Explicit rollback discards the staged log
        db.rollback()

        # Query to verify it was not committed
        persisted = db.query(AuditLog).filter(
            AuditLog.action == "TEST_ACTION",
            AuditLog.entity_id == "entity-123"
        ).first()
        assert persisted is None
    finally:
        db.close()


# ==============================================================================
# DEFECT A: SQLITE BEGIN IMMEDIATE CONCURRENCY & LOCK RELEASE TESTS
# ==============================================================================

def test_sqlite_begin_immediate_detects_concurrent_lock():
    """
    Verify that when another connection holds an IMMEDIATE transaction,
    transition_state detects the locked database and safely reports lock contention.
    """
    db1 = SessionLocal()
    db2 = SessionLocal()
    try:
        bind = db1.get_bind()
        if bind.dialect.name.lower() != "sqlite":
            pytest.skip("Test specifically covers SQLite BEGIN IMMEDIATE lock contention")

        server = db1.query(MCPServer).first()
        admin = db1.query(User).filter(User.role == "ADMIN").first()

        server.env_vars = {"DEPLOYMENT_STATE": "PREPARED", "DEPLOYMENT_HISTORY": []}
        db1.commit()

        # s2 and a2 loaded before contention
        s2 = db2.query(MCPServer).filter(MCPServer.id == server.id).first()
        a2 = db2.query(User).filter(User.id == admin.id).first()

        orig_execute = db2.execute
        def selective_execute(statement, *args, **kwargs):
            if "BEGIN IMMEDIATE" in str(statement):
                raise Exception("(sqlite3.OperationalError) database is locked")
            return orig_execute(statement, *args, **kwargs)

        with patch.object(db2, "execute", side_effect=selective_execute):
            ok, msg, state = DeploymentGovernanceService.transition_state(
                db2, s2, DeploymentState.ELIGIBLE, a2, "Transition during contention"
            )
            assert ok is False
            assert "database is locked" in msg.lower()
            assert state == DeploymentState.PREPARED
    finally:
        db1.close()
        db2.close()


def test_lock_released_on_rejected_transition():
    """
    Verify that when a transition is rejected (e.g. invalid matrix or safety gate),
    the SQLite transaction is immediately rolled back, releasing the reserved lock.
    """
    db1 = SessionLocal()
    db2 = SessionLocal()
    try:
        server = db1.query(MCPServer).first()
        admin = db1.query(User).filter(User.role == "ADMIN").first()

        server.env_vars = {"DEPLOYMENT_STATE": "PREPARED", "DEPLOYMENT_HISTORY": []}
        db1.commit()

        # Attempt forbidden transition: CANARY_ACTIVE is strictly forbidden in Phase 15D.3
        ok, msg, st = DeploymentGovernanceService.transition_state(
            db1, server, DeploymentState.CANARY_ACTIVE, admin, "Premature canary activation"
        )
        assert ok is False
        assert "forbidden in Phase 15D.3" in msg

        # db2 should be able to execute transition immediately without database is locked error
        s2 = db2.query(MCPServer).filter(MCPServer.id == server.id).first()
        a2 = db2.query(User).filter(User.id == admin.id).first()

        ok2, msg2, st2 = DeploymentGovernanceService.transition_state(
            db2, s2, DeploymentState.ELIGIBLE, a2, "Valid transition following rejected"
        )
        assert ok2 is True
        assert st2 == DeploymentState.ELIGIBLE
    finally:
        db1.close()
        db2.close()


def test_lock_released_on_tenant_isolation_rejection():
    """
    Verify that tenant isolation failure rolls back transaction cleanly, releasing any SQLite lock.
    """
    db1 = SessionLocal()
    db2 = SessionLocal()
    try:
        server = db1.query(MCPServer).first()
        admin = db1.query(User).filter(User.role == "ADMIN").first()

        # Create actor from another org
        unauthorized_actor = User(
            id="usr-cross-org",
            email="other@corp.io",
            full_name="Other Org User",
            role="ADMIN",
            organization_id="org-foreign-999"
        )

        ok, msg, st = DeploymentGovernanceService.transition_state(
            db1, server, DeploymentState.DISABLED, unauthorized_actor, "Cross-tenant attempt"
        )
        assert ok is False
        assert "Cannot alter deployment state of another organization" in msg

        # Next valid transition on db2 must succeed immediately
        s2 = db2.query(MCPServer).filter(MCPServer.id == server.id).first()
        a2 = db2.query(User).filter(User.id == admin.id).first()

        ok2, msg2, st2 = DeploymentGovernanceService.transition_state(
            db2, s2, DeploymentState.DISABLED, a2, "Valid authorized transition"
        )
        assert ok2 is True
        assert st2 == DeploymentState.DISABLED
    finally:
        db1.close()
        db2.close()


def test_sqlite_multithread_cross_session_serialization():
    """
    Simulate multiple threads attempting conflicting state transitions concurrently.
    All transitions must either succeed sequentially or fail cleanly with transition matrix
    or lock rejection, never corrupting state or losing audit records.
    """
    db_setup = SessionLocal()
    server = db_setup.query(MCPServer).first()
    admin = db_setup.query(User).filter(User.role == "ADMIN").first()
    server_id = server.id
    admin_id = admin.id

    server.env_vars = {"DEPLOYMENT_STATE": "PREPARED", "DEPLOYMENT_HISTORY": []}
    db_setup.commit()

    initial_audit_count = db_setup.query(AuditLog).filter(
        AuditLog.entity_id == server_id,
        AuditLog.action == "DEPLOYMENT_STATE_CHANGE"
    ).count()
    db_setup.close()

    results = []
    barrier = threading.Barrier(3)

    def worker(worker_id: int, target_state: DeploymentState, reason: str):
        barrier.wait()
        db = SessionLocal()
        try:
            s = db.query(MCPServer).filter(MCPServer.id == server_id).first()
            a = db.query(User).filter(User.id == admin_id).first()
            ok, msg, st = DeploymentGovernanceService.transition_state(
                db, s, target_state, a, reason
            )
            results.append((worker_id, ok, msg, st))
        finally:
            db.close()

    t1 = threading.Thread(target=worker, args=(1, DeploymentState.ELIGIBLE, "Worker 1 to ELIGIBLE"))
    t2 = threading.Thread(target=worker, args=(2, DeploymentState.DISABLED, "Worker 2 to DISABLED"))
    t3 = threading.Thread(target=worker, args=(3, DeploymentState.ELIGIBLE, "Worker 3 to ELIGIBLE"))

    for t in (t1, t2, t3):
        t.start()
    for t in (t1, t2, t3):
        t.join()

    # All 3 workers must have finished cleanly without uncaught exceptions
    assert len(results) == 3
    successful_count = sum(1 for r in results if r[1] is True)

    # Check database state consistency
    db_final = SessionLocal()
    try:
        srv_final = db_final.query(MCPServer).filter(MCPServer.id == server_id).first()
        final_state = DeploymentGovernanceService.get_server_state(srv_final)
        history = DeploymentGovernanceService.get_transition_history(srv_final)
        final_audit_count = db_final.query(AuditLog).filter(
            AuditLog.entity_id == server_id,
            AuditLog.action == "DEPLOYMENT_STATE_CHANGE"
        ).count()

        audit_delta = final_audit_count - initial_audit_count

        # The number of history entries added must match the successful transition count and audit delta
        assert len(history) == successful_count
        assert audit_delta == successful_count
        # The latest history entry to_state must match the final server state
        if history:
            assert history[-1]["to_state"] == final_state.value
    finally:
        db_final.close()


def test_sqlite_multiprocess_cross_process_serialization():
    """
    True multi-process test: launch two separate OS processes executing state transitions
    concurrently on the shared test database. Verify no deadlocks, no corruptions, and
    exact serialized audit/history consistency.
    """
    db_setup = SessionLocal()
    server = db_setup.query(MCPServer).first()
    admin = db_setup.query(User).filter(User.role == "ADMIN").first()
    server_id = server.id
    admin_id = admin.id

    server.env_vars = {"DEPLOYMENT_STATE": "PREPARED", "DEPLOYMENT_HISTORY": []}
    db_setup.commit()

    initial_audit_count = db_setup.query(AuditLog).filter(
        AuditLog.entity_id == server_id,
        AuditLog.action == "DEPLOYMENT_STATE_CHANGE"
    ).count()
    db_setup.close()

    queue = multiprocessing.Queue()
    db_url = settings.DATABASE_URL

    p1 = multiprocessing.Process(
        target=_multiprocess_transition_worker,
        args=(db_url, server_id, admin_id, "ELIGIBLE", "Process 1 promotion", queue)
    )
    p2 = multiprocessing.Process(
        target=_multiprocess_transition_worker,
        args=(db_url, server_id, admin_id, "DISABLED", "Process 2 disabling", queue)
    )

    p1.start()
    p2.start()

    # Collect outcomes from queue reliably with timeout
    outcomes = []
    for _ in range(2):
        try:
            outcomes.append(queue.get(timeout=15))
        except Exception:
            pass

    p1.join(timeout=10)
    p2.join(timeout=10)

    assert len(outcomes) == 2
    for executed_cleanly, ok, msg, st_val in outcomes:
        assert executed_cleanly is True

    # Verify database final state and audit log consistency
    db_check = SessionLocal()
    try:
        srv_final = db_check.query(MCPServer).filter(MCPServer.id == server_id).first()
        history = DeploymentGovernanceService.get_transition_history(srv_final)
        final_audit_count = db_check.query(AuditLog).filter(
            AuditLog.entity_id == server_id,
            AuditLog.action == "DEPLOYMENT_STATE_CHANGE"
        ).count()
        audit_delta = final_audit_count - initial_audit_count

        successful_ops = sum(1 for o in outcomes if o[1] is True)
        assert len(history) == successful_ops
        assert audit_delta == successful_ops
    finally:
        db_check.close()
