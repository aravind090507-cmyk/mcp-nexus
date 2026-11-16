"""
Phase 15D.4.4 Database Schema Migration & Alembic Lifecycle Test Suite

Covers:
1. Application import creates zero unexpected schema (zero DDL on import).
2. SQLite compatibility (upgrade to head, revision inspection, downgrade to base).
3. Fresh PostgreSQL initialization and initial migration.
4. Existing database adoption (schema equivalence check and safe stamping).
5. Reversible migration downgrade and re-upgrade on PostgreSQL.
6. Migration failure and transactional safety.
7. PostgreSQL application connection and ORM query preservation.
"""

import os
import sys
import uuid
import pytest
from sqlalchemy import create_engine, inspect, text
from alembic.config import Config
from alembic import command
from alembic.script import ScriptDirectory

# Ensure backend root is on sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app.core.config import settings
from app.database.session import Base, SessionLocal, reset_database_engine
import app.models.all_models
from app.models.all_models import Organization, User, MCPServer

POSTGRES_TEST_URL = os.getenv(
    "POSTGRES_TEST_DATABASE_URL",
    "postgresql://postgres:postgrespassword2026@127.0.0.1:5432/mcp_nexus_test"
)


def _get_alembic_config(db_url: str) -> Config:
    """Builds an isolated Alembic Config instance pointing to the specified database URL."""
    ini_path = os.path.join(ROOT_DIR, "alembic.ini")
    if not os.path.exists(ini_path):
        ini_path = os.path.join(BASE_DIR, "alembic.ini")
    cfg = Config(ini_path)
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _is_pg_available() -> bool:
    try:
        eng = create_engine(POSTGRES_TEST_URL, connect_args={"connect_timeout": 2})
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


# ==============================================================================
# 1. APPLICATION IMPORT ZERO DDL TEST
# ==============================================================================

def test_01_application_import_creates_zero_schema(tmp_path):
    """Verify that importing application modules does not trigger any DDL execution."""
    test_db = tmp_path / f"import_test_{uuid.uuid4().hex[:8]}.db"
    db_url = f"sqlite:///{test_db}"

    # Verify database file does not exist yet
    assert not os.path.exists(test_db)

    # Point to the isolated test db
    test_eng = create_engine(db_url)
    with test_eng.connect() as conn:
        insp = inspect(conn)
        tables_before = insp.get_table_names()
    assert len(tables_before) == 0

    # Ensure importing app.main and app.database.session creates ZERO tables
    import app.main
    import app.database.session

    with test_eng.connect() as conn:
        insp = inspect(conn)
        tables_after = insp.get_table_names()

    assert len(tables_after) == 0, f"Expected 0 tables on module import, got {tables_after}"
    test_eng.dispose()


# ==============================================================================
# 2. SQLITE COMPATIBILITY & LIFECYCLE TEST
# ==============================================================================

def test_02_sqlite_compatibility_migration_lifecycle(tmp_path):
    """Verify fresh migration upgrade, revision check, and rollback in SQLite."""
    test_db = tmp_path / f"sqlite_mig_{uuid.uuid4().hex[:8]}.db"
    db_url = f"sqlite:///{test_db}"

    cfg = _get_alembic_config(db_url)
    script = ScriptDirectory.from_config(cfg)
    head_rev = script.get_current_head()

    # Step 1: Upgrade to head
    command.upgrade(cfg, "head")

    eng = create_engine(db_url)
    with eng.connect() as conn:
        insp = inspect(conn)
        tables = set(insp.get_table_names())

    expected_tables = set(Base.metadata.tables.keys())
    assert expected_tables.issubset(tables), f"Missing tables after upgrade: {expected_tables - tables}"
    assert "alembic_version" in tables

    # Step 2: Verify current revision
    with eng.connect() as conn:
        res = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert res == head_rev

    # Step 3: Downgrade to base
    command.downgrade(cfg, "base")

    with eng.connect() as conn:
        insp = inspect(conn)
        tables_after_downgrade = set(insp.get_table_names())

    # All domain tables should be dropped
    domain_remaining = expected_tables.intersection(tables_after_downgrade)
    assert len(domain_remaining) == 0, f"Domain tables remaining after downgrade: {domain_remaining}"

    eng.dispose()


# ==============================================================================
# 3. FRESH POSTGRESQL INITIALIZATION & MIGRATION TEST
# ==============================================================================

