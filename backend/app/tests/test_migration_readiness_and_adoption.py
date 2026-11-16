"""
Phase 15D.4.4.2 Verification & Hardening Test Suite:
1. Production Alembic revision readiness (connectivity, missing version table, empty version table,
   outdated revision, unknown revision, multiple heads, unreachable database).
2. Existing database safe adoption (schema verification, rejection of partial/incompatible schemas,
   data preservation, non-destructive behavior).
"""

import os
import sys
import uuid
import tempfile
import pytest
from sqlalchemy import create_engine, inspect, text
from alembic.config import Config
from alembic import command
from alembic.script import ScriptDirectory

# Ensure backend and root are on sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app.core.config import settings
from app.database.session import Base, reset_database_engine
import app.models.all_models
from app.main import check_database_readiness
from app.database.adoption import verify_schema_compatibility, safely_adopt_existing_database

POSTGRES_TEST_URL = os.getenv(
    "POSTGRES_TEST_DATABASE_URL",
    "postgresql://postgres:postgrespassword2026@127.0.0.1:5432/mcp_nexus_test"
)


def _is_pg_available() -> bool:
    try:
        eng = create_engine(POSTGRES_TEST_URL, connect_args={"connect_timeout": 2})
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


# ==============================================================================
# 1. PRODUCTION REVISION READINESS TESTS
# ==============================================================================

def test_prod_readiness_missing_version_table_rejected(tmp_path):
    """Verify production startup fails fast when the alembic_version table is absent."""
    test_db = tmp_path / f"prod_no_alembic_{uuid.uuid4().hex[:6]}.db"
    db_url = f"sqlite:///{test_db}"

    # Create tables without Alembic
    eng = create_engine(db_url)
    Base.metadata.create_all(bind=eng)
    eng.dispose()

    orig_env = settings.ENVIRONMENT
    saved_url = settings.DATABASE_URL
    try:
        settings.ENVIRONMENT = "Production"
        reset_database_engine(db_url)

        with pytest.raises(RuntimeError) as exc_info:
            check_database_readiness()

        err_msg = str(exc_info.value)
        assert "Alembic version table 'alembic_version' is missing" in err_msg
        assert "Run 'alembic upgrade head'" in err_msg
    finally:
        settings.ENVIRONMENT = orig_env
        reset_database_engine(saved_url)


def test_prod_readiness_empty_version_table_rejected(tmp_path):
    """Verify production startup fails fast when the alembic_version table has no rows."""
    test_db = tmp_path / f"prod_empty_ver_{uuid.uuid4().hex[:6]}.db"
    db_url = f"sqlite:///{test_db}"

    eng = create_engine(db_url)
    Base.metadata.create_all(bind=eng)
    with eng.connect() as conn:
        conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL);"))
        conn.commit()
    eng.dispose()

    orig_env = settings.ENVIRONMENT
    saved_url = settings.DATABASE_URL
    try:
        settings.ENVIRONMENT = "Production"
        reset_database_engine(db_url)

        with pytest.raises(RuntimeError) as exc_info:
            check_database_readiness()

        err_msg = str(exc_info.value)
        assert "Alembic version table is empty" in err_msg
    finally:
        settings.ENVIRONMENT = orig_env
        reset_database_engine(saved_url)


def test_prod_readiness_unknown_revision_rejected(tmp_path):
    """Verify production startup fails fast when the database has an unknown revision."""
    test_db = tmp_path / f"prod_unknown_rev_{uuid.uuid4().hex[:6]}.db"
    db_url = f"sqlite:///{test_db}"

    eng = create_engine(db_url)
    Base.metadata.create_all(bind=eng)
    with eng.connect() as conn:
        conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL);"))
        conn.execute(text("INSERT INTO alembic_version VALUES ('unknown_rev_xyz_999');"))
        conn.commit()
    eng.dispose()

    orig_env = settings.ENVIRONMENT
    saved_url = settings.DATABASE_URL
    try:
        settings.ENVIRONMENT = "Production"
        reset_database_engine(db_url)

        with pytest.raises(RuntimeError) as exc_info:
            check_database_readiness()

        err_msg = str(exc_info.value)
        assert "unknown" in err_msg.lower()
    finally:
        settings.ENVIRONMENT = orig_env
        reset_database_engine(saved_url)


