"""
MCP NEXUS — Global Test Database Isolation & Safety Harness (conftest.py)

Guarantees 100% isolation of automated test execution from the development database (mcp_nexus.db).
Initializes a temporary SQLite database from the pristine baseline before any test modules or
FastAPI applications are imported.
"""

import sys
import os
import shutil
import tempfile
import hashlib
import sqlite3
import pytest

# 1. Ensure backend root is on sys.path before any application imports
backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
repo_root = os.path.abspath(os.path.join(backend_root, ".."))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

# 2. Locate baseline pristine database template
dev_db_path = os.path.join(repo_root, "mcp_nexus.db")
baseline_candidate = os.path.join(repo_root, "mcp_nexus.db.bak_pristine_baseline")
if os.path.exists(baseline_candidate):
    baseline_src = baseline_candidate
elif os.path.exists(dev_db_path):
    baseline_src = dev_db_path
else:
    raise RuntimeError("CRITICAL ARCHITECTURAL FAILURE: Baseline database template missing. Tests cannot proceed safely.")

# Record baseline hash of dev_db_path to verify invariance
_initial_dev_db_hash = None
if os.path.exists(dev_db_path):
    _initial_dev_db_hash = hashlib.sha256(open(dev_db_path, "rb").read()).hexdigest()

# 3. Create global temporary database directory and clone baseline
_global_temp_dir = tempfile.mkdtemp(prefix="mcp_nexus_pytest_global_")
_global_temp_db_path = os.path.join(_global_temp_dir, "isolated_mcp_nexus_test.db")
shutil.copy2(baseline_src, _global_temp_db_path)

_global_isolated_url = f"sqlite:///{_global_temp_db_path}"

# 4. Authoritatively bind configuration and engine to temporary database
from app.core.config import settings
settings.DATABASE_URL = _global_isolated_url

from app.database.session import reset_database_engine, SessionLocal, get_db, _current_engine
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


# 6. Global Session-Level Lifecycle Fixture
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


@pytest.fixture(autouse=True)
def ensure_isolated_database_per_test():
    """Guarantees that every test begins and ends pointing to an isolated test database."""
    yield
    # If a test reloaded settings to Development or Staging, ensure subsequent tests rebind to isolated DB
    if "isolated" not in settings.DATABASE_URL:
        settings.DATABASE_URL = _global_isolated_url
        reset_database_engine(_global_isolated_url)
