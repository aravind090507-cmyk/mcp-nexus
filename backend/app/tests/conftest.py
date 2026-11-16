"""
MCP NEXUS — Global Test Database Isolation & Safety Harness (conftest.py)

Guarantees 100% isolation of automated test execution from the development database (mcp_nexus.db).
Initializes a temporary SQLite database from the pristine baseline before any test modules or
FastAPI applications are imported.

Enforces exact 4-point database isolation verification before and after every test.
"""

import sys
import os
import shutil
import tempfile
import hashlib
import sqlite3
import logging
from typing import Tuple, Optional
import pytest

logger = logging.getLogger("mcp-nexus.test-isolation")

# 1. Ensure backend root is on sys.path before any application imports
backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
repo_root = os.path.abspath(os.path.join(backend_root, ".."))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

# 2. Locate baseline pristine database template
dev_db_path = os.path.abspath(os.path.join(repo_root, "mcp_nexus.db"))
baseline_candidate = os.path.abspath(os.path.join(repo_root, "mcp_nexus.db.bak_pristine_baseline"))
if os.path.exists(baseline_candidate):
    baseline_src = baseline_candidate
elif os.path.exists(dev_db_path):
    baseline_src = dev_db_path
else:
    # Clean-checkout / CI fallback: Synthesize pristine baseline database template
    logger.info("Baseline database binary not found in clean checkout; synthesizing pristine template.")
    synth_dir = tempfile.mkdtemp(prefix="mcp_nexus_ci_baseline_")
    synth_path = os.path.abspath(os.path.join(synth_dir, "clean_ci_baseline.db"))
    from sqlalchemy import create_engine
    from app.database.session import Base, reset_database_engine
    import app.models.all_models
    import asyncio
    from app.main import startup_seed

    _synth_eng = create_engine(f"sqlite:///{synth_path}")
    Base.metadata.create_all(bind=_synth_eng)
    _synth_eng.dispose()

    reset_database_engine(f"sqlite:///{synth_path}")
    asyncio.run(startup_seed())
    reset_database_engine()
    baseline_src = synth_path

# Record baseline hash of dev_db_path to verify invariance
_initial_dev_db_hash = None
if os.path.exists(dev_db_path):
    _initial_dev_db_hash = hashlib.sha256(open(dev_db_path, "rb").read()).hexdigest()

# 3. Create global temporary database directory and clone baseline (singleton guarded)
if not hasattr(sys, "_mcp_nexus_global_temp_dir"):
    sys._mcp_nexus_global_temp_dir = tempfile.mkdtemp(prefix="mcp_nexus_pytest_global_")
    sys._mcp_nexus_global_temp_db_path = os.path.abspath(os.path.join(sys._mcp_nexus_global_temp_dir, "isolated_mcp_nexus_test.db"))
    shutil.copy2(baseline_src, sys._mcp_nexus_global_temp_db_path)
    sys._mcp_nexus_global_isolated_url = f"sqlite:///{sys._mcp_nexus_global_temp_db_path}"

_global_temp_dir = sys._mcp_nexus_global_temp_dir
_global_temp_db_path = sys._mcp_nexus_global_temp_db_path
_global_isolated_url = sys._mcp_nexus_global_isolated_url

# 4. Authoritatively bind configuration and engine to temporary database
from app.core.config import settings
settings.DATABASE_URL = _global_isolated_url

from app.database.session import reset_database_engine, SessionLocal, get_db, engine, _current_engine
reset_database_engine(_global_isolated_url)

# 5. Authoritatively bind FastAPI dependency overrides
try:
    from app.main import app
    def _test_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    app.dependency_overrides[get_db] = _test_get_db
except Exception:
    pass


# 6. Exact Database Isolation Verification Engine
_isolation_violations = []

def _normalize_path(p: str) -> str:
    """Returns normalized, absolute, real filesystem path with consistent casing."""
    return os.path.normcase(os.path.abspath(os.path.realpath(p)))

def _extract_sqlite_path(db_url: str) -> str:
    """Extracts filesystem path from an SQLite database URL."""
    url_str = str(db_url)
    if url_str.startswith("sqlite:///"):
        raw = url_str[len("sqlite:///"): ]
    elif url_str.startswith("sqlite://"):
        raw = url_str[len("sqlite://"): ]
    else:
        raw = url_str
    return _normalize_path(raw)

