"""
Phase 15D.2.7 Comprehensive Verification Suite:
1. SQLAlchemy Engine Lifecycle Safety & Leases.
2. Thread-Safe Session Creation and Rebinding Concurrency.
3. Obsolete Engine Deferred Disposal Under Active Operations.
4. Exception Safety (Failed Rebind Preserves Active Engine).
5. SQLAlchemy Event Registration and Replay Across Rebinds.
6. DDL Operations (Base.metadata.create_all / drop_all via Engine Proxy).
7. Exact Database Isolation Verification (Catching and Rejecting mcp_nexus.db).
"""

import os
import sys
import time
import threading
import tempfile
import pytest
from sqlalchemy import text, Column, Integer, String, Table, MetaData, event
from sqlalchemy.orm import declarative_base

from app.core.config import settings
from app.database.session import (
    engine, SessionLocal, reset_database_engine, get_db,
    ManagedEngineContext, Base, _current_context
)
from app.tests.conftest import (
    verify_exact_database_isolation, _global_isolated_url, _global_temp_db_path, dev_db_path
)


# ==============================================================================
# 1. ENGINE OPERATION COMPATIBILITY TESTS
# ==============================================================================

def test_engine_connect_execute_and_close():
    """Verify engine.connect() operates cleanly, executes SQL, and safely closes."""
    with engine.connect() as conn:
        res = conn.execute(text("SELECT 42")).scalar()
        assert res == 42
        assert not conn.closed
    assert conn.closed


def test_engine_begin_transaction_commit():
    """Verify engine.begin() manages transaction lifecycle and commits successfully."""
    with engine.begin() as conn:
        res = conn.execute(text("SELECT 'phase15d27'")).scalar()
        assert res == "phase15d27"
    assert conn.closed


def test_engine_begin_transaction_rollback():
    """Verify engine.begin() rolls back cleanly upon exception and closes connection."""
    with pytest.raises(ValueError, match="intentional rollback"):
        with engine.begin() as conn:
            conn.execute(text("SELECT 1"))
            raise ValueError("intentional rollback")
    assert conn.closed


def test_base_metadata_create_all_and_drop_all():
    """Verify Base.metadata.create_all(bind=engine) and drop_all operate through proxy."""
    test_meta = MetaData()
    test_table = Table(
        "phase15d27_probe",
        test_meta,
        Column("id", Integer, primary_key=True),
        Column("val", String(50))
    )

    test_meta.create_all(bind=engine)

    with engine.connect() as conn:
        conn.execute(text("INSERT INTO phase15d27_probe (id, val) VALUES (1, 'ok')"))
        conn.commit()
        val = conn.execute(text("SELECT val FROM phase15d27_probe WHERE id = 1")).scalar()
        assert val == "ok"

    test_meta.drop_all(bind=engine)

    with engine.connect() as conn:
        res = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='phase15d27_probe'")).fetchall()
        assert len(res) == 0


def test_session_lifecycle_and_get_db_generator():
    """Verify SessionLocal() and get_db() lifecycle and lease tracking."""
    # Test SessionLocal explicit close
    sess = SessionLocal()
    res = sess.execute(text("SELECT 100")).scalar()
    assert res == 100
    sess.close()

    # Test get_db generator
    gen = get_db()
    db = next(gen)
    res2 = db.execute(text("SELECT 200")).scalar()
    assert res2 == 200
    try:
        next(gen)
    except StopIteration:
        pass


# ==============================================================================
# 2. EVENT REGISTRATION & REPLAY TESTS
# ==============================================================================

def test_sqlalchemy_event_registration_and_replay():
    """Verify SQLAlchemy event listeners fire and are replayed across engine rebinds."""
    events_captured = []

    def on_cursor_exec(conn, cursor, statement, parameters, context, executemany):
        if "SELECT 'evt_test'" in statement:
            events_captured.append("captured")

    event.listen(engine, "before_cursor_execute", on_cursor_exec)

    # 1. Execute on current engine
    with engine.connect() as conn:
        conn.execute(text("SELECT 'evt_test'"))
    assert len(events_captured) == 1

    # 2. Rebind to a new temporary database URL
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_db = tmp.name
    tmp_url = f"sqlite:///{tmp_db}"

    try:
        reset_database_engine(tmp_url)
        # 3. Execute on rebound engine - verify event was transferred!
        with engine.connect() as conn:
            conn.execute(text("SELECT 'evt_test'"))
        assert len(events_captured) == 2
    finally:
        # Rebind back to global isolated database
        reset_database_engine(_global_isolated_url)
        if os.path.exists(tmp_db):
            try:
                os.remove(tmp_db)
            except Exception:
                pass


