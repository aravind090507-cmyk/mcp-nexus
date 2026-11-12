import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, Integer, Float, DateTime, ForeignKey, Text, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.database.session import Base
from app.core.permissions import RoleEnum

def generate_uuid() -> str:
    return str(uuid.uuid4())

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    tier = Column(String(50), default="ENTERPRISE")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    servers = relationship("MCPServer", back_populates="organization", cascade="all, delete-orphan")
    agents = relationship("AIAgent", back_populates="organization", cascade="all, delete-orphan")

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), default=RoleEnum.OPERATOR.value, nullable=False)
    is_active = Column(Boolean, default=True)
    department = Column(String(100), default="Operations")
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization = relationship("Organization", back_populates="users")
    approval_requests = relationship("ApprovalRequest", back_populates="requesting_user", foreign_keys="ApprovalRequest.requesting_user_id")

class MCPServer(Base):
    __tablename__ = "mcp_servers"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False)
    name = Column(String(255), nullable=False)
    identifier = Column(String(100), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    transport_type = Column(String(50), default="STDIO")  # STDIO or HTTP_SSE
    endpoint = Column(String(512), nullable=True)         # for HTTP_SSE
    command = Column(String(255), nullable=True)          # for STDIO: python / npx / binary
    args = Column(JSON, default=list)                     # command arguments list
    env_vars = Column(JSON, default=dict)                 # environment variables dict
    auth_method = Column(String(50), default="NONE")      # NONE, BEARER, API_KEY
    auth_token = Column(String(512), nullable=True)
    environment = Column(String(50), default="Production") # Development, Staging, Production
    status = Column(String(50), default="HEALTHY")        # HEALTHY, DEGRADED, UNHEALTHY, DISCONNECTED
    connection_timeout = Column(Integer, default=15)      # in seconds
    is_enabled = Column(Boolean, default=True)
    last_health_check = Column(DateTime, default=datetime.utcnow)
    avg_response_time_ms = Column(Float, default=45.0)
    error_rate = Column(Float, default=0.0)
    total_calls = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization = relationship("Organization", back_populates="servers")
    tools = relationship("MCPTool", back_populates="server", cascade="all, delete-orphan")
    agent_assignments = relationship("AgentServerAssignment", back_populates="server", cascade="all, delete-orphan")

class MCPTool(Base):
    __tablename__ = "mcp_tools"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    server_id = Column(String(36), ForeignKey("mcp_servers.id"), nullable=False)
    name = Column(String(255), index=True, nullable=False)
    description = Column(Text, nullable=True)
    input_schema = Column(JSON, default=dict)
    risk_level = Column(String(50), default="LOW")         # LOW, MEDIUM, HIGH, CRITICAL
    requires_approval = Column(Boolean, default=False)
    is_enabled = Column(Boolean, default=True)
    total_executions = Column(Integer, default=0)
    failed_executions = Column(Integer, default=0)
    last_executed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    server = relationship("MCPServer", back_populates="tools")
    agent_permissions = relationship("AgentToolPermission", back_populates="tool", cascade="all, delete-orphan")

class AIAgent(Base):
    __tablename__ = "ai_agents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False)
    name = Column(String(255), nullable=False)
    identifier = Column(String(100), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    llm_provider = Column(String(50), default="GEMINI")   # GEMINI, OPENAI, ANTHROPIC, DEMO_DETERMINISTIC
    model = Column(String(100), default="gemini-1.5-pro")
    system_prompt = Column(Text, nullable=True)
    status = Column(String(50), default="ACTIVE")         # ACTIVE, INACTIVE, SUSPENDED
    max_execution_steps = Column(Integer, default=5)
    execution_policy = Column(String(50), default="STRICT") # STRICT, PERMISSIVE, AUDITED
    total_orchestrations = Column(Integer, default=0)
    last_active_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization = relationship("Organization", back_populates="agents")
    server_assignments = relationship("AgentServerAssignment", back_populates="agent", cascade="all, delete-orphan")
    tool_permissions = relationship("AgentToolPermission", back_populates="agent", cascade="all, delete-orphan")

class AgentServerAssignment(Base):
    __tablename__ = "agent_server_assignments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    agent_id = Column(String(36), ForeignKey("ai_agents.id"), nullable=False)
    server_id = Column(String(36), ForeignKey("mcp_servers.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    agent = relationship("AIAgent", back_populates="server_assignments")
    server = relationship("MCPServer", back_populates="agent_assignments")

class AgentToolPermission(Base):
    __tablename__ = "agent_tool_permissions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    agent_id = Column(String(36), ForeignKey("ai_agents.id"), nullable=False)
    tool_id = Column(String(36), ForeignKey("mcp_tools.id"), nullable=False)
    is_permitted = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    agent = relationship("AIAgent", back_populates="tool_permissions")
    tool = relationship("MCPTool", back_populates="agent_permissions")

class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    requesting_user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    agent_id = Column(String(36), ForeignKey("ai_agents.id"), nullable=True)
    server_id = Column(String(36), ForeignKey("mcp_servers.id"), nullable=False)
    tool_id = Column(String(36), ForeignKey("mcp_tools.id"), nullable=False)
    operation_description = Column(Text, nullable=False)
    parameters = Column(JSON, default=dict)
    risk_level = Column(String(50), default="HIGH")       # HIGH, CRITICAL
    status = Column(String(50), default="PENDING")        # PENDING, APPROVED, REJECTED, EXECUTED
    reason = Column(Text, nullable=True)
    reviewed_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    requesting_user = relationship("User", foreign_keys=[requesting_user_id], back_populates="approval_requests")
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    server = relationship("MCPServer")
    tool = relationship("MCPTool")
    agent = relationship("AIAgent")

class ExecutionTrace(Base):
    __tablename__ = "execution_traces"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    trace_id = Column(String(64), index=True, nullable=False)
    request_id = Column(String(64), index=True, nullable=False)
    user_id = Column(String(36), nullable=True)
    agent_id = Column(String(36), nullable=True)
    server_id = Column(String(36), nullable=True)
    server_name = Column(String(255), nullable=True)
    tool_name = Column(String(255), nullable=False)
    user_query = Column(Text, nullable=True)
    input_parameters = Column(JSON, default=dict)
    output_response = Column(JSON, default=dict)
    error_details = Column(Text, nullable=True)
    status = Column(String(50), default="SUCCESS")        # SUCCESS, FAILED, BLOCKED, PENDING_APPROVAL
    duration_ms = Column(Float, default=0.0)
    risk_level = Column(String(50), default="LOW")
    authorization_decision = Column(String(50), default="PERMITTED") # PERMITTED, DENIED, ELEVATED
    policy_evaluated = Column(String(255), nullable=True)
    spans = Column(JSON, default=list)                   # Timeline breakdown array: [UserReq, AgentDec, PolicyVal, MCPDispatch, ToolExec, Resp]
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

class SecurityEvent(Base):
    __tablename__ = "security_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    event_type = Column(String(100), nullable=False)      # UNAUTHORIZED_ACCESS, POLICY_VIOLATION, BLOCKED_TOOL, APPROVAL_REQUESTED
    severity = Column(String(50), default="MEDIUM")       # LOW, MEDIUM, HIGH, CRITICAL
    actor = Column(String(255), nullable=False)           # User or Agent identifier
    target_resource = Column(String(255), nullable=False) # Server / Tool name
    description = Column(Text, nullable=False)
    ip_address = Column(String(45), default="127.0.0.1")
    metadata_json = Column(JSON, default=dict)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    action = Column(String(100), nullable=False)          # CREATE_SERVER, EXECUTE_TOOL, APPROVE_REQUEST, POLICY_CHANGE
    entity_type = Column(String(100), nullable=False)     # SERVER, TOOL, AGENT, POLICY, APPROVAL
    entity_id = Column(String(64), nullable=False)
    user_name = Column(String(255), default="System")
    role = Column(String(50), default="ADMIN")
    details = Column(Text, nullable=True)
    diff = Column(JSON, default=dict)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

class IntegrationConfig(Base):
    __tablename__ = "integration_configs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    system_type = Column(String(50), nullable=False)      # ERP, INVENTORY, EQUIPMENT, HR, PROCUREMENT
    vendor = Column(String(100), default="SAP S/4HANA")   # e.g. SAP, Oracle, Maximo
    status = Column(String(50), default="CONNECTED")      # CONNECTED, SYNCING, ERROR, OFFLINE
    endpoint = Column(String(512), nullable=True)
    linked_mcp_server = Column(String(100), nullable=True)
    sync_interval_mins = Column(Integer, default=15)
    last_sync = Column(DateTime, default=datetime.utcnow)
    stats = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