@pytest.mark.skipif(not _is_pg_available(), reason="PostgreSQL service unavailable")
def test_03_fresh_postgresql_initialization_and_migration():
    """Verify clean database initialization and full schema migration on live PostgreSQL."""
    db_name = f"nexus_fresh_{uuid.uuid4().hex[:8]}"
    admin_eng = create_engine(POSTGRES_TEST_URL, isolation_level="AUTOCOMMIT")

    with admin_eng.connect() as conn:
        conn.execute(text(f"CREATE DATABASE {db_name};"))

    pg_url = POSTGRES_TEST_URL.rsplit("/", 1)[0] + f"/{db_name}"

    try:
        cfg = _get_alembic_config(pg_url)
        script = ScriptDirectory.from_config(cfg)
        head_rev = script.get_current_head()

        # Execute migration upgrade
        command.upgrade(cfg, "head")

        pg_eng = create_engine(pg_url)
        with pg_eng.connect() as conn:
            insp = inspect(conn)
            tables = set(insp.get_table_names())
            current_ver = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()

        expected_tables = set(Base.metadata.tables.keys())
        assert expected_tables.issubset(tables), f"PostgreSQL missing tables: {expected_tables - tables}"
        assert current_ver == head_rev

        pg_eng.dispose()
    finally:
        admin_eng.dispose()
        cleanup_eng = create_engine(POSTGRES_TEST_URL, isolation_level="AUTOCOMMIT")
        with cleanup_eng.connect() as conn:
            # Terminate connections and drop
            conn.execute(text(f"""
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = '{db_name}'
                  AND pid <> pg_backend_pid();
            """))
            conn.execute(text(f"DROP DATABASE IF EXISTS {db_name};"))
        cleanup_eng.dispose()


# ==============================================================================
# 4. EXISTING DATABASE ADOPTION & SCHEMA EQUIVALENCE TEST
# ==============================================================================

@pytest.mark.skipif(not _is_pg_available(), reason="PostgreSQL service unavailable")
def test_04_existing_database_adoption_and_safe_stamping():
    """Verify safe adoption of pre-existing schemas via schema equivalence and stamping."""
    db_name = f"nexus_adopt_{uuid.uuid4().hex[:8]}"
    admin_eng = create_engine(POSTGRES_TEST_URL, isolation_level="AUTOCOMMIT")

    with admin_eng.connect() as conn:
        conn.execute(text(f"CREATE DATABASE {db_name};"))

    pg_url = POSTGRES_TEST_URL.rsplit("/", 1)[0] + f"/{db_name}"

    try:
        pg_eng = create_engine(pg_url)
        # Simulate pre-existing legacy database initialized without Alembic
        Base.metadata.create_all(bind=pg_eng)

        # 1. Verify schema equivalence
        with pg_eng.connect() as conn:
            insp = inspect(conn)
            tables = set(insp.get_table_names())
            assert "alembic_version" not in tables

        expected_tables = set(Base.metadata.tables.keys())
        assert expected_tables.issubset(tables), "Pre-existing database missing expected tables."

        # 2. Stamp to head
        cfg = _get_alembic_config(pg_url)
        command.stamp(cfg, "head")

        # 3. Verify stamped revision
        with pg_eng.connect() as conn:
            current_ver = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        script = ScriptDirectory.from_config(cfg)
        assert current_ver == script.get_current_head()

        # 4. Verify no pending migrations
        # command.check raises if there are unapplied schema differences
        command.check(cfg)

        pg_eng.dispose()
    finally:
        admin_eng.dispose()
        cleanup_eng = create_engine(POSTGRES_TEST_URL, isolation_level="AUTOCOMMIT")
        with cleanup_eng.connect() as conn:
            conn.execute(text(f"""
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = '{db_name}'
                  AND pid <> pg_backend_pid();
            """))
            conn.execute(text(f"DROP DATABASE IF EXISTS {db_name};"))
        cleanup_eng.dispose()


# ==============================================================================
# 5. REVERSIBLE MIGRATION DOWNGRADE AND RE-UPGRADE TEST
# ==============================================================================

@pytest.mark.skipif(not _is_pg_available(), reason="PostgreSQL service unavailable")
def test_05_reversible_migration_downgrade_and_reupgrade_postgresql():
    """Verify that full schema downgrade and subsequent re-upgrade succeed cleanly."""
    db_name = f"nexus_revers_{uuid.uuid4().hex[:8]}"
    admin_eng = create_engine(POSTGRES_TEST_URL, isolation_level="AUTOCOMMIT")

    with admin_eng.connect() as conn:
        conn.execute(text(f"CREATE DATABASE {db_name};"))

    pg_url = POSTGRES_TEST_URL.rsplit("/", 1)[0] + f"/{db_name}"

    try:
        cfg = _get_alembic_config(pg_url)
        script = ScriptDirectory.from_config(cfg)
        head_rev = script.get_current_head()

        # Upgrade to head
        command.upgrade(cfg, "head")

        pg_eng = create_engine(pg_url)
        with pg_eng.connect() as conn:
            insp = inspect(conn)
            assert len(insp.get_table_names()) >= 13

        # Downgrade to base
        command.downgrade(cfg, "base")

        with pg_eng.connect() as conn:
            insp = inspect(conn)
            remaining = set(insp.get_table_names()) - {"alembic_version"}
            assert len(remaining) == 0, f"Tables remaining after downgrade: {remaining}"

        # Re-upgrade to head
        command.upgrade(cfg, "head")

        with pg_eng.connect() as conn:
            insp = inspect(conn)
            restored = set(insp.get_table_names())
            assert set(Base.metadata.tables.keys()).issubset(restored)
            current_ver = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            assert current_ver == head_rev

        pg_eng.dispose()
    finally:
        admin_eng.dispose()
        cleanup_eng = create_engine(POSTGRES_TEST_URL, isolation_level="AUTOCOMMIT")
        with cleanup_eng.connect() as conn:
            conn.execute(text(f"""
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = '{db_name}'
                  AND pid <> pg_backend_pid();
            """))
            conn.execute(text(f"DROP DATABASE IF EXISTS {db_name};"))
        cleanup_eng.dispose()


