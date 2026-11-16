import os
import sys
from logging.config import fileConfig

from sqlalchemy import pool, create_engine
from alembic import context

# Ensure backend and root are on sys.path
ALEMBIC_DIR = os.path.abspath(os.path.dirname(__file__))
BACKEND_DIR = os.path.abspath(os.path.join(ALEMBIC_DIR, ".."))
ROOT_DIR = os.path.abspath(os.path.join(BACKEND_DIR, ".."))

for p in (BACKEND_DIR, ROOT_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

# Import models and Base
from app.core.config import settings
from app.database.session import Base
import app.models.all_models  # Registers all 13 models on Base.metadata

config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    try:
        fileConfig(config.config_file_name)
    except Exception:
        pass

target_metadata = Base.metadata


def get_url() -> str:
    """
    Resolves the authoritative database URL for Alembic migrations.
    Priority:
    1. Direct CLI argument: -x db_url=<url>
    2. POSTGRES_TEST_DATABASE_URL (if set during test/CI execution)
    3. Environment variable DATABASE_URL
    4. Application settings.DATABASE_URL
    """
    x_args = context.get_x_argument(as_dictionary=True)
    if x_args.get("db_url"):
        return x_args["db_url"]

    # Check programmatic or explicitly configured sqlalchemy.url
    ini_url = config.get_main_option("sqlalchemy.url")
    if ini_url and not ini_url.startswith("driver://"):
        return ini_url

    if os.getenv("POSTGRES_TEST_DATABASE_URL") and os.getenv("ENVIRONMENT") == "Testing":
        return os.getenv("POSTGRES_TEST_DATABASE_URL")

    if os.getenv("DATABASE_URL"):
        return os.getenv("DATABASE_URL")

    return getattr(settings, "DATABASE_URL", "sqlite:///./mcp_nexus.db")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=url.startswith("sqlite"),
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    url = get_url()
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}

    # Use a standard SQLAlchemy Engine directly rather than the custom proxy,
    # ensuring complete compatibility with Alembic's transaction and DDL management.
    connectable = create_engine(
        url,
        connect_args=connect_args,
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=url.startswith("sqlite"),
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