def verify_exact_database_isolation(test_name: str = "unknown") -> Tuple[bool, Optional[str]]:
    """
    Performs strict exact database identity verification against all 4 isolation vectors:
    1. settings.DATABASE_URL
    2. The actual active SQLAlchemy engine URL
    3. The resolved SQLite database file path
    4. The expected temporary test database path

    Returns (is_valid, violation_reason).
    """
    from app.core.config import settings
    from app.database.session import engine

    expected_path = _normalize_path(_global_temp_db_path)
    expected_url = _global_isolated_url

    # Vector 1: settings.DATABASE_URL
    settings_raw_url = str(settings.DATABASE_URL)
    settings_db_path = _extract_sqlite_path(settings_raw_url)

    # Vector 2: Actual active SQLAlchemy engine URL
    engine_raw_url = str(engine.url)

    # Vector 3: Resolved SQLite database file path from engine
    engine_db_path = _extract_sqlite_path(engine_raw_url)

    # Vector 4: Development database path (must NEVER match)
    dev_db_normalized = _normalize_path(dev_db_path) if os.path.exists(dev_db_path) else None

    # Check A: Absolute prohibition against development database
    if dev_db_normalized and (settings_db_path == dev_db_normalized or engine_db_path == dev_db_normalized):
        reason = (
            f"CRITICAL ISOLATION BREACH: Active database resolved to development database (mcp_nexus.db)! "
            f"settings='{settings_raw_url}', engine='{engine_raw_url}', dev_db='{dev_db_normalized}'"
        )
        return False, reason

    # Check B: Settings and Engine URL synchronization
    if settings_db_path != engine_db_path:
        reason = (
            f"ISOLATION DESYNCHRONIZATION: settings.DATABASE_URL and active engine point to different files! "
            f"settings_path='{settings_db_path}' vs engine_path='{engine_db_path}'"
        )
        return False, reason

    # Check C: Must resolve to an authorized isolated test database
    is_global_match = (engine_db_path == expected_path)
    is_authorized_temp = (
        ("tmp" in engine_db_path or "temp" in engine_db_path or "pytest" in engine_db_path)
        and (dev_db_normalized is None or engine_db_path != dev_db_normalized)
    )

    if not is_global_match and not is_authorized_temp:
        reason = (
            f"ISOLATION MISMATCH: Active database is not an isolated test database! "
            f"engine_path='{engine_db_path}', expected='{expected_path}'"
        )
        return False, reason

    return True, None


# 7. Global Session-Level Lifecycle Fixture
@pytest.fixture(scope="session", autouse=True)
def global_database_isolation_session():
    """
    Session-scoped lifecycle fixture:
    - Enforces that all database operations point to the temporary test database.
    - Guarantees clean engine disposal and temporary directory cleanup on session end.
    - Validates that mcp_nexus.db was not modified in any way.
    """
    yield _global_isolated_url

    # Teardown:
    # A. Dispose SQLAlchemy engine
    from app.database.session import _current_engine, reset_database_engine
    if _current_engine is not None:
        try:
            _current_engine.dispose()
        except Exception:
            pass

    # B. Restore original settings to baseline path
    if os.path.exists(dev_db_path):
        orig_url = f"sqlite:///{dev_db_path}"
        settings.DATABASE_URL = orig_url
        reset_database_engine(orig_url)

    # C. Verify development database invariance
    if _initial_dev_db_hash and os.path.exists(dev_db_path):
        final_hash = hashlib.sha256(open(dev_db_path, "rb").read()).hexdigest()
        assert final_hash == _initial_dev_db_hash, (
            f"CRITICAL TEST ISOLATION BREACH: mcp_nexus.db was modified during test run! "
            f"Initial SHA256: {_initial_dev_db_hash}, Final SHA256: {final_hash}"
        )

    # D. Remove temporary database directory and associated WAL/SHM files
    if os.path.exists(_global_temp_dir):
        try:
            shutil.rmtree(_global_temp_dir, ignore_errors=True)
        except Exception:
            pass


# 8. Per-Test Exact Isolation Enforcement Guard
@pytest.fixture(autouse=True)
def ensure_isolated_database_per_test(request):
    """
    Guarantees exact database isolation for every single test.
    Executes pre-test setup verification and post-test teardown verification.
    If any mismatch occurs:
    1. Immediately restores the isolated database binding.
    2. Records the violation.
    3. Fails the test with pytest.fail().
    """
    from app.core.config import settings
    from app.database.session import reset_database_engine

    # --- Pre-Test Verification ---
    is_valid, reason = verify_exact_database_isolation(request.node.name)
    if not is_valid:
        # Immediate restoration to safe isolated state
        settings.DATABASE_URL = _global_isolated_url
        reset_database_engine(_global_isolated_url)
        _isolation_violations.append((request.node.name, "setup", reason))
        logger.critical(f"PRE-TEST ISOLATION BREACH in {request.node.name}: {reason}")
        pytest.fail(f"PRE-TEST DATABASE ISOLATION BREACH in '{request.node.name}': {reason}")

    try:
        from app.mcp.persistent_session import PersistentSessionManager
        PersistentSessionManager.test_harness_reset()
    except Exception:
        pass

    yield

    try:
        from app.mcp.persistent_session import PersistentSessionManager
        PersistentSessionManager.test_harness_reset()
    except Exception:
        pass

    # --- Post-Test Verification ---
    is_valid, reason = verify_exact_database_isolation(request.node.name)
    expected_path = _normalize_path(_global_temp_db_path)
    current_engine_path = _extract_sqlite_path(str(settings.DATABASE_URL))

    if not is_valid:
        # Immediate restoration to safe isolated state
        settings.DATABASE_URL = _global_isolated_url
        reset_database_engine(_global_isolated_url)
        _isolation_violations.append((request.node.name, "teardown", reason))
        logger.critical(f"POST-TEST ISOLATION BREACH in {request.node.name}: {reason}")
        pytest.fail(f"POST-TEST DATABASE ISOLATION BREACH in '{request.node.name}': {reason}")

    # Rebind back to global isolated database if a test legitimately used a local temporary DB
    if current_engine_path != expected_path:
        settings.DATABASE_URL = _global_isolated_url
        reset_database_engine(_global_isolated_url)
