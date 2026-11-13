from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime

# --- AUTH & USER ---
class UserLogin(BaseModel):
    email: str
    password: str

class UserCreate(BaseModel):
    email: str
    full_name: str
    password: str
    role: str = "OPERATOR"
    department: Optional[str] = "Operations"

class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    department: Optional[str] = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

# --- MCP SERVERS ---
class MCPServerCreate(BaseModel):
    name: str
    identifier: str
    description: Optional[str] = None
    transport_type: str = "STDIO"
    endpoint: Optional[str] = None
    command: Optional[str] = None
    args: List[str] = Field(default_factory=list)
    env_vars: Dict[str, str] = Field(default_factory=dict)
    auth_method: str = "NONE"
    auth_token: Optional[str] = None
    environment: str = "Production"
    connection_timeout: int = 15

class MCPServerUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    endpoint: Optional[str] = None
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env_vars: Optional[Dict[str, str]] = None
    environment: Optional[str] = None
    is_enabled: Optional[bool] = None
    connection_timeout: Optional[int] = None

class ServerDiscoverRequest(BaseModel):
    transport_type: str = "STDIO" # STDIO, HTTP_SSE, HTTP
    command: Optional[str] = None
    args: List[str] = []
    endpoint: Optional[str] = None
    env_vars: Dict[str, str] = {}
    auth_token: Optional[str] = None

class ServerDiscoverResponse(BaseModel):
    success: bool
    protocol_version: str = "2024-11-05"
    server_info: Dict[str, Any] = {}
    capabilities: Dict[str, Any] = {}
    discovered_tools: List[Dict[str, Any]] = []
    discovered_resources: List[Dict[str, Any]] = []
    discovered_prompts: List[Dict[str, Any]] = []
    latency_ms: float = 0.0
    error: Optional[str] = None

class MCPToolOut(BaseModel):
    id: str
    server_id: str
    name: str
    description: Optional[str] = None
    input_schema: Dict[str, Any]
    risk_level: str
    requires_approval: bool
    is_enabled: bool
    total_executions: int
    failed_executions: int
    last_executed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class MCPToolUpdate(BaseModel):
    risk_level: Optional[str] = None
    requires_approval: Optional[bool] = None
    is_enabled: Optional[bool] = None
    description: Optional[str] = None

class MCPServerOut(BaseModel):
    id: str
    name: str
    identifier: str
    description: Optional[str] = None
    transport_type: str
    endpoint: Optional[str] = None
    command: Optional[str] = None
    args: List[str] = []
    environment: str
    status: str
    connection_timeout: int
    is_enabled: bool
    last_health_check: Optional[datetime] = None
    avg_response_time_ms: float
    error_rate: float
    total_calls: int
    tools: List[MCPToolOut] = []

    model_config = ConfigDict(from_attributes=True)

# --- TOOL PLAYGROUND ---
class ToolExecuteRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)

class ToolExecuteResponse(BaseModel):
    tool_name: str
    server_name: str
    is_success: bool
    duration_ms: float
    result: Any
    error: Optional[str] = None
    trace_id: Optional[str] = None

# --- AGENTS ---
class AIAgentCreate(BaseModel):
    name: str
    identifier: str
    description: Optional[str] = None
    llm_provider: str = "GEMINI"
    model: str = "gemini-1.5-pro"
    system_prompt: Optional[str] = None
    max_execution_steps: int = 5
    execution_policy: str = "STRICT"
    assigned_server_ids: List[str] = []

class AIAgentOut(BaseModel):
    id: str
    name: str
    identifier: str
    description: Optional[str] = None
    llm_provider: str
    model: str
    status: str
    max_execution_steps: int
    execution_policy: str
    total_orchestrations: int
    last_active_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class OrchestrationRequest(BaseModel):
    agent_id: str
    prompt: str

class OrchestrationResponse(BaseModel):
    trace_id: str
    request_id: str
    agent_name: str
    model: str
    execution_mode: str
    overall_status: str
    duration_ms: float
    synthesis: str
    tool_executions: List[Dict[str, Any]]
    spans: List[Dict[str, Any]]
    risk_assessment: Optional[Dict[str, Any]] = None