def test_prod_readiness_outdated_or_behind_revision_rejected(tmp_path):
    """Verify production startup fails fast when the database is behind the expected head."""
    test_db = tmp_path / f"prod_behind_{uuid.uuid4().hex[:6]}.db"
    db_url = f"sqlite:///{test_db}"

    eng = create_engine(db_url)
    Base.metadata.create_all(bind=eng)
    with eng.connect() as conn:
        conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL);"))
        # Synthetic older revision ID
        conn.execute(text("INSERT INTO alembic_version VALUES ('outdated_older_rev');"))
        conn.commit()
    eng.dispose()

    orig_env = settings.ENVIRONMENT
    saved_url = settings.DATABASE_URL
    try:
        settings.ENVIRONMENT = "Production"
        reset_database_engine(db_url)

        with pytest.raises(RuntimeError) as exc_info:
            check_database_readiness()

        err_msg = str(exc_info.value)
        assert "CRITICAL STARTUP ERROR" in err_msg
    finally:
        settings.ENVIRONMENT = orig_env
        reset_database_engine(saved_url)


def test_prod_readiness_unreachable_database_rejected():
    """Verify production startup rejects unreachable database with descriptive error."""
    unreachable_url = "postgresql://invalid_user:invalid_pw@127.0.0.1:54399/non_existent_db"
    orig_env = settings.ENVIRONMENT
    saved_url = settings.DATABASE_URL
    try:
        settings.ENVIRONMENT = "Production"
        reset_database_engine(unreachable_url)

        with pytest.raises(RuntimeError) as exc_info:
            check_database_readiness()

        err_msg = str(exc_info.value)
        assert "unreachable" in err_msg.lower() or "connectivity" in err_msg.lower()
    finally:
        settings.ENVIRONMENT = orig_env
        reset_database_engine(saved_url)


