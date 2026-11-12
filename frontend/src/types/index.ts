export type Role = 'SUPER_ADMIN' | 'ADMIN' | 'DEVELOPER' | 'OPERATOR' | 'VIEWER';

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  department?: string;
  is_active: boolean;
}

export interface MCPTool {
  id: string;
  server_id: string;
  name: string;
  description?: string;
  input_schema: Record<string, any>;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  requires_approval: boolean;
  is_enabled: boolean;
  total_executions: number;
  failed_executions: number;
  last_executed_at?: string;
}

export interface MCPServer {
  id: string;
  name: string;
  identifier: string;
  description?: string;
  transport_type: 'STDIO' | 'HTTP_SSE';
  endpoint?: string;
  command?: string;
  args?: string[];
  environment: 'Development' | 'Staging' | 'Production';
  status: 'HEALTHY' | 'DEGRADED' | 'UNHEALTHY' | 'DISCONNECTED';
  connection_timeout: number;
  is_enabled: boolean;
  last_health_check?: string;
  avg_response_time_ms: number;
  error_rate: number;
  total_calls: number;
  tools: MCPTool[];
}

export interface AIAgent {
  id: string;
  name: string;
  identifier: string;
  description?: string;
  llm_provider: string;
  model: string;
  status: 'ACTIVE' | 'INACTIVE' | 'SUSPENDED';
  max_execution_steps: number;
  execution_policy: 'STRICT' | 'PERMISSIVE' | 'AUDITED';
  total_orchestrations: number;
  last_active_at?: string;
  created_at: string;
}

export interface Span {
  stage: 'USER_REQUEST' | 'AGENT_DECISION' | 'POLICY_VALIDATION' | 'MCP_SERVER' | 'TOOL_EXECUTION' | 'RESPONSE';
  name: string;
  status: 'COMPLETED' | 'BLOCKED' | 'FAILED' | 'PENDING';
  timestamp: string;
  duration_ms: number;
  details: Record<string, any>;
}

export interface ExecutionTrace {
  id: string;
  trace_id: string;
  request_id: string;
  agent_id?: string;
  server_name?: string;
  tool_name: string;
  user_query?: string;
  status: 'SUCCESS' | 'FAILED' | 'BLOCKED' | 'PENDING_APPROVAL';
  duration_ms: number;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  authorization_decision: string;
  created_at: string;
  input_parameters?: Record<string, any>;
  output_response?: Record<string, any>;
  error_details?: string;
  spans?: Span[];
}

export interface ApprovalRequest {
  id: string;
  requesting_user: string;
  agent_name?: string;
  server_name: string;
  tool_name: string;
  operation_description: string;
  parameters: Record<string, any>;
  risk_level: 'HIGH' | 'CRITICAL';
  status: 'PENDING' | 'PARTIALLY_APPROVED' | 'APPROVED' | 'REJECTED' | 'EXPIRED' | 'EXECUTED' | 'EXECUTION_FAILED';
  requires_dual_approval?: boolean;
  first_approver_name?: string;
  first_approved_at?: string;
  second_approver_name?: string;
  second_approved_at?: string;
  expires_at?: string;
  created_at: string;
  reviewed_at?: string;
}

export interface SecurityEvent {
  id: string;
  event_type: string;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  actor: string;
  target_resource: string;
  description: string;
  ip_address: string;
  timestamp: string;
}

export interface AuditLog {
  id: string;
  action: string;
  entity_type: string;
  entity_id: string;
  user_name: string;
  role: string;
  details?: string;
  diff?: Record<string, any>;
  timestamp: string;
}

export interface SecurityPolicy {
  id: string;
  name: string;
  description?: string;
  action: 'ALLOW' | 'DENY' | 'REQUIRE_APPROVAL';
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' | 'ANY';
  environment: 'ALL' | 'PRODUCTION' | 'STAGING' | 'DEVELOPMENT';
  scope: 'GLOBAL' | 'SERVER' | 'TOOL';
  server_id?: string;
  tool_pattern?: string;
  argument_conditions?: Record<string, any>;
  is_enabled: boolean;
  created_at: string;
  updated_at?: string;
}

export interface IntegrationConfig {
  id: string;
  name: string;
  system_type: 'ERP' | 'EQUIPMENT' | 'INVENTORY' | 'HR' | 'PROCUREMENT';
  vendor: string;
  status: 'CONNECTED' | 'SYNCING' | 'ERROR' | 'OFFLINE';
  endpoint?: string;
  linked_mcp_server?: string;
  sync_interval_mins: number;
  last_sync: string;
  stats?: Record<string, any>;
}

export interface CommandCenterMetrics {
  top_metrics: {
    registered_servers: number;
    active_servers: number;
    connected_agents: number;
    total_executions: number;
    failed_executions: number;
    pending_approvals: number;
    success_rate_pct: number;
  };
  server_distribution: { name: string; count: number; color: string }[];
  infra_health: {
    id: string;
    name: string;
    identifier: string;
    transport: string;
    environment: string;
    status: string;
    avg_response_time_ms: number;
    error_rate: number;
    total_calls: number;
    last_health_check?: string;
    is_enabled: boolean;
  }[];
  activity_chart: { time: string; executions: number; errors: number }[];
  recent_executions: {
    id: string;
    trace_id: string;
    timestamp: string;
    agent_name: string;
    mcp_server: string;
    tool_executed: string;
    duration_ms: number;
    status: string;
    risk_level: string;
  }[];
  security_events: {
    id: string;
    type: string;
    severity: string;
    actor: string;
    resource: string;
    description: string;
    timestamp: string;
  }[];
  system_timeline: {
    id: string;
    action: string;
    entity: string;
    user: string;
    role: string;
    details: string;
    timestamp: string;
  }[];
}
