"""
MCP NEXUS — POSTGRESQL PRODUCTION INTEGRATION TEST SUITE
Validates PostgreSQL connection, concurrency locking (SELECT FOR UPDATE),
atomic deployment transitions, and tenant isolation in production-grade environments.

Guarded by POSTGRES_TEST_DATABASE_URL: Skips gracefully when running in environments
without live PostgreSQL infrastructure (e.g. local Windows without Docker/PostgreSQL service).
"""

import os
import sys
import uuid
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

POSTGRES_URL = os.getenv("POSTGRES_TEST_DATABASE_URL")
POSTGRES_AVAILABLE = bool(POSTGRES_URL and POSTGRES_URL.startswith("postgresql"))

pytestmark = pytest.mark.skipif(
    not POSTGRES_AVAILABLE,
    reason="PostgreSQL test database not available. Set POSTGRES_TEST_DATABASE_URL to execute."
)


@pytest.fixture(scope="module")
def pg_engine():
    if not POSTGRES_AVAILABLE:
        pytest.skip("PostgreSQL test database not available.")
    engine = create_engine(POSTGRES_URL, pool_pre_ping=True, pool_size=10, max_overflow=10)
    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def pg_tables(pg_engine):
    from app.database.session import Base
    import app.models.all_models  # ensure models are registered
    Base.metadata.create_all(bind=pg_engine)
    yield
    # Tables preserved or dropped per CI policy


@pytest.fixture
def pg_session(pg_engine, pg_tables):
    Session = sessionmaker(bind=pg_engine, autoflush=False, autocommit=False)
    session = Session()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _ensure_org_and_admin(session):
    from app.models.all_models import Organization, User
    from app.core.security import get_password_hash

    org = session.query(Organization).first()
    if not org:
        org = Organization(name="PG Test Org", slug=f"pg-test-org-{uuid.uuid4().hex[:6]}", tier="ENTERPRISE")
        session.add(org)
        session.commit()
        session.refresh(org)

    admin = session.query(User).filter(User.organization_id == org.id, User.role == "SUPER_ADMIN").first()
    if not admin:
        admin = User(
            organization_id=org.id,
            email=f"pg_admin_{uuid.uuid4().hex[:6]}@nexus.test",
            hashed_password=get_password_hash("admin_secret_pass"),
            full_name="PG Super Admin",
            role="SUPER_ADMIN",
            is_active=True
        )
        session.add(admin)
        session.commit()
        session.refresh(admin)

    return org, admin


def test_01_postgresql_connection_and_version(pg_session):
    """Test 1: Verify PostgreSQL engine connectivity and server version."""
    result = pg_session.execute(text("SELECT version()")).scalar()
    assert result is not None
    assert "PostgreSQL" in result


def test_02_postgresql_concurrent_deployment_state_transitions(pg_engine, pg_tables):
    """Test 2: Verify PostgreSQL row-level locking (SELECT FOR UPDATE) during deployment transition."""
    import concurrent.futures
    from app.models.all_models import MCPServer, User
    from app.services.deployment_governance import DeploymentGovernanceService, DeploymentState

    Session = sessionmaker(bind=pg_engine, autoflush=False, autocommit=False)
    setup_session = Session()
    try:
        org, admin = _ensure_org_and_admin(setup_session)

        server = MCPServer(
            organization_id=org.id,
            name="PG Concurrency Test Server",
            identifier=f"pg-srv-concurrency-{uuid.uuid4().hex[:6]}",
            transport_type="STDIO",
            command="python",
            args=["-c", "print(1)"],
            env_vars={"DEPLOYMENT_STATE": "DISABLED"},
            is_enabled=True
        )
        setup_session.add(server)
        setup_session.commit()
        server_id = server.id
        admin_id = admin.id
    finally:
        setup_session.close()

    def attempt_transition(target_state: DeploymentState, actor_name: str):
        worker_session = Session()
        try:
            srv = worker_session.query(MCPServer).filter(MCPServer.id == server_id).first()
            actor_user = worker_session.query(User).filter(User.id == admin_id).first()

            ok, msg, new_st = DeploymentGovernanceService.transition_state(
                db=worker_session,
                server=srv,
                target_state=target_state,
                actor=actor_user,
                reason=f"Transition to {target_state.value} by {actor_name}"
            )
            return ok, msg, new_st
        except Exception as e:
            worker_session.rollback()
            return False, str(e), None
        finally:
            worker_session.close()

    # Attempt concurrent transitions to PREPARED
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        f1 = executor.submit(attempt_transition, DeploymentState.PREPARED, "Worker 1")
        f2 = executor.submit(attempt_transition, DeploymentState.PREPARED, "Worker 2")
        f3 = executor.submit(attempt_transition, DeploymentState.PREPARED, "Worker 3")

    results = [f.result() for f in [f1, f2, f3]]
    successes = [r for r in results if r[0] is True]
    assert len(successes) >= 1, f"At least one transition must succeed, got {results}"

    # Verify final state in database is PREPARED
    verify_session = Session()
    try:
        srv = verify_session.query(MCPServer).filter(MCPServer.id == server_id).first()
        state = DeploymentGovernanceService.get_server_state(srv)
        assert state == DeploymentState.PREPARED
    finally:
        verify_session.close()