def test_prod_readiness_migrated_head_permitted(tmp_path):
    """Verify production startup succeeds smoothly when database is migrated to head."""
    test_db = tmp_path / f"prod_valid_{uuid.uuid4().hex[:6]}.db"
    db_url = f"sqlite:///{test_db}"

    cfg = Config(os.path.join(ROOT_DIR, "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(cfg, "head")

    orig_env = settings.ENVIRONMENT
    saved_url = settings.DATABASE_URL
    try:
        settings.ENVIRONMENT = "Production"
        reset_database_engine(db_url)

        # Should execute cleanly with zero exceptions raised
        check_database_readiness()
    finally:
        settings.ENVIRONMENT = orig_env
        reset_database_engine(saved_url)


# ==============================================================================
# 2. EXISTING DATABASE ADOPTION TESTS
# ==============================================================================

def test_adoption_compatible_schema_stamped_successfully(tmp_path):
    """Verify that a 100% compatible pre-existing database is safely adopted and stamped."""
    test_db = tmp_path / f"adopt_valid_{uuid.uuid4().hex[:6]}.db"
    db_url = f"sqlite:///{test_db}"

    # Initialize tables via Base.metadata (simulating pre-existing compatible DB)
    eng = create_engine(db_url)
    Base.metadata.create_all(bind=eng)

    # Insert test record to verify data preservation
    with eng.connect() as conn:
        conn.execute(text("INSERT INTO organizations (id, name, slug) VALUES ('org-1', 'Org Alpha', 'org-alpha');"))
        conn.commit()
    eng.dispose()

    # Adopt
    ok, msg = safely_adopt_existing_database(db_url)
    assert ok, f"Adoption failed unexpectedly: {msg}"
    assert "Successfully adopted" in msg or "already stamped" in msg

    # Verify stamp in database and data preservation
    eng2 = create_engine(db_url)
    with eng2.connect() as conn:
        res = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        org_name = conn.execute(text("SELECT name FROM organizations WHERE id = 'org-1'")).scalar()

    cfg = Config(os.path.join(ROOT_DIR, "alembic.ini"))
    script = ScriptDirectory.from_config(cfg)
    assert res == script.get_current_head()
    assert org_name == "Org Alpha", "Data was corrupted or dropped during adoption!"
    eng2.dispose()


def test_adoption_missing_table_rejected(tmp_path):
    """Verify that an existing database missing a required table is rejected for adoption."""
    test_db = tmp_path / f"adopt_missing_tbl_{uuid.uuid4().hex[:6]}.db"
    db_url = f"sqlite:///{test_db}"

    eng = create_engine(db_url)
    # Only create a subset of tables
    Base.metadata.tables["organizations"].create(bind=eng)
    Base.metadata.tables["users"].create(bind=eng)
    eng.dispose()

    ok, msg = safely_adopt_existing_database(db_url)
    assert not ok
    assert "missing required table" in msg.lower()

    # Verify alembic_version was NOT stamped
    eng2 = create_engine(db_url)
    with eng2.connect() as conn:
        insp = inspect(conn)
        assert "alembic_version" not in insp.get_table_names()
    eng2.dispose()


def test_canonical_schema_contract_consistency():
    """Verify that Base.metadata, initial Alembic migration, and CANONICAL_INITIAL_SCHEMA_TABLES 100% agree."""
    import ast
    from app.database.adoption import CANONICAL_INITIAL_SCHEMA_TABLES

    # 1. Base.metadata must contain exactly the 13 canonical tables
    assert set(Base.metadata.tables.keys()) == set(CANONICAL_INITIAL_SCHEMA_TABLES)

    # 2. Parse Alembic initial migration file and extract created table names
    mig_file = os.path.join(ROOT_DIR, "backend", "alembic", "versions", "2a307f9f14bc_initial_schema.py")
    with open(mig_file, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    mig_tables = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if getattr(node.func, "attr", "") == "create_table":
                if node.args and isinstance(node.args[0], ast.Constant):
                    mig_tables.add(node.args[0].value)

    assert mig_tables == set(CANONICAL_INITIAL_SCHEMA_TABLES), (
        f"Migration schema divergence detected: {mig_tables ^ set(CANONICAL_INITIAL_SCHEMA_TABLES)}"
    )


def test_adoption_unexpected_extraneous_table_rejected(tmp_path):
    """Verify that an existing database containing extraneous tables is rejected for adoption."""
    test_db = tmp_path / f"adopt_extra_tbl_{uuid.uuid4().hex[:6]}.db"
    db_url = f"sqlite:///{test_db}"

    eng = create_engine(db_url)
    Base.metadata.create_all(bind=eng)
    with eng.connect() as conn:
        conn.execute(text("CREATE TABLE unknown_foreign_table (id INT PRIMARY KEY, val TEXT);"))
        conn.commit()
    eng.dispose()

    ok, msg = safely_adopt_existing_database(db_url)
    assert not ok
    assert "unexpected table(s) found" in msg.lower() or "structural differences detected" in msg.lower()


def test_adoption_already_versioned_older_revision_rejected(tmp_path):
    """Verify that a database already managed by Alembic at an older revision is rejected for stamp adoption."""
    test_db = tmp_path / f"adopt_old_rev_{uuid.uuid4().hex[:6]}.db"
    db_url = f"sqlite:///{test_db}"

    eng = create_engine(db_url)
    Base.metadata.create_all(bind=eng)
    with eng.connect() as conn:
        conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL);"))
        conn.execute(text("INSERT INTO alembic_version VALUES ('older_legacy_rev_123');"))
        conn.commit()
    eng.dispose()

    ok, msg = safely_adopt_existing_database(db_url)
    assert not ok
    assert "already managed by alembic" in msg.lower() or "upgrade" in msg.lower()


def test_adoption_invalid_or_non_head_target_revision_rejected(tmp_path):
    """Verify that specifying an unknown or non-head target revision is safely rejected."""
    test_db = tmp_path / f"adopt_bad_target_{uuid.uuid4().hex[:6]}.db"
    db_url = f"sqlite:///{test_db}"

    eng = create_engine(db_url)
    Base.metadata.create_all(bind=eng)
    eng.dispose()

    # Case 1: Unknown target revision
    ok, msg = safely_adopt_existing_database(db_url, target_revision="completely_unknown_rev")
    assert not ok
    assert "unknown" in msg.lower()

    # Case 2: Outdated/non-head target revision
    ok2, msg2 = safely_adopt_existing_database(db_url, target_revision="fake_older_head")
    assert not ok2


def test_adoption_nullability_mismatch_rejected(tmp_path):
    """Verify that a column nullability discrepancy causes adoption rejection."""
    test_db = tmp_path / f"adopt_null_mismatch_{uuid.uuid4().hex[:6]}.db"
    db_url = f"sqlite:///{test_db}"

    eng = create_engine(db_url)
    Base.metadata.create_all(bind=eng)
    # Recreate organizations with null slug (which should be non-nullable)
    with eng.connect() as conn:
        conn.execute(text("DROP TABLE organizations;"))
        conn.execute(text("CREATE TABLE organizations (id VARCHAR(36) PRIMARY KEY, name VARCHAR(255) NULL, slug VARCHAR(100) NULL);"))
        conn.commit()
    eng.dispose()

    ok, msg = safely_adopt_existing_database(db_url)
    assert not ok
    assert "nullability mismatch" in msg.lower() or "missing column" in msg.lower()


def test_adoption_live_postgresql():
    """Verify safe adoption workflow against a live disposable PostgreSQL database."""
    if not _is_pg_available():
        pytest.skip("PostgreSQL test instance is unavailable.")

    admin_url = POSTGRES_TEST_URL.rsplit('/', 1)[0] + '/postgres'
    disp_db = f"adopt_pg_{uuid.uuid4().hex[:8]}"

    eng_admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with eng_admin.connect() as conn:
        conn.execute(text(f"CREATE DATABASE {disp_db};"))
    eng_admin.dispose()

    disp_url = POSTGRES_TEST_URL.rsplit('/', 1)[0] + f"/{disp_db}"

    try:
        # Pre-populate schema using Base.metadata (simulating legacy pre-migration database)
        eng_disp = create_engine(disp_url)
        Base.metadata.create_all(bind=eng_disp)

        # Insert test data to verify data retention
        with eng_disp.connect() as conn:
            conn.execute(text("INSERT INTO organizations (id, name, slug) VALUES ('pg-org-1', 'PG Alpha', 'pg-alpha');"))
            conn.commit()
        eng_disp.dispose()

        # Adopt
        ok, msg = safely_adopt_existing_database(disp_url)
        assert ok, f"PostgreSQL adoption failed: {msg}"

        # Verify alembic_version stamped and data intact
        eng_check = create_engine(disp_url)
        with eng_check.connect() as conn:
            ver = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            org_name = conn.execute(text("SELECT name FROM organizations WHERE id = 'pg-org-1'")).scalar()
        eng_check.dispose()

        cfg = Config(os.path.join(ROOT_DIR, "alembic.ini"))
        script = ScriptDirectory.from_config(cfg)
        assert ver == script.get_current_head()
        assert org_name == "PG Alpha"

        # Verify idempotence on repeat adoption
        ok_repeat, msg_repeat = safely_adopt_existing_database(disp_url)
        assert ok_repeat
        assert "already stamped" in msg_repeat

    finally:
        eng_admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
        with eng_admin.connect() as conn:
            conn.execute(text(f"DROP DATABASE IF EXISTS {disp_db} WITH (FORCE);"))
        eng_admin.dispose()



def test_adoption_missing_column_rejected(tmp_path):
    """Verify that an existing database with a missing column is rejected for adoption."""
    test_db = tmp_path / f"adopt_missing_col_{uuid.uuid4().hex[:6]}.db"
    db_url = f"sqlite:///{test_db}"

    eng = create_engine(db_url)
    Base.metadata.create_all(bind=eng)
    # Intentionally drop a column or simulate incomplete schema
    # In SQLite, create a partial table for users missing 'hashed_password'
    with eng.connect() as conn:
        conn.execute(text("DROP TABLE users;"))
        conn.execute(text("CREATE TABLE users (id VARCHAR(36) PRIMARY KEY, organization_id VARCHAR(36), email VARCHAR(255));"))
        conn.commit()
    eng.dispose()

    ok, msg = safely_adopt_existing_database(db_url)
    assert not ok
    assert "missing column" in msg.lower()

    eng2 = create_engine(db_url)
    with eng2.connect() as conn:
        insp = inspect(conn)
        assert "alembic_version" not in insp.get_table_names()
    eng2.dispose()


def test_canonical_schema_contract_consistency():
    """Verify that Base.metadata, initial Alembic migration, and CANONICAL_INITIAL_SCHEMA_TABLES 100% agree."""
    import ast
    from app.database.adoption import CANONICAL_INITIAL_SCHEMA_TABLES

    # 1. Base.metadata must contain exactly the 13 canonical tables
    assert set(Base.metadata.tables.keys()) == set(CANONICAL_INITIAL_SCHEMA_TABLES)

    # 2. Parse Alembic initial migration file and extract created table names
    mig_file = os.path.join(ROOT_DIR, "backend", "alembic", "versions", "2a307f9f14bc_initial_schema.py")
    with open(mig_file, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    mig_tables = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if getattr(node.func, "attr", "") == "create_table":
                if node.args and isinstance(node.args[0], ast.Constant):
                    mig_tables.add(node.args[0].value)

    assert mig_tables == set(CANONICAL_INITIAL_SCHEMA_TABLES), (
        f"Migration schema divergence detected: {mig_tables ^ set(CANONICAL_INITIAL_SCHEMA_TABLES)}"
    )


def test_adoption_unexpected_extraneous_table_rejected(tmp_path):
    """Verify that an existing database containing extraneous tables is rejected for adoption."""
    test_db = tmp_path / f"adopt_extra_tbl_{uuid.uuid4().hex[:6]}.db"
    db_url = f"sqlite:///{test_db}"

    eng = create_engine(db_url)
    Base.metadata.create_all(bind=eng)
    with eng.connect() as conn:
        conn.execute(text("CREATE TABLE unknown_foreign_table (id INT PRIMARY KEY, val TEXT);"))
        conn.commit()
    eng.dispose()

    ok, msg = safely_adopt_existing_database(db_url)
    assert not ok
    assert "unexpected table(s) found" in msg.lower() or "structural differences detected" in msg.lower()


def test_adoption_already_versioned_older_revision_rejected(tmp_path):
    """Verify that a database already managed by Alembic at an older revision is rejected for stamp adoption."""
    test_db = tmp_path / f"adopt_old_rev_{uuid.uuid4().hex[:6]}.db"
    db_url = f"sqlite:///{test_db}"

    eng = create_engine(db_url)
    Base.metadata.create_all(bind=eng)
    with eng.connect() as conn:
        conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL);"))
        conn.execute(text("INSERT INTO alembic_version VALUES ('older_legacy_rev_123');"))
        conn.commit()
    eng.dispose()

    ok, msg = safely_adopt_existing_database(db_url)
    assert not ok
    assert "already managed by alembic" in msg.lower() or "upgrade" in msg.lower()


def test_adoption_invalid_or_non_head_target_revision_rejected(tmp_path):
    """Verify that specifying an unknown or non-head target revision is safely rejected."""
    test_db = tmp_path / f"adopt_bad_target_{uuid.uuid4().hex[:6]}.db"
    db_url = f"sqlite:///{test_db}"

    eng = create_engine(db_url)
    Base.metadata.create_all(bind=eng)
    eng.dispose()

    # Case 1: Unknown target revision
    ok, msg = safely_adopt_existing_database(db_url, target_revision="completely_unknown_rev")
    assert not ok
    assert "unknown" in msg.lower()

    # Case 2: Outdated/non-head target revision
    ok2, msg2 = safely_adopt_existing_database(db_url, target_revision="fake_older_head")
    assert not ok2


def test_adoption_nullability_mismatch_rejected(tmp_path):
    """Verify that a column nullability discrepancy causes adoption rejection."""
    test_db = tmp_path / f"adopt_null_mismatch_{uuid.uuid4().hex[:6]}.db"
    db_url = f"sqlite:///{test_db}"

    eng = create_engine(db_url)
    Base.metadata.create_all(bind=eng)
    # Recreate organizations with null slug (which should be non-nullable)
    with eng.connect() as conn:
        conn.execute(text("DROP TABLE organizations;"))
        conn.execute(text("CREATE TABLE organizations (id VARCHAR(36) PRIMARY KEY, name VARCHAR(255) NULL, slug VARCHAR(100) NULL);"))
        conn.commit()
    eng.dispose()

    ok, msg = safely_adopt_existing_database(db_url)
    assert not ok
    assert "nullability mismatch" in msg.lower() or "missing column" in msg.lower()


def test_adoption_live_postgresql():
    """Verify safe adoption workflow against a live disposable PostgreSQL database."""
    if not _is_pg_available():
        pytest.skip("PostgreSQL test instance is unavailable.")

    admin_url = POSTGRES_TEST_URL.rsplit('/', 1)[0] + '/postgres'
    disp_db = f"adopt_pg_{uuid.uuid4().hex[:8]}"

    eng_admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with eng_admin.connect() as conn:
        conn.execute(text(f"CREATE DATABASE {disp_db};"))
    eng_admin.dispose()

    disp_url = POSTGRES_TEST_URL.rsplit('/', 1)[0] + f"/{disp_db}"

    try:
        # Pre-populate schema using Base.metadata (simulating legacy pre-migration database)
        eng_disp = create_engine(disp_url)
        Base.metadata.create_all(bind=eng_disp)

        # Insert test data to verify data retention
        with eng_disp.connect() as conn:
            conn.execute(text("INSERT INTO organizations (id, name, slug) VALUES ('pg-org-1', 'PG Alpha', 'pg-alpha');"))
            conn.commit()
        eng_disp.dispose()

        # Adopt
        ok, msg = safely_adopt_existing_database(disp_url)
        assert ok, f"PostgreSQL adoption failed: {msg}"

        # Verify alembic_version stamped and data intact
        eng_check = create_engine(disp_url)
        with eng_check.connect() as conn:
            ver = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            org_name = conn.execute(text("SELECT name FROM organizations WHERE id = 'pg-org-1'")).scalar()
        eng_check.dispose()

        cfg = Config(os.path.join(ROOT_DIR, "alembic.ini"))
        script = ScriptDirectory.from_config(cfg)
        assert ver == script.get_current_head()
        assert org_name == "PG Alpha"

        # Verify idempotence on repeat adoption
        ok_repeat, msg_repeat = safely_adopt_existing_database(disp_url)
        assert ok_repeat
        assert "already stamped" in msg_repeat

    finally:
        eng_admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
        with eng_admin.connect() as conn:
            conn.execute(text(f"DROP DATABASE IF EXISTS {disp_db} WITH (FORCE);"))
        eng_admin.dispose()

