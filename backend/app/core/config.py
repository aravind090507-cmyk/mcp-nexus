from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional, Dict, Any
import os
import sys
from dotenv import load_dotenv

VALID_ENVIRONMENTS = ("Development", "Testing", "Staging", "Production")

def _resolve_and_load_environment() -> str:
    """
    Identifies the active environment profile and securely loads the corresponding
    configuration file with strict fail-closed validation.

    Guarantees:
    - 'Staging': Strictly requires .env.staging. Fails fast if missing.
    - 'Staging' / 'Testing': Rejects any DATABASE_URL physically resolving to 'mcp_nexus.db'.
    - 'Development': Loads .env if present, otherwise defaults to local dev settings.
    - 'Production': Rejects default secrets, sqlite databases, and wildcard persistent sessions.
    - Ambiguous or unknown environments fail fast.
    """
    raw_env = os.getenv("ENVIRONMENT", "Development").strip()
    env = raw_env.capitalize()

    if env not in VALID_ENVIRONMENTS:
        raise RuntimeError(
            f"CRITICAL CONFIGURATION ERROR: Invalid or ambiguous ENVIRONMENT '{raw_env}'. "
            f"Allowed environments are strictly: {', '.join(VALID_ENVIRONMENTS)}."
        )

    # Locate candidate directories for env files
    curr_dir = os.path.abspath(os.getcwd())
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    search_dirs = [curr_dir, repo_root, backend_root]

    dev_db_canonical = os.path.normcase(os.path.realpath(os.path.abspath(os.path.join(repo_root, "mcp_nexus.db"))))

    if env == "Staging":
        staging_file = None
        for d in search_dirs:
            candidate = os.path.join(d, ".env.staging")
            if os.path.isfile(candidate):
                staging_file = candidate
                break

        if not staging_file:
            raise RuntimeError(
                "CRITICAL CONFIGURATION ERROR: ENVIRONMENT is set to 'Staging' but '.env.staging' "
                "could not be located in search paths. Startup aborted to prevent selecting the development database."
            )

        # Explicitly load staging environment variables if not already set in process environment
        load_dotenv(staging_file, override=False)

        # Verify database URL does not physically resolve to development database
        db_url = os.getenv("DATABASE_URL", "")
        if db_url.startswith("sqlite:///"):
            sqlite_path = os.path.normcase(os.path.realpath(os.path.abspath(db_url.replace("sqlite:///", ""))))
            if sqlite_path == dev_db_canonical or ("mcp_nexus.db" in db_url and "staging" not in db_url):
                raise RuntimeError(
                    f"CRITICAL CONFIGURATION ERROR: Staging environment DATABASE_URL is misconfigured ('{db_url}'). "
                    f"It physically resolves to the development database ('{dev_db_canonical}'). "
                    f"Staging must strictly resolve to 'mcp_nexus_staging.db'."
                )
        elif "mcp_nexus.db" in db_url and "staging" not in db_url:
            raise RuntimeError(
                f"CRITICAL CONFIGURATION ERROR: Staging environment DATABASE_URL is misconfigured ('{db_url}'). "
                f"Staging must strictly resolve to 'mcp_nexus_staging.db'."
            )

    elif env == "Testing":
        # Testing environment must never point to development database
        db_url = os.getenv("DATABASE_URL", "")
        if db_url.startswith("sqlite:///"):
            sqlite_path = os.path.normcase(os.path.realpath(os.path.abspath(db_url.replace("sqlite:///", ""))))
            if sqlite_path == dev_db_canonical:
                raise RuntimeError(
                    f"CRITICAL CONFIGURATION ERROR: Testing environment cannot use the development database ('{dev_db_canonical}')."
                )

    elif env == "Production":
        prod_secret = os.getenv("SECRET_KEY", "")
        if not prod_secret or len(prod_secret) < 32 or any(k in prod_secret.lower() for k in ("supersecret", "xyz", "vault", "default", "changeme")):
            raise RuntimeError(
                "CRITICAL CONFIGURATION ERROR: Production SECRET_KEY must be a valid, cryptographically secure "
                "enterprise secret of at least 32 characters."
            )
        prod_db = os.getenv("DATABASE_URL", "")
        if not prod_db or "sqlite" in prod_db.lower():
            raise RuntimeError("CRITICAL CONFIGURATION ERROR: Production environment cannot use SQLite database.")

        # Wildcard persistent MCP session allowlist is strictly forbidden in Production
        persistent_servers = os.getenv("PERSISTENT_MCP_SERVERS", "")
        if persistent_servers.strip() == "*":
            raise RuntimeError(
                "CRITICAL CONFIGURATION ERROR: Wildcard PERSISTENT_MCP_SERVERS='*' is strictly forbidden in Production. "
                "Explicit, audited server identifiers are required."
            )

    else:
        # Development default
        for d in search_dirs:
            candidate = os.path.join(d, ".env")
            if os.path.isfile(candidate):
                load_dotenv(candidate, override=False)
                break

    return env

_active_env = _resolve_and_load_environment()

