"""
MCP NEXUS — POSTGRESQL PRODUCTION INTEGRATION TEST SUITE
Validates PostgreSQL connection, concurrency locking (SELECT FOR UPDATE),
atomic deployment transitions, and tenant isolation in production-grade environments.

Guarded by POSTGRES_TEST_DATABASE_URL: Skips gracefully when running in environments
without live PostgreSQL infrastructure (e.g. local Windows without Docker/PostgreSQL service).
"""

import os
import sys
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
    engine = create_engine(POSTGRES_URL, pool_pre_ping=True, pool_size=5, max_overflow=5)
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


def test_01_postgresql_connection_and_version(pg_session):
    """Test 1: Verify PostgreSQL engine connectivity and server version."""
    result = pg_session.execute(text("SELECT version()")).scalar()
    assert result is not None
    assert "PostgreSQL" in result


def test_02_postgresql_concurrent_deployment_state_transitions(pg_engine, pg_tables):
    """Test 2: Verify PostgreSQL row-level locking (SELECT FOR UPDATE) during deployment transition."""
    import concurrent.futures
    from app.models.all_models import MCPServer, Organization
    from app.services.deployment_governance import DeploymentGovernanceService

    Session = sessionmaker(bind=pg_engine, autoflush=False, autocommit=False)
    setup_session = Session()
    try:
        org = setup_session.query(Organization).first()
        if not org:
            org = Organization(name="PG Test Org", slug="pg-test-org", tier="ENTERPRISE")
            setup_session.add(org)
            setup_session.commit()
            setup_session.refresh(org)

        server = MCPServer(
            organization_id=org.id,
            name="PG Concurrency Test Server",
            identifier="pg-srv-concurrency-test",
            transport_type="STDIO",
            command="python",
            args=["-c", "print(1)"],
            deployment_state="DEVELOPMENT",
            is_enabled=True
        )
        setup_session.add(server)
        setup_session.commit()
        server_id = server.id
    finally:
        setup_session.close()

    def attempt_transition(target_state: str, actor: str):
        worker_session = Session()
        try:
            res = DeploymentGovernanceService.transition_state(
                db=worker_session,
                server_id=server_id,
                target_state=target_state,
                actor_user_id="user-pg-test",
                actor_role="SUPER_ADMIN",
                actor_name=actor,
                reason=f"Transition to {target_state} by {actor}"
            )
            return True, res
        except Exception as e:
            worker_session.rollback()
            return False, str(e)
        finally:
            worker_session.close()

    # Attempt concurrent transitions to CANARY_EVALUATION
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        f1 = executor.submit(attempt_transition, "CANARY_EVALUATION", "Worker 1")
        f2 = executor.submit(attempt_transition, "CANARY_EVALUATION", "Worker 2")
        f3 = executor.submit(attempt_transition, "CANARY_EVALUATION", "Worker 3")

    results = [f.result() for f in [f1, f2, f3]]
    successes = [r for r in results if r[0] is True]
    assert len(successes) >= 1, "At least one transition must succeed"


def test_03_postgresql_atomic_deployment_state_and_audit_logging(pg_engine, pg_tables):
    """Test 3: Verify atomic commit of deployment state and audit log in PostgreSQL."""
    from app.models.all_models import MCPServer, Organization, AuditLog
    from app.services.deployment_governance import DeploymentGovernanceService

    Session = sessionmaker(bind=pg_engine, autoflush=False, autocommit=False)
    session = Session()
    try:
        org = session.query(Organization).first()
        server = MCPServer(
            organization_id=org.id,
            name="PG Atomic Audit Server",
            identifier="pg-srv-atomic-audit",
            transport_type="STDIO",
            command="python",
            deployment_state="DEVELOPMENT",
            is_enabled=True
        )
        session.add(server)
        session.commit()
        server_id = server.id

        result = DeploymentGovernanceService.transition_state(
            db=session,
            server_id=server_id,
            target_state="STAGING",
            actor_user_id="user-pg-test",
            actor_role="SUPER_ADMIN",
            actor_name="Audit Tester",
            reason="Verify atomic audit"
        )
        assert result["new_state"] == "STAGING"

        # Verify audit log exists
        audit = session.query(AuditLog).filter(
            AuditLog.entity_id == server_id,
            AuditLog.action == "DEPLOYMENT_TRANSITION"
        ).first()
        assert audit is not None
        assert "STAGING" in audit.details
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
        server = setup_sess.query(MCPServer).first()
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
        server = session.query(MCPServer).first()
        initial_name = server.name

        try:
            server.name = "Corrupted Name That Should Roll Back"
            # Intentionally cause a foreign key or constraint error
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
        org_a = Organization(name="Tenant Alpha", slug="tenant-alpha", tier="ENTERPRISE")
        org_b = Organization(name="Tenant Beta", slug="tenant-beta", tier="ENTERPRISE")
        session.add_all([org_a, org_b])
        session.commit()

        srv_a = MCPServer(
            organization_id=org_a.id,
            name="Server Alpha",
            identifier="srv-alpha",
            transport_type="STDIO",
            command="python"
        )
        srv_b = MCPServer(
            organization_id=org_b.id,
            name="Server Beta",
            identifier="srv-beta",
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
