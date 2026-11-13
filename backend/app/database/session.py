from typing import Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

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
engine = _current_engine

class _SessionLocalProxy:
    """
    Transparent proxy to the active SQLAlchemy session factory.
    Ensures that when reset_database_engine is called (e.g. for isolated test databases),
    all modules holding a reference to SessionLocal automatically route to the rebound database.
    """
    def __call__(self, *args, **kwargs):
        return _current_session_factory(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(_current_session_factory, name)

SessionLocal = _SessionLocalProxy()

Base = declarative_base()

def reset_database_engine(new_db_url: Optional[str] = None):
    """
    Dynamically rebinds the SQLAlchemy engine and session factory to a specified database URL
    or re-reads settings.DATABASE_URL. Used for environment transitions and isolated test harnesses.
    """
    global _current_engine, _current_session_factory, engine
    url = new_db_url or settings.DATABASE_URL
    _current_engine, _current_session_factory = _create_engine_and_session(url)
    engine = _current_engine
    return engine, SessionLocal

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
