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


class _LeaseReleaser:
    """
    Safely releases an operation lease on a ManagedEngineContext.
    Maintains zero references to the Session or Connection object,
    preventing reference cycles in weakref.finalize (DEFECT-15D27-01).
    """
    def __init__(self, ctx: ManagedEngineContext):
        self.ctx = ctx
        self.released = False
        self.lock = threading.Lock()

    def __call__(self):
        with self.lock:
            if not self.released:
                self.released = True
                self.ctx.release_lease()


class _EngineEventRegistry:
    """
    Authoritative registry of user-registered SQLAlchemy engine event listeners.
    Preserves original function references so that listeners can be cleanly replayed
    and reliably removed across engine rebinding transitions (DEFECT-15D27-02).
    """
    def __init__(self):
        self._listeners: dict = {}
        self._lock = threading.Lock()

    def register(self, identifier: str, fn: Callable, *args, **kwargs):
        fn_key = (id(fn.__func__), id(fn.__self__)) if hasattr(fn, '__func__') else id(fn)
        with self._lock:
            self._listeners[(identifier, fn_key)] = (identifier, fn, args, kwargs)

    def unregister(self, identifier: str, fn: Callable):
        fn_key = (id(fn.__func__), id(fn.__self__)) if hasattr(fn, '__func__') else id(fn)
        with self._lock:
            self._listeners.pop((identifier, fn_key), None)

    def replay_on_engine(self, target_engine):
        with self._lock:
            items = list(self._listeners.values())
        if items:
            target_engine._has_events = True
        for identifier, fn, args, kwargs in items:
            try:
                event.listen(target_engine, identifier, fn, *args, **kwargs)
            except Exception:
                pass


_engine_event_registry = _EngineEventRegistry()


def _create_engine_and_session(db_url: str):
    connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
    eng = create_engine(
        db_url,
        connect_args=connect_args,
        echo=False
    )
    # Intercept dispatch._listen to record user-registered original callbacks
    orig_listen = eng.dispatch._listen

    def _tracking_listen(event_key, *args, **kwargs):
        _engine_event_registry.register(event_key.identifier, event_key.fn, *args, **kwargs)
        return orig_listen(event_key, *args, **kwargs)

    eng.dispatch._listen = _tracking_listen

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

        # Decoupled lease releaser prevents reference cycles with weakref.finalize (DEFECT-15D27-01)
        releaser = _LeaseReleaser(ctx)
        fin = weakref.finalize(conn, releaser)

        orig_close = conn.close

        def _safe_close():
            try:
                orig_close()
            finally:
                fin()

        conn.close = _safe_close
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

    def remove_listener(self, identifier: str, fn: Callable):
        """Explicitly unregisters a listener from both the active engine and the registry (DEFECT-15D27-02)."""
        _engine_event_registry.unregister(identifier, fn)
        with _state_lock:
            active_eng = _current_context.engine
        try:
            event.remove(self, identifier, fn)
        except Exception:
            pass
        try:
            event.remove(active_eng, identifier, fn)
        except Exception:
            pass

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

        # Decoupled lease releaser prevents reference cycles with weakref.finalize (DEFECT-15D27-01)
        releaser = _LeaseReleaser(ctx)
        fin = weakref.finalize(session, releaser)

        orig_close = session.close

        def _safe_close():
            try:
                orig_close()
            finally:
                fin()

        session.close = _safe_close
        return session

    def __getattr__(self, name):
        with _state_lock:
            return getattr(_current_context.session_factory, name)


SessionLocal = _SessionLocalProxy()

Base = declarative_base()


def init_db(target_engine=None):
    """
    Explicitly initializes all database tables using SQLAlchemy declarative metadata.
    Intended for testing fixtures and explicit development setup.
    """
    eng = target_engine or engine
    Base.metadata.create_all(bind=eng)


def reset_database_engine(new_db_url: Optional[str] = None):
    """
    Dynamically rebinds the SQLAlchemy engine and session factory to a specified database URL
    or re-reads settings.DATABASE_URL.
    
    Guarantees:
    - Atomically creates and validates the new engine before retiring the old engine.
    - If engine creation fails, the active engine is preserved completely untouched.
    - Previous engine is retired and only disposed once all active leases have completed.
    - Authoritative event listeners are replayed on the rebound engine using original functions.
    - Thread-safe and deadlock-free.
    """
    global _current_context
    url = new_db_url or settings.DATABASE_URL

    # Step 1: Create and validate new engine and session factory outside state mutation.
    # If this raises any exception, _current_context is completely untouched!
    new_eng, new_sess = _create_engine_and_session(url)

    # Step 2: Replay authoritative event listeners on the new engine (DEFECT-15D27-02)
    _engine_event_registry.replay_on_engine(new_eng)

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
