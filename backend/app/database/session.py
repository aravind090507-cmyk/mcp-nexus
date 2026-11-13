import os
import sys
import threading
import weakref
import logging
from typing import Optional, Any, Callable, List, Tuple
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

logger = logging.getLogger("mcp-nexus.database")

# Dedicated re-entrant locks for engine lifecycle and thread-safe operations
_rebind_lock = threading.RLock()
_state_lock = threading.RLock()


class ManagedEngineContext:
    """
    Encapsulates an SQLAlchemy engine and session factory with active operation lease tracking.
    Guarantees that obsolete engines are never disposed while queries or transactions are active.
    """
    def __init__(self, engine, session_factory, url: str):
        self.engine = engine
        self.session_factory = session_factory
        self.url = url
        self._active_leases = 0
        self._retired = False
        self._disposed = False
        self._lock = threading.Lock()

    def acquire_lease(self):
        """Acquire an active operation lease. Increments active operation count."""
        with self._lock:
            if self._disposed:
                raise RuntimeError(f"Cannot acquire lease on disposed engine ({self.url}).")
            self._active_leases += 1
            return self

    def release_lease(self):
        """Release an active operation lease. Triggers disposal if retired and leases reach zero."""
        should_dispose = False
        with self._lock:
            if self._active_leases > 0:
                self._active_leases -= 1
            if self._retired and self._active_leases == 0 and not self._disposed:
                self._disposed = True
                should_dispose = True

        if should_dispose:
            self._safe_dispose()

    def retire(self):
        """
        Marks engine context as retired (superseded by a new engine).
        If no active leases exist, disposes engine immediately.
        Otherwise, disposal is deferred until the last active lease is released.
        """
        should_dispose = False
        with self._lock:
            self._retired = True
            if self._active_leases == 0 and not self._disposed:
                self._disposed = True
                should_dispose = True

        if should_dispose:
            self._safe_dispose()

    def _safe_dispose(self):
        """Disposes the underlying engine and connection pool safely."""
        try:
            self.engine.dispose()
        except Exception as e:
            logger.warning(f"Error during engine disposal for {self.url}: {e}")

    @property
    def active_leases(self) -> int:
        with self._lock:
            return self._active_leases

    @property
    def is_retired(self) -> bool:
        with self._lock:
            return self._retired

    @property
    def is_disposed(self) -> bool:
        with self._lock:
            return self._disposed


def _create_engine_and_session(db_url: str):
    connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
    eng = create_engine(
        db_url,
        connect_args=connect_args,
        echo=False
    )
    sess_factory = sessionmaker(autocommit=False, autoflush=False, bind=eng)
    return eng, sess_factory


def _initialize_initial_context() -> ManagedEngineContext:
    eng, sess = _create_engine_and_session(settings.DATABASE_URL)
    return ManagedEngineContext(eng, sess, settings.DATABASE_URL)


_current_context: ManagedEngineContext = _initialize_initial_context()


def get_current_managed_context() -> ManagedEngineContext:
    """Returns the currently active ManagedEngineContext thread-safely."""
    with _state_lock:
        return _current_context


