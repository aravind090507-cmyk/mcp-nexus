"""
MCP NEXUS — PHASE 15D.4.2 MULTIPROCESS & ATOMIC AUDIT RELIABILITY TEST SUITE

Tests:
1. WORKSTREAM B: True Multiprocess Emergency Shutdown Propagation, Persistence, and Recovery.
   Uses operating-system spawned independent processes (multiprocessing spawn context)
   with separate memory spaces, process IDs, and isolated database connection pools.
2. WORKSTREAM C: Atomic Audit-Event Persistence, Failure Rollback, and Concurrency Consistency.
"""

import os
import sys
import uuid
import time
import asyncio
import pytest
import multiprocessing as mp

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.all_models import MCPServer, User, Organization, AuditLog, IntegrationConfig
from app.services.audit_service import AuditService
from app.services.deployment_governance import DeploymentGovernanceService, DeploymentState
from app.mcp.persistent_session import PersistentSessionManager
from app.core.security import get_password_hash


# ==============================================================================
# Top-level Multiprocessing Worker Functions (Required for Windows Spawn)
# ==============================================================================

def _multiprocess_executor_worker(db_url: str, cmd_queue: mp.Queue, res_queue: mp.Queue):
    """
    Independent OS process worker that executes lifecycle and governance commands
    against an isolated database connection pool without shared memory.
    """
    import os
    import sys
    import asyncio
    os.environ["DATABASE_URL"] = db_url

    from app.core.config import settings
    settings.DATABASE_URL = db_url

    from app.database.session import reset_database_engine, SessionLocal, _current_engine
    reset_database_engine(db_url)

    from app.mcp.persistent_session import PersistentSessionManager
    from app.services.deployment_governance import DeploymentGovernanceService, DeploymentState
    from app.models.all_models import MCPServer, User, AuditLog

    # Signal ready
    res_queue.put(("READY", os.getpid()))

    while True:
        try:
            item = cmd_queue.get(timeout=10.0)
        except Exception:
            break

        cmd = item[0]
        if cmd == "EXIT":
            break

        elif cmd == "CHECK_SHUTDOWN":
            # Test whether shutdown is detected from DB
            is_disabled = PersistentSessionManager.is_emergency_disabled()
            reason = PersistentSessionManager._emergency_reason
            res_queue.put(("STATUS", is_disabled, reason, os.getpid()))

        elif cmd == "TRIGGER_SHUTDOWN":
            reason = item[1]
            actor = item[2]
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                res = loop.run_until_complete(
                    PersistentSessionManager.emergency_disable(reason=reason, actor_email=actor)
                )
                loop.close()
                res_queue.put(("SHUTDOWN_OK", res, os.getpid()))
            except Exception as e:
                res_queue.put(("SHUTDOWN_ERROR", str(e), os.getpid()))

        elif cmd == "TRIGGER_ENABLE":
            actor = item[1]
            try:
                res = PersistentSessionManager.emergency_enable(actor_email=actor)
                res_queue.put(("ENABLE_OK", res, os.getpid()))
            except Exception as e:
                res_queue.put(("ENABLE_ERROR", str(e), os.getpid()))

        elif cmd == "ATTEMPT_CANARY_TRANSITION":
            server_id = item[1]
            admin_id = item[2]
            target_state_val = item[3]
            db = SessionLocal()
            try:
                s = db.query(MCPServer).filter(MCPServer.id == server_id).first()
                a = db.query(User).filter(User.id == admin_id).first()
                ok, msg, st = DeploymentGovernanceService.transition_state(
                    db, s, DeploymentState(target_state_val), a, "Multiprocess transition attempt"
                )
                res_queue.put(("TRANSITION_RESULT", ok, msg, st.value if st else None, os.getpid()))
            except Exception as e:
                res_queue.put(("TRANSITION_ERROR", str(e), None, None, os.getpid()))
            finally:
                db.close()

        elif cmd == "ATTEMPT_ACQUIRE_SESSION":
            # Attempting to acquire persistent session must fail if shutdown is engaged
            try:
                # PersistentSessionManager.is_emergency_disabled() check
                if PersistentSessionManager.is_emergency_disabled():
                    raise RuntimeError(f"Cannot acquire persistent session: emergency kill switch is engaged ({PersistentSessionManager._emergency_reason}).")
                res_queue.put(("ACQUIRE_OK", True, os.getpid()))
            except Exception as e:
                res_queue.put(("ACQUIRE_BLOCKED", str(e), os.getpid()))

    if _current_engine is not None:
        _current_engine.dispose()


