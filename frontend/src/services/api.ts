import type {
  MCPServer,
  MCPTool,
  AIAgent,
  ExecutionTrace,
  ApprovalRequest,
  SecurityEvent,
  AuditLog,
  SecurityPolicy,
  IntegrationConfig,
  CommandCenterMetrics,
  User,
  Role
} from '../types';

const API_BASE = '/api/v1';

let activeRole: Role = (localStorage.getItem('mcp_nexus_role') as Role) || 'SUPER_ADMIN';
let authToken: string | null = localStorage.getItem('mcp_nexus_token') || null;

export const getActiveRole = (): Role => activeRole;
export const getAuthToken = (): string | null => authToken;

export const setActiveRole = async (role: Role) => {
  activeRole = role;
  localStorage.setItem('mcp_nexus_role', role);
  try {
    const res = await fetch(`${API_BASE}/auth/switch-role`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role }),
    });
    if (res.ok) {
      const data = await res.json();
      authToken = data.access_token;
      localStorage.setItem('mcp_nexus_token', data.access_token);
    }
  } catch (e) {
    console.error('Failed to switch auth token for role:', e);
  }
  window.dispatchEvent(new Event('role_changed'));
};

async function fetchJSON<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  // If no auth token stored yet, obtain initial token for default role
  if (!authToken) {
    try {
      const authRes = await fetch(`${API_BASE}/auth/switch-role`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role: activeRole }),
      });
      if (authRes.ok) {
        const data = await authRes.json();
        authToken = data.access_token;
        localStorage.setItem('mcp_nexus_token', data.access_token);
      }
    } catch (_) {}
  }

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(authToken ? { 'Authorization': `Bearer ${authToken}` } : {}),
    ...(options.headers as Record<string, string> || {}),
  };

  const res = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    let errorMsg = `API Error ${res.status}: ${res.statusText}`;
    try {
      const errData = await res.json();
      if (errData.detail) {
        errorMsg = typeof errData.detail === 'string' ? errData.detail : JSON.stringify(errData.detail);
      }
    } catch (_) {}
    throw new Error(errorMsg);
  }

  return res.json();
}

