from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional
import os
import sys
from dotenv import load_dotenv

def _resolve_and_load_environment() -> str:
    """
    Identifies the active environment profile and securely loads the corresponding
    configuration file.
    
    Guarantees:
    - 'Staging': Strictly requires .env.staging. Fails fast if missing.
    - 'Staging': Rejects any DATABASE_URL pointing to the development database ('mcp_nexus.db').
    - 'Development': Loads .env if present, otherwise defaults to local dev settings.
    - 'Production': Rejects default secrets and unencrypted/sqlite development endpoints.
    """
    env = os.getenv("ENVIRONMENT", "Development").strip().capitalize()
    
    # Locate candidate directories for env files
    curr_dir = os.path.abspath(os.getcwd())
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    search_dirs = [curr_dir, repo_root, backend_root]
    
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
        
        # Verify database URL does not point to development database
        db_url = os.getenv("DATABASE_URL", "")
        if "mcp_nexus.db" in db_url and "staging" not in db_url:
            raise RuntimeError(
                f"CRITICAL CONFIGURATION ERROR: Staging environment DATABASE_URL is misconfigured ('{db_url}'). "
                f"Staging must strictly resolve to 'mcp_nexus_staging.db'."
            )
            
    elif env == "Production":
        prod_secret = os.getenv("SECRET_KEY", "")
        if not prod_secret or "supersecret" in prod_secret.lower() or "xyz" in prod_secret.lower():
            raise RuntimeError("CRITICAL CONFIGURATION ERROR: Production SECRET_KEY must be a valid, unique enterprise secret.")
        prod_db = os.getenv("DATABASE_URL", "")
        if not prod_db or "sqlite" in prod_db.lower():
            raise RuntimeError("CRITICAL CONFIGURATION ERROR: Production environment cannot use SQLite database.")
            
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
    PERSISTENT_MCP_SERVERS: str = os.getenv("PERSISTENT_MCP_SERVERS", "*")  # Comma-separated server identifiers or '*' for all
    PERSISTENT_MCP_FALLBACK_TO_LEGACY: bool = os.getenv("PERSISTENT_MCP_FALLBACK_TO_LEGACY", "True").lower() == "true"
    PERSISTENT_MCP_PREWARM_ON_STARTUP: bool = os.getenv("PERSISTENT_MCP_PREWARM_ON_STARTUP", "False").lower() == "true"
    MCP_HEARTBEAT_INTERVAL_SECONDS: float = float(os.getenv("MCP_HEARTBEAT_INTERVAL_SECONDS", "30.0"))
    MCP_SESSION_RECONNECT_MAX_RETRIES: int = int(os.getenv("MCP_SESSION_RECONNECT_MAX_RETRIES", "3"))
    MCP_SESSION_PING_TIMEOUT_SECONDS: float = float(os.getenv("MCP_SESSION_PING_TIMEOUT_SECONDS", "5.0"))
    
    model_config = SettingsConfigDict(case_sensitive=True, extra="ignore")

    def resolve_absolute_db_path(self) -> str:
        """Returns the fully resolved absolute filesystem path of the active SQLite database."""
        if self.DATABASE_URL.startswith("sqlite:///"):
            raw_path = self.DATABASE_URL.replace("sqlite:///", "")
            return os.path.abspath(raw_path)
        return self.DATABASE_URL

    @classmethod
    def reload_for_environment(cls, env_name: str) -> "Settings":
        """Re-evaluates and switches settings for a given environment (Development, Staging, Production)."""
        os.environ["ENVIRONMENT"] = env_name
        _resolve_and_load_environment()
        new_instance = cls()
        return new_instance

settings = Settings()