# ==============================================================================
# Helper for creating a clean test database environment (PostgreSQL or SQLite)
# ==============================================================================

@pytest.fixture(autouse=True)
def cleanup_multiprocess_workers():
    """Ensure no worker processes spawned via multiprocessing survive across test cases."""
    yield
    import multiprocessing as mp
    for p in mp.active_children():
        try:
            p.terminate()
            p.join(timeout=1.0)
            if p.is_alive():
                p.kill()
                p.join(timeout=1.0)
        except Exception:
            pass

@pytest.fixture(scope="module")
def reliability_db_url():
    pg_url = os.getenv("POSTGRES_TEST_DATABASE_URL")
    if pg_url and pg_url.startswith("postgresql"):
        # Use live PostgreSQL
        engine = create_engine(pg_url, pool_pre_ping=True)
        from app.database.session import Base
        Base.metadata.create_all(bind=engine)
        yield pg_url
        engine.dispose()
    else:
        # Fall back to isolated SQLite file for local verification
        test_db_path = os.path.abspath(f"mcp_nexus_multiprocess_test_{uuid.uuid4().hex[:6]}.db")
        db_url = f"sqlite:///{test_db_path}"
        engine = create_engine(db_url)
        from app.database.session import Base
        Base.metadata.create_all(bind=engine)
        yield db_url
        engine.dispose()
        if os.path.exists(test_db_path):
            try:
                os.remove(test_db_path)
            except Exception:
                pass


@pytest.fixture
def test_setup_entities(reliability_db_url):
    engine = create_engine(reliability_db_url)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    try:
        org_slug = f"mp-org-{uuid.uuid4().hex[:6]}"
        org = Organization(name="Multiprocess Test Org", slug=org_slug, tier="ENTERPRISE")
        session.add(org)
        session.commit()
        session.refresh(org)

        admin = User(
            organization_id=org.id,
            email=f"mp_admin_{uuid.uuid4().hex[:6]}@test.com",
            hashed_password=get_password_hash("testpass"),
            full_name="Multiprocess Admin",
            role="SUPER_ADMIN",
            is_active=True
        )
        session.add(admin)
        session.commit()
        session.refresh(admin)

        server = MCPServer(
            organization_id=org.id,
            name="Multiprocess Server",
            identifier=f"mp-srv-{uuid.uuid4().hex[:6]}",
            transport_type="STDIO",
            command="python",
            env_vars={"DEPLOYMENT_STATE": "PREPARED", "DEPLOYMENT_HISTORY": []},
            is_enabled=True
        )
        session.add(server)
        session.commit()
        session.refresh(server)

        # Clear any existing kill switch
        session.query(IntegrationConfig).filter(
            IntegrationConfig.name == "GLOBAL_EMERGENCY_KILL_SWITCH"
        ).delete()
        session.commit()

        yield {
            "org_id": org.id,
            "admin_id": admin.id,
            "server_id": server.id,
            "db_url": reliability_db_url
        }
    finally:
        session.close()
        engine.dispose()


# ==============================================================================
# WORKSTREAM B: TRUE MULTIPROCESS RELIABILITY TESTS
# ==============================================================================