export const api = {
  // Auth
  switchRole: (role: Role) => setActiveRole(role),

  // Command Center Metrics
  getMetrics: () => fetchJSON<CommandCenterMetrics>('/metrics/command-center'),
  getSystemHealth: () => fetchJSON<any>('/metrics/system-health'),

  // Servers
  getServers: (environment?: string) =>
    fetchJSON<MCPServer[]>(environment ? `/servers?environment=${environment}` : '/servers'),
  getServer: (id: string) => fetchJSON<MCPServer>(`/servers/${id}`),
  registerServer: (data: any) =>
    fetchJSON<MCPServer>('/servers', { method: 'POST', body: JSON.stringify(data) }),
  updateServer: (id: string, data: any) =>
    fetchJSON<MCPServer>(`/servers/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteServer: (id: string) =>
    fetchJSON<{ message: string }>(`/servers/${id}`, { method: 'DELETE' }),
  connectServer: (id: string) =>
    fetchJSON<any>(`/servers/${id}/connect`, { method: 'POST' }),
  discoverTools: (id: string) =>
    fetchJSON<any>(`/servers/${id}/discover-tools`, { method: 'POST' }),
  getServerLogs: (id: string) =>
    fetchJSON<{ server_id: string; server_name: string; logs: string[] }>(`/servers/${id}/logs`),
  getIncidents: () => fetchJSON<any[]>('/servers/circuit-breaker/incidents'),
  resetCircuit: (serverId: string) =>
    fetchJSON<any>(`/servers/${serverId}/reset-circuit`, { method: 'POST' }),
  discoverEndpoint: (data: {
    transport_type: string;
    command?: string;
    args?: string[];
    endpoint?: string;
    env_vars?: Record<string, string>;
    auth_token?: string;
  }) =>
    fetchJSON<{
      success: boolean;
      protocol_version: string;
      server_info: Record<string, any>;
      capabilities: Record<string, any>;
      discovered_tools: any[];
      discovered_resources: any[];
      discovered_prompts: any[];
      latency_ms: number;
      error?: string;
    }>('/servers/discover', { method: 'POST', body: JSON.stringify(data) }),

  // Tools & Playground
  getTools: (server_id?: string, risk_level?: string) => {
    const params = new URLSearchParams();
    if (server_id) params.append('server_id', server_id);
    if (risk_level) params.append('risk_level', risk_level);
    const qs = params.toString();
    return fetchJSON<MCPTool[]>(qs ? `/tools?${qs}` : '/tools');
  },
  toggleTool: (id: string) =>
    fetchJSON<any>(`/tools/${id}/toggle`, { method: 'PATCH' }),
  updateToolConfig: (id: string, data: any) =>
    fetchJSON<MCPTool>(`/tools/${id}/config`, { method: 'PUT', body: JSON.stringify(data) }),
  executePlaygroundTool: (tool_name: string, args: Record<string, any>) =>
    fetchJSON<any>('/tools/execute', {
      method: 'POST',
      body: JSON.stringify({ tool_name, arguments: args }),
    }),

  // AI Agents & Orchestration
  getAgents: () => fetchJSON<AIAgent[]>('/agents'),
  createAgent: (data: any) =>
    fetchJSON<AIAgent>('/agents', { method: 'POST', body: JSON.stringify(data) }),
  orchestrate: (agent_id: string, prompt: string) =>
    fetchJSON<any>('/agents/orchestrate', {
      method: 'POST',
      body: JSON.stringify({ agent_id, prompt }),
    }),

  // Governance & Approvals
  getApprovals: (status_filter?: string) =>
    fetchJSON<ApprovalRequest[]>(
      status_filter ? `/governance/approvals?status_filter=${status_filter}` : '/governance/approvals'
    ),
  reviewApproval: (approval_id: string, action: 'APPROVE' | 'REJECT', reason?: string) =>
    fetchJSON<any>(`/governance/approvals/${approval_id}/action`, {
      method: 'POST',
      body: JSON.stringify({ action, reason }),
    }),
  getSecurityEvents: () => fetchJSON<SecurityEvent[]>('/governance/security-events'),
  getAuditLogs: () => fetchJSON<AuditLog[]>('/governance/audit-logs'),
  getPolicies: () => fetchJSON<SecurityPolicy[]>('/governance/policies'),
  createPolicy: (data: Partial<SecurityPolicy>) =>
    fetchJSON<SecurityPolicy>('/governance/policies', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  updatePolicy: (id: string, data: Partial<SecurityPolicy>) =>
    fetchJSON<SecurityPolicy>(`/governance/policies/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  deletePolicy: (id: string) =>
    fetchJSON<{ success: boolean; message: string }>(`/governance/policies/${id}`, {
      method: 'DELETE',
    }),

  // Traces
  getTraces: (status?: string) =>
    fetchJSON<ExecutionTrace[]>(status ? `/traces?status=${status}` : '/traces'),
  getTrace: (id: string) => fetchJSON<ExecutionTrace>(`/traces/${id}`),

  // Topology Map
  getTopology: () => fetchJSON<{ nodes: any[]; edges: any[] }>('/topology'),

  // Integrations
  getIntegrations: () => fetchJSON<IntegrationConfig[]>('/integrations'),

  // Settings
  getOrganization: () => fetchJSON<any>('/settings/organization'),
  getApiConfig: () => fetchJSON<any>('/settings/api-configuration'),
  getUsers: () => fetchJSON<User[]>('/settings/users'),
  createUser: (data: any) =>
    fetchJSON<User>('/settings/users', { method: 'POST', body: JSON.stringify(data) }),
};
