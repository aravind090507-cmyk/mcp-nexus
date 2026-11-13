from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional
import os

class Settings(BaseSettings):
    PROJECT_NAME: str = "MCP NEXUS"
    TAGLINE: str = "CONNECT. ORCHESTRATE. GOVERN."
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "Development")
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

settings = Settings()