def test_01_cross_process_shutdown_propagation(reliability_db_url, test_setup_entities):
    """
    Test 1: Cross-process shutdown propagation.
    Process A triggers shutdown; Process B (independent OS process) observes the state
    and rejects protected operations.
    """
    ctx = mp.get_context("spawn")
    cmd_a, res_a = ctx.Queue(), ctx.Queue()
    cmd_b, res_b = ctx.Queue(), ctx.Queue()

    proc_a = ctx.Process(target=_multiprocess_executor_worker, args=(reliability_db_url, cmd_a, res_a))
    proc_b = ctx.Process(target=_multiprocess_executor_worker, args=(reliability_db_url, cmd_b, res_b))

    proc_a.start()
    proc_b.start()

    try:
        # Confirm both processes are operational
        tag_a, pid_a = res_a.get(timeout=8.0)
        tag_b, pid_b = res_b.get(timeout=8.0)
        assert tag_a == "READY" and tag_b == "READY"
        assert pid_a != pid_b, "Processes must have different PIDs"

        # Initially, Process B confirms shutdown is not active
        cmd_b.put(("CHECK_SHUTDOWN",))
        _, is_disabled_initial, _, _ = res_b.get(timeout=8.0)
        assert is_disabled_initial is False

        # Process A triggers emergency shutdown
        reason = "Operator Emergency Alert - Plant Gas Flare"
        cmd_a.put(("TRIGGER_SHUTDOWN", reason, "process_a@nexus.enterprise"))
        tag, shut_res, p_id = res_a.get(timeout=8.0)
        assert tag == "SHUTDOWN_OK"
        assert shut_res["status"] == "ENGAGED"

        # Process B queries status -> MUST observe ENGAGED from central database
        cmd_b.put(("CHECK_SHUTDOWN",))
        _, is_disabled_after, reason_observed, pid_observed = res_b.get(timeout=8.0)
        assert is_disabled_after is True
        assert reason_observed == reason
        assert pid_observed == pid_b

        # Process B attempts protected operations -> MUST be rejected
        cmd_b.put(("ATTEMPT_ACQUIRE_SESSION",))
        tag_acq, err_msg, _ = res_b.get(timeout=8.0)
        assert tag_acq == "ACQUIRE_BLOCKED"
        assert "emergency kill switch is engaged" in err_msg

        # Process B attempts transition to CANARY_AUTHORIZED -> MUST be blocked
        cmd_b.put(("ATTEMPT_CANARY_TRANSITION", test_setup_entities["server_id"], test_setup_entities["admin_id"], "CANARY_AUTHORIZED"))
        tag_tr, ok, msg, _, _ = res_b.get(timeout=8.0)
        assert tag_tr == "TRANSITION_RESULT"
        assert ok is False
        assert "emergency kill switch" in msg.lower()

    finally:
        cmd_a.put(("EXIT",))
        cmd_b.put(("EXIT",))
        proc_a.join(timeout=5.0)
        proc_b.join(timeout=5.0)