class _EngineProxy:
    """
    Transparent, thread-safe proxy to the active SQLAlchemy engine.
    Ensures that any module that imported engine directly routes its connections,
    executions, and DDL bindings to the active engine with lease-based lifecycle tracking.
    """
    def connect(self, *args, **kwargs):
        """Acquire a connection from the active engine under an active operation lease."""
        with _rebind_lock:
            with _state_lock:
                ctx = _current_context
                ctx.acquire_lease()
            try:
                conn = ctx.engine.connect(*args, **kwargs)
            except Exception:
                ctx.release_lease()
                raise

        # Attach lease release to connection closure and GC finalization
        _released = False
        _lock = threading.Lock()
        orig_close = conn.close

        def _safe_close():
            nonlocal _released
            with _lock:
                if not _released:
                    _released = True
                    try:
                        orig_close()
                    finally:
                        ctx.release_lease()

        conn.close = _safe_close
        weakref.finalize(conn, _safe_close)
        return conn

    @contextmanager
    def begin(self, *args, **kwargs):
        """Context manager yielding a Connection inside an active transaction."""
        conn = self.connect(*args, **kwargs)
        with conn.begin():
            try:
                yield conn
            finally:
                conn.close()

    def execution_options(self, *args, **kwargs):
        with _state_lock:
            return _current_context.engine.execution_options(*args, **kwargs)

    def dispose(self):
        """Disposes the active engine."""
        with _state_lock:
            _current_context.engine.dispose()

    @property
    def url(self):
        with _state_lock:
            return _current_context.engine.url

    @property
    def name(self):
        with _state_lock:
            return _current_context.engine.name

    @property
    def dialect(self):
        with _state_lock:
            return _current_context.engine.dialect

    @property
    def echo(self):
        with _state_lock:
            return _current_context.engine.echo

    @property
    def pool(self):
        with _state_lock:
            return _current_context.engine.pool

    @property
    def dispatch(self):
        with _state_lock:
            return _current_context.engine.dispatch

    @property
    def managed_context(self) -> ManagedEngineContext:
        with _state_lock:
            return _current_context

    def __getattr__(self, name):
        with _state_lock:
            return getattr(_current_context.engine, name)

    def __setattr__(self, name, value):
        with _state_lock:
            setattr(_current_context.engine, name, value)

    def __repr__(self):
        with _state_lock:
            return repr(_current_context.engine)


engine = _EngineProxy()
_current_engine = engine


class _SessionLocalProxy:
    """
    Transparent proxy to the active SQLAlchemy session factory.
    Ensures that when reset_database_engine is called, all sessions are created from
    the active database with active lease tracking.
    """
    def __call__(self, *args, **kwargs):
        with _rebind_lock:
            with _state_lock:
                ctx = _current_context
                ctx.acquire_lease()
            factory = ctx.session_factory

        try:
            session = factory(*args, **kwargs)
        except Exception:
            ctx.release_lease()
            raise

        _released = False
        _lock = threading.Lock()
        orig_close = session.close

        def _safe_close():
            nonlocal _released
            with _lock:
                if not _released:
                    _released = True
                    try:
                        orig_close()
                    finally:
                        ctx.release_lease()

        session.close = _safe_close
        weakref.finalize(session, _safe_close)
        return session

    def __getattr__(self, name):
        with _state_lock:
            return getattr(_current_context.session_factory, name)


SessionLocal = _SessionLocalProxy()

Base = declarative_base()


def reset_database_engine(new_db_url: Optional[str] = None):
    """
    Dynamically rebinds the SQLAlchemy engine and session factory to a specified database URL
    or re-reads settings.DATABASE_URL.
    
    Guarantees:
    - Atomically creates and validates the new engine before retiring the old engine.
    - If engine creation fails, the active engine is preserved completely untouched.
    - Previous engine is retired and only disposed once all active leases have completed.
    - Event listeners from the active engine are transferred to the rebound engine.
    - Thread-safe and deadlock-free.
    """
    global _current_context
    url = new_db_url or settings.DATABASE_URL

    # Step 1: Create and validate new engine and session factory outside state mutation.
    # If this raises any exception, _current_context is completely untouched!
    new_eng, new_sess = _create_engine_and_session(url)

    # Step 2: Transfer registered event listeners to the new engine
    with _state_lock:
        old_ctx = _current_context
        if old_ctx and old_ctx.engine:
            if getattr(old_ctx.engine, "_has_events", False):
                new_eng._has_events = True
            for name in dir(old_ctx.engine.dispatch):
                if not name.startswith('_'):
                    col = getattr(old_ctx.engine.dispatch, name, None)
                    if col and hasattr(col, '__iter__') and len(col) > 0:
                        for item in col:
                            try:
                                event.listen(new_eng, name, item)
                            except Exception:
                                pass

    # Step 3: Under _rebind_lock, atomically swap to new context and retire old context
    new_ctx = ManagedEngineContext(new_eng, new_sess, url)
    with _rebind_lock:
        with _state_lock:
            old_ctx = _current_context
            _current_context = new_ctx
            if new_db_url:
                settings.DATABASE_URL = new_db_url

        # Step 4: Retire old engine. If active leases == 0, disposes immediately.
        # Otherwise, disposal is deferred until in-flight leases reach zero.
        if old_ctx is not None and old_ctx is not new_ctx:
            old_ctx.retire()

    return engine, SessionLocal


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