class Settings(BaseSettings):
    PROJECT_NAME: str = "MCP NEXUS"
    TAGLINE: str = "CONNECT. ORCHESTRATE. GOVERN."
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"

    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", _active_env)
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "mcp-nexus-enterprise-vault-supersecret-key-2026-xyz")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Database: Default to sqlite file for zero-config out-of-the-box run, easily switched to Postgres via DATABASE_URL
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./mcp_nexus.db")

    # LLM Provider Configuration
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "DEMO_DETERMINISTIC") # DEMO_DETERMINISTIC, OPENAI, ANTHROPIC, GEMINI
    LLM_API_KEY: Optional[str] = os.getenv("LLM_API_KEY", None)
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gemini-1.5-pro")

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://localhost:8000"
    ]

    # MCP Protocol & Session Management
    ENABLE_PERSISTENT_MCP_SESSIONS: bool = os.getenv("ENABLE_PERSISTENT_MCP_SESSIONS", "False").lower() == "true"
    PERSISTENT_MCP_SERVERS: str = os.getenv("PERSISTENT_MCP_SERVERS", "")  # Comma-separated server identifiers (empty = none eligible)
    PERSISTENT_MCP_FALLBACK_TO_LEGACY: bool = os.getenv("PERSISTENT_MCP_FALLBACK_TO_LEGACY", "True").lower() == "true"
    PERSISTENT_MCP_PREWARM_ON_STARTUP: bool = os.getenv("PERSISTENT_MCP_PREWARM_ON_STARTUP", "False").lower() == "true"
    MCP_HEARTBEAT_INTERVAL_SECONDS: float = float(os.getenv("MCP_HEARTBEAT_INTERVAL_SECONDS", "30.0"))
    MCP_SESSION_RECONNECT_MAX_RETRIES: int = int(os.getenv("MCP_SESSION_RECONNECT_MAX_RETRIES", "3"))
    MCP_SESSION_PING_TIMEOUT_SECONDS: float = float(os.getenv("MCP_SESSION_PING_TIMEOUT_SECONDS", "5.0"))

    # Canary Readiness & Deployment Governance Thresholds (Task H)
    CANARY_MIN_SUCCESS_RATE_PCT: float = float(os.getenv("CANARY_MIN_SUCCESS_RATE_PCT", "99.0"))
    CANARY_MAX_P95_LATENCY_MS: float = float(os.getenv("CANARY_MAX_P95_LATENCY_MS", "150.0"))
    CANARY_MAX_P99_LATENCY_MS: float = float(os.getenv("CANARY_MAX_P99_LATENCY_MS", "350.0"))
    CANARY_MAX_INIT_FAILURES: int = int(os.getenv("CANARY_MAX_INIT_FAILURES", "0"))
    CANARY_MAX_HEARTBEAT_FAILURES: int = int(os.getenv("CANARY_MAX_HEARTBEAT_FAILURES", "0"))
    CANARY_MAX_MEMORY_GROWTH_MB: float = float(os.getenv("CANARY_MAX_MEMORY_GROWTH_MB", "50.0"))
    CANARY_ROLLBACK_TARGET_MS: float = float(os.getenv("CANARY_ROLLBACK_TARGET_MS", "2000.0"))
    CANARY_MIN_OBSERVATIONS: int = int(os.getenv("CANARY_MIN_OBSERVATIONS", "50"))

    model_config = SettingsConfigDict(case_sensitive=True, extra="ignore")

    def resolve_absolute_db_path(self) -> str:
        """Returns the fully resolved absolute filesystem path of the active SQLite database."""
        if self.DATABASE_URL.startswith("sqlite:///"):
            raw_path = self.DATABASE_URL.replace("sqlite:///", "")
            return os.path.abspath(raw_path)
        return self.DATABASE_URL

    def validate_startup_configuration(self) -> Dict[str, Any]:
        """
        Executes comprehensive fail-closed startup validation across all environments.
        Raises RuntimeError on any misconfiguration.
        """
        env = self.ENVIRONMENT.capitalize()
        if env not in VALID_ENVIRONMENTS:
            raise RuntimeError(f"Startup check failed: Invalid ENVIRONMENT '{self.ENVIRONMENT}'.")

        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        dev_db_canonical = os.path.normcase(os.path.realpath(os.path.abspath(os.path.join(repo_root, "mcp_nexus.db"))))

        if env in ("Staging", "Testing") and self.DATABASE_URL.startswith("sqlite:///"):
            active_path = os.path.normcase(os.path.realpath(os.path.abspath(self.DATABASE_URL.replace("sqlite:///", ""))))
            if active_path == dev_db_canonical:
                raise RuntimeError(
                    f"Startup check failed: {env} environment is bound to development database '{dev_db_canonical}'."
                )

        if env == "Production":
            if not self.SECRET_KEY or len(self.SECRET_KEY) < 32 or any(k in self.SECRET_KEY.lower() for k in ("supersecret", "xyz", "vault", "default")):
                raise RuntimeError("Startup check failed: Insecure SECRET_KEY in Production.")
            if "sqlite" in self.DATABASE_URL.lower():
                raise RuntimeError("Startup check failed: SQLite is strictly forbidden in Production.")
            if self.PERSISTENT_MCP_SERVERS.strip() == "*":
                raise RuntimeError("Startup check failed: Wildcard PERSISTENT_MCP_SERVERS='*' forbidden in Production.")

        return {
            "environment": env,
            "status": "VALIDATED",
            "database_url_safe": True,
            "security_valid": True,
            "persistent_sessions_default": not self.ENABLE_PERSISTENT_MCP_SESSIONS
        }

    @classmethod
    def reload_for_environment(cls, env_name: str) -> "Settings":
        """Re-evaluates and switches settings for a given environment (Development, Testing, Staging, Production)."""
        os.environ["ENVIRONMENT"] = env_name
        _resolve_and_load_environment()
        new_instance = cls()
        return new_instance

settings = Settings()