# --- ENTERPRISE WORKFLOWS ---
class WorkflowExecutionRequest(BaseModel):
    workflow_id: Optional[str] = "construction-risk-intelligence"
    prompt: Optional[str] = "Identify construction projects at risk due to delayed milestones, equipment failures and insufficient inventory."
    agent_id: Optional[str] = None
    project_filter: Optional[str] = None

class WorkflowExecutionResponse(BaseModel):
    workflow_id: str
    workflow_name: str
    trace_id: str
    execution_status: str
    duration_ms: float
    server_progress: Dict[str, Any]
    risk_assessment: Dict[str, Any]
    synthesis: str
    tool_executions: List[Dict[str, Any]]
    spans: List[Dict[str, Any]]
    dataset_notice: str

# --- GOVERNANCE & APPROVALS ---
class ApprovalOut(BaseModel):
    id: str
    requesting_user: str
    agent_name: Optional[str] = None
    server_name: str
    tool_name: str
    operation_description: str
    parameters: Dict[str, Any]
    risk_level: str
    status: str
    requires_dual_approval: bool = False
    first_approver_name: Optional[str] = None
    first_approved_at: Optional[datetime] = None
    second_approver_name: Optional[str] = None
    second_approved_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime
    reviewed_at: Optional[datetime] = None

class ApprovalActionRequest(BaseModel):
    action: str # APPROVE or REJECT
    reason: Optional[str] = None

# --- SECURITY POLICIES ---
class SecurityPolicyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    action: str = "REQUIRE_APPROVAL" # ALLOW, DENY, REQUIRE_APPROVAL
    risk_level: str = "HIGH"         # LOW, MEDIUM, HIGH, CRITICAL, ANY
    environment: str = "ALL"         # ALL, PRODUCTION, STAGING, DEVELOPMENT
    scope: str = "GLOBAL"            # GLOBAL, SERVER, TOOL
    server_id: Optional[str] = None
    tool_pattern: Optional[str] = None
    argument_conditions: Dict[str, Any] = {}
    is_enabled: bool = True

class SecurityPolicyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    action: Optional[str] = None
    risk_level: Optional[str] = None
    environment: Optional[str] = None
    scope: Optional[str] = None
    server_id: Optional[str] = None
    tool_pattern: Optional[str] = None
    argument_conditions: Optional[Dict[str, Any]] = None
    is_enabled: Optional[bool] = None

class SecurityPolicyOut(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    action: str
    risk_level: str
    environment: str
    scope: str
    server_id: Optional[str] = None
    tool_pattern: Optional[str] = None
    argument_conditions: Dict[str, Any] = {}
    is_enabled: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class SecurityEventOut(BaseModel):
    id: str
    event_type: str
    severity: str
    actor: str
    target_resource: str
    description: str
    ip_address: str
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)

class AuditLogOut(BaseModel):
    id: str
    action: str
    entity_type: str
    entity_id: str
    user_name: str
    role: str
    details: Optional[str] = None
    diff: Dict[str, Any] = {}
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)

# --- TRACES ---
class TraceOut(BaseModel):
    id: str
    trace_id: str
    request_id: str
    agent_id: Optional[str] = None
    server_name: Optional[str] = None
    tool_name: str
    user_query: Optional[str] = None
    status: str
    duration_ms: float
    risk_level: str
    authorization_decision: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class TraceDetailOut(TraceOut):
    input_parameters: Dict[str, Any]
    output_response: Dict[str, Any]
    error_details: Optional[str] = None
    spans: List[Dict[str, Any]] = []

# --- DEPLOYMENT GOVERNANCE & CANARY READINESS ---
class DeploymentTransitionRequest(BaseModel):
    target_state: str
    reason: str

class DeploymentStateOut(BaseModel):
    server_id: str
    server_name: str
    deployment_state: str
    history: List[Dict[str, Any]] = []

class CanaryEligibilityOut(BaseModel):
    is_eligible: bool
    reason: str
    server_id: str
    server_name: str
    environment: str
    evaluated_at: str
    deployment_state: str
    policy_allowed: bool
    details: Dict[str, Any] = {}
