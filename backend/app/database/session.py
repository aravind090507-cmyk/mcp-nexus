import threading
from typing import Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

_engine_lock = threading.RLock()
_current_engine = None
_current_session_factory = None

def _create_engine_and_session(db_url: str):
    connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
    eng = create_engine(
        db_url,
        connect_args=connect_args,
        echo=False
    )
    sess_factory = sessionmaker(autocommit=False, autoflush=False, bind=eng)
    return eng, sess_factory

_current_engine, _current_session_factory = _create_engine_and_session(settings.DATABASE_URL)

class _EngineProxy:
    """
    Transparent proxy to the active SQLAlchemy engine.
    Ensures that any module that imported engine directly always routes
    its connections, executions, and DDL bindings to the active rebound engine.
    """
    def __getattr__(self, name):
        with _engine_lock:
            return getattr(_current_engine, name)

    def __repr__(self):
        with _engine_lock:
            return repr(_current_engine)

engine = _EngineProxy()

class _SessionLocalProxy:
    """
    Transparent proxy to the active SQLAlchemy session factory.
    Ensures that when reset_database_engine is called (e.g. for isolated test databases),
    all modules holding a reference to SessionLocal automatically route to the rebound database.
    """
    def __call__(self, *args, **kwargs):
        with _engine_lock:
            factory = _current_session_factory
        return factory(*args, **kwargs)

    def __getattr__(self, name):
        with _engine_lock:
            return getattr(_current_session_factory, name)

SessionLocal = _SessionLocalProxy()

Base = declarative_base()

def reset_database_engine(new_db_url: Optional[str] = None):
    """
    Dynamically rebinds the SQLAlchemy engine and session factory to a specified database URL
    or re-reads settings.DATABASE_URL. Used for environment transitions and isolated test harnesses.
    Thread-safe and disposes of the previously active engine to prevent resource leaks.
    """
    global _current_engine, _current_session_factory
    with _engine_lock:
        old_engine = _current_engine
        url = new_db_url or settings.DATABASE_URL
        new_eng, new_sess = _create_engine_and_session(url)
        _current_engine = new_eng
        _current_session_factory = new_sess
        if old_engine is not None and old_engine is not new_eng:
            try:
                old_engine.dispose()
            except Exception:
                pass
    return _current_engine, SessionLocal

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