def test_02_shutdown_persistence_across_process_lifecycle(reliability_db_url, test_setup_entities):
    """
    Test 2: Shutdown persistence across process lifecycle.
    Process A triggers shutdown and terminates. Process C starts fresh and verifies
    shutdown remains effective.
    """
    ctx = mp.get_context("spawn")
    cmd_a, res_a = ctx.Queue(), ctx.Queue()

    # Step 1: Process A starts, engages shutdown, and terminates
    proc_a = ctx.Process(target=_multiprocess_executor_worker, args=(reliability_db_url, cmd_a, res_a))
    proc_a.start()
    res_a.get(timeout=8.0)  # READY

    cmd_a.put(("TRIGGER_SHUTDOWN", "Turbine Overheat Shutdown", "proc_a@nexus.enterprise"))
    tag, _, pid_a = res_a.get(timeout=8.0)
    assert tag == "SHUTDOWN_OK"

    # Terminate Process A
    cmd_a.put(("EXIT",))
    proc_a.join(timeout=5.0)
    assert not proc_a.is_alive()

    # Step 2: Process C starts fresh after Process A is dead
    cmd_c, res_c = ctx.Queue(), ctx.Queue()
    proc_c = ctx.Process(target=_multiprocess_executor_worker, args=(reliability_db_url, cmd_c, res_c))
    proc_c.start()

    try:
        res_c.get(timeout=8.0)  # READY

        # Process C must discover the persistent shutdown state
        cmd_c.put(("CHECK_SHUTDOWN",))
        _, is_disabled, reason, pid_c = res_c.get(timeout=8.0)
        assert is_disabled is True
        assert reason == "Turbine Overheat Shutdown"
        assert pid_c != pid_a

        # Process C protected operation fails closed
        cmd_c.put(("ATTEMPT_ACQUIRE_SESSION",))
        tag, err_msg, _ = res_c.get(timeout=8.0)
        assert tag == "ACQUIRE_BLOCKED"
        assert "emergency kill switch is engaged" in err_msg
    finally:
        cmd_c.put(("EXIT",))
        proc_c.join(timeout=5.0)


def test_03_concurrent_cross_process_shutdown_requests(reliability_db_url, test_setup_entities):
    """
    Test 3: Concurrent shutdown requests from independent processes.
    Both complete without deadlock or state corruption.
    """
    ctx = mp.get_context("spawn")
    cmd_1, res_1 = ctx.Queue(), ctx.Queue()
    cmd_2, res_2 = ctx.Queue(), ctx.Queue()

    proc_1 = ctx.Process(target=_multiprocess_executor_worker, args=(reliability_db_url, cmd_1, res_1))
    proc_2 = ctx.Process(target=_multiprocess_executor_worker, args=(reliability_db_url, cmd_2, res_2))

    proc_1.start()
    proc_2.start()

    try:
        res_1.get(timeout=8.0)  # READY
        res_2.get(timeout=8.0)  # READY

        # Trigger concurrent shutdowns
        cmd_1.put(("TRIGGER_SHUTDOWN", "Concurrent Alarm Site 1", "site1@nexus.enterprise"))
        cmd_2.put(("TRIGGER_SHUTDOWN", "Concurrent Alarm Site 2", "site2@nexus.enterprise"))

        tag1, r1, _ = res_1.get(timeout=8.0)
        tag2, r2, _ = res_2.get(timeout=8.0)

        assert tag1 == "SHUTDOWN_OK"
        assert tag2 == "SHUTDOWN_OK"
        assert r1["status"] == "ENGAGED"
        assert r2["status"] == "ENGAGED"

        # Verify database record is ENGAGED
        engine = create_engine(reliability_db_url)
        Session = sessionmaker(bind=engine)
        sess = Session()
        try:
            cfg = sess.query(IntegrationConfig).filter(
                IntegrationConfig.name == "GLOBAL_EMERGENCY_KILL_SWITCH"
            ).first()
            assert cfg is not None
            assert cfg.status == "ENGAGED"
        finally:
            sess.close()
            engine.dispose()
    finally:
        cmd_1.put(("EXIT",))
        cmd_2.put(("EXIT",))
        proc_1.join(timeout=5.0)
        proc_2.join(timeout=5.0)