def test_event_listener_removal_after_engine_rebinding():
    """Verify that user event listeners can be reliably removed after engine rebinds (DEFECT-15D27-02)."""
    events_captured = []

    def on_cursor_exec(conn, cursor, statement, parameters, context, executemany):
        if "SELECT 'evt_removal_test'" in statement:
            events_captured.append("captured")

    event.listen(engine, "before_cursor_execute", on_cursor_exec)

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_db = tmp.name
    tmp_url = f"sqlite:///{tmp_db}"

    try:
        # Rebind to new engine
        reset_database_engine(tmp_url)

        # Verify listener fires on rebound engine
        with engine.connect() as conn:
            conn.execute(text("SELECT 'evt_removal_test'"))
        assert len(events_captured) == 1

        # Now remove listener using proxy remove_listener
        engine.remove_listener("before_cursor_execute", on_cursor_exec)

        # Verify listener no longer fires on rebound engine
        with engine.connect() as conn:
            conn.execute(text("SELECT 'evt_removal_test'"))
        assert len(events_captured) == 1  # Unchanged!
    finally:
        reset_database_engine(_global_isolated_url)
        if os.path.exists(tmp_db):
            try:
                os.remove(tmp_db)
            except Exception:
                pass


# ==============================================================================
# 3. CONCURRENCY & LEASE TRACKING TESTS
# ==============================================================================

def test_concurrent_session_creation():
    """Verify concurrent threads creating and using sessions execute without deadlocks."""
    errors = []

    def worker(worker_id):
        try:
            for _ in range(20):
                db = SessionLocal()
                val = db.execute(text(f"SELECT {worker_id}")).scalar()
                assert val == worker_id
                db.close()
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Concurrent session errors: {errors}"


def test_engine_rebinding_preserves_active_leases_without_premature_disposal():
    """
    Verify that an active transaction holding an engine lease continues executing
    normally even when reset_database_engine() rebinds the application to a new engine.
    The obsolete engine is ONLY disposed after the in-flight transaction completes.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_db = tmp.name
    tmp_url = f"sqlite:///{tmp_db}"

    initial_ctx = engine.managed_context
    conn = engine.connect()
    assert initial_ctx.active_leases >= 1

    try:
        # Rebind to another engine while conn is actively held!
        reset_database_engine(tmp_url)

        # The initial context must be retired, but NOT disposed because conn is still open!
        assert initial_ctx.is_retired
        assert not initial_ctx.is_disposed
        assert initial_ctx.active_leases >= 1

        # The active connection can still execute queries safely on its engine
        res = conn.execute(text("SELECT 999")).scalar()
        assert res == 999

        # Now close the connection: should trigger deferred disposal
        conn.close()
        assert initial_ctx.active_leases == 0
        assert initial_ctx.is_disposed

    finally:
        reset_database_engine(_global_isolated_url)
        if os.path.exists(tmp_db):
            try:
                os.remove(tmp_db)
            except Exception:
                pass


def test_abandoned_session_gc_releases_engine_lease():
    """Verify that abandoned SessionLocal objects are collected by GC and release engine leases (DEFECT-15D27-01)."""
    import gc
    ctx = engine.managed_context
    initial_leases = ctx.active_leases

    def _open_and_abandon():
        s = SessionLocal()
        assert ctx.active_leases == initial_leases + 1
        # Abandon session s without calling .close()
        return None

    _open_and_abandon()
    # Force garbage collection to trigger weakref.finalize
    gc.collect()
    assert ctx.active_leases == initial_leases


def test_abandoned_connection_gc_releases_engine_lease():
    """Verify that abandoned engine.connect() objects are collected by GC and release engine leases (DEFECT-15D27-01)."""
    import gc
    ctx = engine.managed_context
    initial_leases = ctx.active_leases

    def _open_and_abandon():
        c = engine.connect()
        assert ctx.active_leases == initial_leases + 1
        # Abandon connection c without calling .close()
        return None

    _open_and_abandon()
    # Force garbage collection to trigger weakref.finalize
    gc.collect()
    assert ctx.active_leases == initial_leases


def test_failed_rebind_preserves_active_engine():
    """Verify that an invalid database URL raises an exception and leaves active engine unharmed."""
    initial_url = str(engine.url)

    with pytest.raises(Exception):
        # Invalid database dialect / URL that fails in create_engine
        reset_database_engine("invalid_unsupported_dialect://bad:path")

    # Active engine must be completely unharmed and fully operational
    assert str(engine.url) == initial_url
    with engine.connect() as conn:
        res = conn.execute(text("SELECT 1")).scalar()
        assert res == 1


# ==============================================================================
# 4. EXACT DATABASE ISOLATION VERIFICATION TESTS
# ==============================================================================

def test_exact_database_isolation_passes_on_global_temp_db():
    """Verify that verify_exact_database_isolation() validates successfully under global test harness."""
    is_valid, reason = verify_exact_database_isolation("test_exact_database_isolation_passes_on_global_temp_db")
    assert is_valid, f"Expected isolation to pass, got reason: {reason}"
    assert reason is None


def test_exact_database_isolation_fails_fast_on_development_db():
    """
    Verify that if the active engine or settings ever resolves to the development
    database (mcp_nexus.db), verify_exact_database_isolation() detects the breach immediately.
    """
    # Simulate a breach check against dev db path
    dev_url = f"sqlite:///{dev_db_path}"
    
    # Temporarily set settings.DATABASE_URL to dev db (without modifying actual active engine)
    orig_url = settings.DATABASE_URL
    try:
        settings.DATABASE_URL = dev_url
        is_valid, reason = verify_exact_database_isolation("probe_dev_breach")
        assert not is_valid
        assert "CRITICAL ISOLATION BREACH" in reason or "ISOLATION DESYNCHRONIZATION" in reason
    finally:
        settings.DATABASE_URL = orig_url