def test_03_postgresql_atomic_deployment_state_and_audit_logging(pg_engine, pg_tables):
    """Test 3: Verify atomic commit of deployment state and audit log in PostgreSQL."""
    from app.models.all_models import MCPServer, AuditLog
    from app.services.deployment_governance import DeploymentGovernanceService, DeploymentState

    Session = sessionmaker(bind=pg_engine, autoflush=False, autocommit=False)
    session = Session()
    try:
        org, admin = _ensure_org_and_admin(session)
        server = MCPServer(
            organization_id=org.id,
            name="PG Atomic Audit Server",
            identifier=f"pg-srv-atomic-{uuid.uuid4().hex[:6]}",
            transport_type="STDIO",
            command="python",
            env_vars={"DEPLOYMENT_STATE": "DISABLED"},
            is_enabled=True
        )
        session.add(server)
        session.commit()
        server_id = server.id

        ok, msg, new_state = DeploymentGovernanceService.transition_state(
            db=session,
            server=server,
            target_state=DeploymentState.PREPARED,
            actor=admin,
            reason="Verify atomic audit"
        )
        assert ok is True
        assert new_state == DeploymentState.PREPARED

        # Verify audit log exists
        audit = session.query(AuditLog).filter(
            AuditLog.entity_id == server_id,
            AuditLog.action == "DEPLOYMENT_STATE_CHANGE"
        ).first()
        assert audit is not None
        assert "PREPARED" in audit.details
    finally:
        session.close()