def test_04_cross_process_recovery_and_reset_safety(reliability_db_url, test_setup_entities):
    """
    Test 4: Recovery and reset safety across processes.
    Process 1 disengages shutdown; Process 2 immediately observes restored capability.
    """
    ctx = mp.get_context("spawn")
    cmd_1, res_1 = ctx.Queue(), ctx.Queue()
    cmd_2, res_2 = ctx.Queue(), ctx.Queue()

    proc_1 = ctx.Process(target=_multiprocess_executor_worker, args=(reliability_db_url, cmd_1, res_1))
    proc_2 = ctx.Process(target=_multiprocess_executor_worker, args=(reliability_db_url, cmd_2, res_2))

    proc_1.start()
    proc_2.start()

    try:
        res_1.get(timeout=8.0)  # READY
        res_2.get(timeout=8.0)  # READY

        # Engage shutdown from Process 1
        cmd_1.put(("TRIGGER_SHUTDOWN", "Drill Alarm", "admin@nexus.enterprise"))
        res_1.get(timeout=8.0)

        # Process 2 observes engaged
        cmd_2.put(("CHECK_SHUTDOWN",))
        _, is_dis_1, _, _ = res_2.get(timeout=8.0)
        assert is_dis_1 is True

        # Process 1 disengages shutdown
        cmd_1.put(("TRIGGER_ENABLE", "admin@nexus.enterprise"))
        tag_en, en_res, _ = res_1.get(timeout=8.0)
        assert tag_en == "ENABLE_OK"
        assert en_res["status"] == "DISENGAGED"

        # Process 2 queries status -> MUST observe DISENGAGED
        cmd_2.put(("CHECK_SHUTDOWN",))
        _, is_dis_2, _, _ = res_2.get(timeout=8.0)
        assert is_dis_2 is False

        # Process 2 acquires session -> NOT blocked
        cmd_2.put(("ATTEMPT_ACQUIRE_SESSION",))
        tag_acq, ok, _ = res_2.get(timeout=8.0)
        assert tag_acq == "ACQUIRE_OK"
        assert ok is True
    finally:
        cmd_1.put(("EXIT",))
        cmd_2.put(("EXIT",))
        proc_1.join(timeout=5.0)
        proc_2.join(timeout=5.0)


# ==============================================================================
# WORKSTREAM C: ATOMIC AUDIT-EVENT RELIABILITY TESTS
# ==============================================================================

def test_05_atomic_audit_and_state_success(reliability_db_url, test_setup_entities):
    """
    Workstream C: Test 1 & 7: Successful protected operation produces expected audit record atomically.
    Metadata, actor role, and entity reference match exactly.
    """
    engine = create_engine(reliability_db_url)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    try:
        server = session.query(MCPServer).filter(MCPServer.id == test_setup_entities["server_id"]).first()
        admin = session.query(User).filter(User.id == test_setup_entities["admin_id"]).first()

        # Set to DISABLED
        server.env_vars = {"DEPLOYMENT_STATE": "DISABLED", "DEPLOYMENT_HISTORY": []}
        session.commit()

        initial_audit_count = session.query(AuditLog).filter(
            AuditLog.entity_id == server.id,
            AuditLog.action == "DEPLOYMENT_STATE_CHANGE"
        ).count()

        # Perform atomic transition DISABLED -> PREPARED
        ok, msg, new_st = DeploymentGovernanceService.transition_state(
            db=session,
            server=server,
            target_state=DeploymentState.PREPARED,
            actor=admin,
            reason="Workstream C Atomic Audit Verification"
        )
        assert ok is True
        assert new_st == DeploymentState.PREPARED

        # Verify in fresh independent session
        check_sess = Session()
        try:
            srv_check = check_sess.query(MCPServer).filter(MCPServer.id == server.id).first()
            assert DeploymentGovernanceService.get_server_state(srv_check) == DeploymentState.PREPARED

            final_audit_count = check_sess.query(AuditLog).filter(
                AuditLog.entity_id == server.id,
                AuditLog.action == "DEPLOYMENT_STATE_CHANGE"
            ).count()
            assert final_audit_count == initial_audit_count + 1

            audit_entry = check_sess.query(AuditLog).filter(
                AuditLog.entity_id == server.id,
                AuditLog.action == "DEPLOYMENT_STATE_CHANGE"
            ).order_by(AuditLog.timestamp.desc()).first()

            assert audit_entry.user_name == admin.full_name
            assert audit_entry.role == admin.role
            assert "Workstream C Atomic Audit Verification" in audit_entry.details
            assert audit_entry.diff["from"] == "DISABLED"
            assert audit_entry.diff["to"] == "PREPARED"
        finally:
            check_sess.close()
    finally:
        session.close()
        engine.dispose()