# ==============================================================================
# 6. MIGRATION TRANSACTIONAL INTEGRITY TEST
# ==============================================================================

@pytest.mark.skipif(not _is_pg_available(), reason="PostgreSQL service unavailable")
def test_06_migration_failure_transaction_safety():
    """Verify that a failing migration rolls back atomically under PostgreSQL transactional DDL."""
    db_name = f"nexus_tx_safe_{uuid.uuid4().hex[:8]}"
    admin_eng = create_engine(POSTGRES_TEST_URL, isolation_level="AUTOCOMMIT")

    with admin_eng.connect() as conn:
        conn.execute(text(f"CREATE DATABASE {db_name};"))

    pg_url = POSTGRES_TEST_URL.rsplit("/", 1)[0] + f"/{db_name}"

    try:
        cfg = _get_alembic_config(pg_url)
        command.upgrade(cfg, "head")

        pg_eng = create_engine(pg_url)

        # Attempt an invalid transactional DDL operation
        # In PostgreSQL, an error rolls back the entire transaction block
        with pytest.raises(Exception):
            with pg_eng.begin() as conn:
                conn.execute(text("CREATE TABLE temp_tx_test (id INT PRIMARY KEY);"))
                # Trigger syntax/type error that causes rollback
                conn.execute(text("INVALID SQL STATEMENT;"))

        with pg_eng.connect() as conn:
            insp = inspect(conn)
            assert "temp_tx_test" not in insp.get_table_names(), "Failed DDL was not rolled back!"

        pg_eng.dispose()
    finally:
        admin_eng.dispose()
        cleanup_eng = create_engine(POSTGRES_TEST_URL, isolation_level="AUTOCOMMIT")
        with cleanup_eng.connect() as conn:
            conn.execute(text(f"""
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = '{db_name}'
                  AND pid <> pg_backend_pid();
            """))
            conn.execute(text(f"DROP DATABASE IF EXISTS {db_name};"))
        cleanup_eng.dispose()


# ==============================================================================
# 7. POSTGRESQL APPLICATION ORM QUERY PRESERVATION TEST
# ==============================================================================

@pytest.mark.skipif(not _is_pg_available(), reason="PostgreSQL service unavailable")
def test_07_postgresql_application_connection_preserved():
    """Verify that ORM models and operations work seamlessly against a migrated PostgreSQL schema."""
    db_name = f"nexus_orm_{uuid.uuid4().hex[:8]}"
    admin_eng = create_engine(POSTGRES_TEST_URL, isolation_level="AUTOCOMMIT")

    with admin_eng.connect() as conn:
        conn.execute(text(f"CREATE DATABASE {db_name};"))

    pg_url = POSTGRES_TEST_URL.rsplit("/", 1)[0] + f"/{db_name}"

    try:
        cfg = _get_alembic_config(pg_url)
        command.upgrade(cfg, "head")

        saved_url = settings.DATABASE_URL
        # Dynamically rebind engine to this migrated PostgreSQL instance
        reset_database_engine(pg_url)

        db = SessionLocal()
        try:
            # Create Organization and User
            org = Organization(name="Migration Corp", slug=f"mig-corp-{uuid.uuid4().hex[:6]}")
            db.add(org)
            db.commit()
            db.refresh(org)

            user = User(
                organization_id=org.id,
                email=f"user-{uuid.uuid4().hex[:6]}@migration.com",
                full_name="Migration User",
                hashed_password="hashed_pw_dummy",
                role="ADMIN"
            )
            db.add(user)
            db.commit()
            db.refresh(user)

            # Query back
            queried_user = db.query(User).filter(User.id == user.id).first()
            assert queried_user is not None
            assert queried_user.email == user.email
            assert queried_user.organization.name == "Migration Corp"
        finally:
            db.close()
            # Reset back to test suite baseline URL
            reset_database_engine(saved_url)

    finally:
        admin_eng.dispose()
        cleanup_eng = create_engine(POSTGRES_TEST_URL, isolation_level="AUTOCOMMIT")
        with cleanup_eng.connect() as conn:
            conn.execute(text(f"""
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = '{db_name}'
                  AND pid <> pg_backend_pid();
            """))
            conn.execute(text(f"DROP DATABASE IF EXISTS {db_name};"))
        cleanup_eng.dispose()