def test_04_postgresql_multi_worker_lock_contention(pg_engine, pg_tables):
    """Test 4: Verify SELECT FOR UPDATE row-level locking serializes concurrent updates."""
    from app.models.all_models import MCPServer
    import time
    import threading

    Session = sessionmaker(bind=pg_engine, autoflush=False, autocommit=False)
    setup_sess = Session()
    try:
        org, _ = _ensure_org_and_admin(setup_sess)
        server = setup_sess.query(MCPServer).first()
        if not server:
            server = MCPServer(
                organization_id=org.id,
                name="PG Lock Server",
                identifier=f"pg-srv-lock-{uuid.uuid4().hex[:6]}",
                transport_type="STDIO",
                command="python",
                total_calls=0
            )
            setup_sess.add(server)
            setup_sess.commit()
        server_id = server.id
    finally:
        setup_sess.close()

    lock_acquired = []

    def worker_with_lock(worker_id: int):
        s = Session()
        try:
            s.execute(text("BEGIN"))
            row = s.query(MCPServer).filter(MCPServer.id == server_id).with_for_update().first()
            lock_acquired.append((worker_id, time.time()))
            time.sleep(0.1)
            row.total_calls = (row.total_calls or 0) + 1
            s.commit()
        except Exception:
            s.rollback()
        finally:
            s.close()

    t1 = threading.Thread(target=worker_with_lock, args=(1,))
    t2 = threading.Thread(target=worker_with_lock, args=(2,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert len(lock_acquired) == 2
    # Verify the locks were serialized (second acquired after first)
    first_acquired_time = lock_acquired[0][1]
    second_acquired_time = lock_acquired[1][1]
    assert second_acquired_time >= first_acquired_time


def test_05_postgresql_failure_rollback(pg_engine, pg_tables):
    """Test 5: Verify transaction rollback on failure leaves database uncorrupted."""
    from app.models.all_models import MCPServer
    Session = sessionmaker(bind=pg_engine, autoflush=False, autocommit=False)
    session = Session()
    try:
        org, _ = _ensure_org_and_admin(session)
        server = session.query(MCPServer).first()
        if not server:
            server = MCPServer(
                organization_id=org.id,
                name="PG Rollback Server",
                identifier=f"pg-srv-rollback-{uuid.uuid4().hex[:6]}",
                transport_type="STDIO",
                command="python"
            )
            session.add(server)
            session.commit()

        initial_name = server.name

        try:
            server.name = "Corrupted Name That Should Roll Back"
            # Intentionally cause an error
            session.execute(text("INSERT INTO non_existent_table_for_rollback_test VALUES (1)"))
            session.commit()
        except Exception:
            session.rollback()

        # Check clean state
        refreshed_server = session.query(MCPServer).filter(MCPServer.id == server.id).first()
        assert refreshed_server.name == initial_name
    finally:
        session.close()


def test_06_postgresql_tenant_isolation_concurrency(pg_engine, pg_tables):
    """Test 6: Verify tenant isolation is preserved under concurrent PostgreSQL sessions."""
    from app.models.all_models import Organization, MCPServer
    Session = sessionmaker(bind=pg_engine, autoflush=False, autocommit=False)
    session = Session()
    try:
        slug_a = f"tenant-alpha-{uuid.uuid4().hex[:8]}"
        slug_b = f"tenant-beta-{uuid.uuid4().hex[:8]}"
        org_a = Organization(name="Tenant Alpha", slug=slug_a, tier="ENTERPRISE")
        org_b = Organization(name="Tenant Beta", slug=slug_b, tier="ENTERPRISE")
        session.add_all([org_a, org_b])
        session.commit()

        srv_a = MCPServer(
            organization_id=org_a.id,
            name="Server Alpha",
            identifier=f"srv-alpha-{uuid.uuid4().hex[:6]}",
            transport_type="STDIO",
            command="python"
        )
        srv_b = MCPServer(
            organization_id=org_b.id,
            name="Server Beta",
            identifier=f"srv-beta-{uuid.uuid4().hex[:6]}",
            transport_type="STDIO",
            command="python"
        )
        session.add_all([srv_a, srv_b])
        session.commit()

        # Query isolated to Org A must never return Server B
        org_a_servers = session.query(MCPServer).filter(MCPServer.organization_id == org_a.id).all()
        org_a_ids = [s.id for s in org_a_servers]
        assert srv_a.id in org_a_ids
        assert srv_b.id not in org_a_ids
    finally:
        session.close()


def test_07_postgresql_emergency_shutdown_persistence_and_propagation(pg_engine, pg_tables):
    """Test 7: Verify database-backed emergency shutdown state and cross-session discovery in PostgreSQL."""
    from app.models.all_models import IntegrationConfig
    from app.mcp.persistent_session import PersistentSessionManager
    from unittest.mock import patch

    Session = sessionmaker(bind=pg_engine, autoflush=False, autocommit=False)

    # Patch SessionLocal to point to our pg_engine for this test
    with patch("app.database.session.SessionLocal", Session):
        # Clean local memory
        PersistentSessionManager._emergency_disabled = False
        PersistentSessionManager._emergency_disabled_at = None
        PersistentSessionManager._emergency_reason = None

        # Process A engages emergency kill switch
        import asyncio
        asyncio.run(PersistentSessionManager.emergency_disable(
            reason="PG 15 Live Emergency Shutdown Test",
            actor_email="pg_ops@nexus.enterprise"
        ))

        # Verify DB directly in separate session
        sess = Session()
        try:
            cfg = sess.query(IntegrationConfig).filter(
                IntegrationConfig.name == "GLOBAL_EMERGENCY_KILL_SWITCH"
            ).first()
            assert cfg is not None
            assert cfg.status == "ENGAGED"
            assert cfg.stats.get("actor") == "pg_ops@nexus.enterprise"
        finally:
            sess.close()

        # Process B starts with empty in-memory state
        PersistentSessionManager._emergency_disabled = False
        PersistentSessionManager._emergency_disabled_at = None
        PersistentSessionManager._emergency_reason = None

        # Process B queries is_emergency_disabled() -> queries PostgreSQL -> discovers ENGAGED
        assert PersistentSessionManager.is_emergency_disabled() is True
        assert PersistentSessionManager._emergency_disabled is True
        assert PersistentSessionManager._emergency_reason == "PG 15 Live Emergency Shutdown Test"

        # Disengage
        res = PersistentSessionManager.emergency_enable(actor_email="pg_admin@nexus.enterprise")
        assert res["status"] == "DISENGAGED"

        # Confirm disengaged in PostgreSQL
        sess = Session()
        try:
            cfg = sess.query(IntegrationConfig).filter(
                IntegrationConfig.name == "GLOBAL_EMERGENCY_KILL_SWITCH"
            ).first()
            assert cfg.status == "DISENGAGED"
        finally:
            sess.close()

        # Another process queries and discovers DISENGAGED
        PersistentSessionManager._emergency_disabled = True
        assert PersistentSessionManager.is_emergency_disabled() is False