def test_06_atomic_audit_rollback_on_failure(reliability_db_url, test_setup_entities):
    """
    Workstream C: Test 2 & 3: Failed operation rolls back both state change AND audit record.
    No misleading audit record is persisted when the operation fails.
    """
    from unittest.mock import patch

    engine = create_engine(reliability_db_url)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    try:
        server = session.query(MCPServer).filter(MCPServer.id == test_setup_entities["server_id"]).first()
        admin = session.query(User).filter(User.id == test_setup_entities["admin_id"]).first()

        server.env_vars = {"DEPLOYMENT_STATE": "PREPARED", "DEPLOYMENT_HISTORY": []}
        session.commit()

        initial_audits = session.query(AuditLog).filter(
            AuditLog.entity_id == server.id,
            AuditLog.action == "DEPLOYMENT_STATE_CHANGE"
        ).count()

        # Simulate unexpected commit failure or database crash right before transaction commits
        with patch.object(session, "commit", side_effect=Exception("Disk Full Simulation / Commit Aborted")):
            ok, msg, current_st = DeploymentGovernanceService.transition_state(
                db=session,
                server=server,
                target_state=DeploymentState.ELIGIBLE,
                actor=admin,
                reason="Simulated Failing Transition"
            )
            assert ok is False
            assert "Database transaction failed" in msg

        # Verify in a separate session that state was NOT modified and audit record was NOT persisted
        check_sess = Session()
        try:
            srv_check = check_sess.query(MCPServer).filter(MCPServer.id == server.id).first()
            assert DeploymentGovernanceService.get_server_state(srv_check) == DeploymentState.PREPARED

            final_audits = check_sess.query(AuditLog).filter(
                AuditLog.entity_id == server.id,
                AuditLog.action == "DEPLOYMENT_STATE_CHANGE"
            ).count()
            assert final_audits == initial_audits, "Audit log must NOT exist if the transition failed"
        finally:
            check_sess.close()
    finally:
        session.close()
        engine.dispose()


def test_07_concurrent_audit_events_consistency(reliability_db_url, test_setup_entities):
    """
    Workstream C: Test 5: Concurrent operations do not produce inconsistent or interleaved audit states.
    """
    import concurrent.futures

    engine = create_engine(reliability_db_url, pool_size=10, max_overflow=10)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    server_id = test_setup_entities["server_id"]
    admin_id = test_setup_entities["admin_id"]

    def record_audit(worker_idx: int):
        sess = Session()
        try:
            adm = sess.query(User).filter(User.id == admin_id).first()
            log = AuditService.record(
                db=sess,
                action="CONCURRENT_RELIABILITY_TEST",
                entity_type="SERVER",
                entity_id=server_id,
                user_name=adm.full_name,
                role=adm.role,
                details=f"Worker {worker_idx} concurrent audit entry",
                diff={"worker": worker_idx},
                auto_commit=True
            )
            return True, log.id
        except Exception as e:
            sess.rollback()
            return False, str(e)
        finally:
            sess.close()

    # 10 concurrent threads recording audits
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(record_audit, i) for i in range(10)]

    results = [f.result() for f in futures]
    successes = [r for r in results if r[0] is True]
    assert len(successes) == 10, f"All 10 concurrent audit writes must succeed, got {results}"

    # Verify all 10 entries exist in the database with matching entity_id
    verify_sess = Session()
    try:
        entries = verify_sess.query(AuditLog).filter(
            AuditLog.entity_id == server_id,
            AuditLog.action == "CONCURRENT_RELIABILITY_TEST"
        ).all()
        assert len(entries) == 10
        workers_found = set(e.diff["worker"] for e in entries)
        assert workers_found == set(range(10))
    finally:
        verify_sess.close()
        engine.dispose()
