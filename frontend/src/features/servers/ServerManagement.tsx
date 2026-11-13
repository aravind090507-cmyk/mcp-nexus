import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../services/api';
import type { MCPServer } from '../../types';
import {
  Server,
  Plus,
  RefreshCw,
  Power,
  Trash2,
  Edit,
  Terminal,
  Activity,
  CheckCircle,
  AlertTriangle,
  X,
  Clock,
  ArrowRight,
  ExternalLink,
  Shield,
  Search
} from 'lucide-react';

export const ServerManagement: React.FC = () => {
  const queryClient = useQueryClient();
  const [selectedServer, setSelectedServer] = useState<MCPServer | null>(null);
  const [showRegisterModal, setShowRegisterModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showLogsModal, setShowLogsModal] = useState(false);
  const [showDiscoverModal, setShowDiscoverModal] = useState(false);
  const [serverLogs, setServerLogs] = useState<string[]>([]);
  const [searchFilter, setSearchFilter] = useState('');
  const [envFilter, setEnvFilter] = useState<string>('ALL');

  // Discovery form state
  const [discoverForm, setDiscoverForm] = useState({
    transport_type: 'STDIO',
    command: 'python',
    args: 'demo_servers/equipment_server.py',
    endpoint: '',
    auth_token: '',
  });
  const [discoverResult, setDiscoverResult] = useState<any>(null);
  const [isProbing, setIsProbing] = useState(false);
  const [discoverError, setDiscoverError] = useState<string | null>(null);

  // Form state
  const [formData, setFormData] = useState({
    name: '',
    identifier: '',
    description: '',
    transport_type: 'STDIO',
    endpoint: '',
    command: 'python',
    args: '',
    environment: 'Production',
    connection_timeout: 15,
  });

  const [editFormData, setEditFormData] = useState({
    id: '',
    name: '',
    description: '',
    environment: 'Production',
    connection_timeout: 15,
    transport_type: 'STDIO',
    command: 'python',
    args: '',
    endpoint: '',
  });

  const { data: servers, isLoading } = useQuery({
    queryKey: ['mcp-servers'],
    queryFn: () => api.getServers(),
  });

  // Connect mutation
  const connectMutation = useMutation({
    mutationFn: (id: string) => api.connectServer(id),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['mcp-servers'] });
      queryClient.invalidateQueries({ queryKey: ['command-center-metrics'] });
      alert(`Server Handshake: ${data.status}\n${data.message}\nDiscovered Tools: ${data.tools_count ?? 0}`);
    },
    onError: (err: any) => alert(`Connection Failed: ${err.message}`),
  });

  // Discover tools mutation
  const discoverMutation = useMutation({
    mutationFn: (id: string) => api.discoverTools(id),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['mcp-servers'] });
      queryClient.invalidateQueries({ queryKey: ['mcp-tools'] });
      alert(`Discovered ${data.discovered_count} tools for ${data.server_name}!`);
    },
    onError: (err: any) => alert(`Discovery Failed: ${err.message}`),
  });

  // Toggle server mutation
  const toggleMutation = useMutation({
    mutationFn: ({ id, is_enabled }: { id: string; is_enabled: boolean }) =>
      api.updateServer(id, { is_enabled: !is_enabled }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mcp-servers'] });
    },
  });

  // Delete server mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteServer(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mcp-servers'] });
      setSelectedServer(null);
    },
    onError: (err: any) => alert(`Delete Failed: ${err.message}`),
  });

  // Edit server mutation
  const editMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => api.updateServer(id, data),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ['mcp-servers'] });
      setShowEditModal(false);
      setSelectedServer(updated);
    },
    onError: (err: any) => alert(`Update Failed: ${err.message}`),
  });

  // Rollback mutation
  const rollbackMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) => api.rollbackServer(id, reason),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['mcp-servers'] });
      alert(data.message);
    },
    onError: (err: any) => alert(`Rollback Failed: ${err.message}`),
  });

  // Recover mutation
  const recoverMutation = useMutation({
    mutationFn: (id: string) => api.recoverServer(id),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['mcp-servers'] });
      alert(data.message);
    },
    onError: (err: any) => alert(`Recovery Failed: ${err.message}`),
  });

  const getDeploymentStateBadge = (state?: string) => {
    const s = state || 'DISABLED';
    switch (s) {
      case 'PREPARED':
        return 'bg-[#48B9D0]/15 text-[#48B9D0] border border-[#48B9D0]/30';
      case 'ELIGIBLE':
        return 'bg-[#9B51E0]/15 text-[#9B51E0] border border-[#9B51E0]/30';
      case 'CANARY_AUTHORIZED':
        return 'bg-[#F0A43A]/15 text-[#F0A43A] border border-[#F0A43A]/30';
      case 'CANARY_ACTIVE':
        return 'bg-[#43B581]/15 text-[#43B581] border border-[#43B581]/30';
      case 'ROLLBACK':
        return 'bg-[#E05252]/15 text-[#E05252] border border-[#E05252]/30';
      default:
        return 'bg-[#303640]/40 text-[#9DA7B5] border border-[#303640]';
    }
  };

  const handleOpenEdit = (server: MCPServer) => {
    setEditFormData({
      id: server.id,
      name: server.name,
      description: server.description || '',
      environment: server.environment || 'Production',
      connection_timeout: server.connection_timeout || 15,
      transport_type: server.transport_type,
      command: server.command || 'python',
      args: (server.args || []).join(' '),
      endpoint: server.endpoint || '',
    });
    setShowEditModal(true);
  };

  const handleEditSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const argsArray = editFormData.args.trim() ? editFormData.args.split(' ').map((s) => s.trim()) : [];
    editMutation.mutate({
      id: editFormData.id,
      data: {
        name: editFormData.name,
        description: editFormData.description,
        environment: editFormData.environment,
        connection_timeout: Number(editFormData.connection_timeout),
        transport_type: editFormData.transport_type,
        command: editFormData.command,
        args: argsArray,
        endpoint: editFormData.endpoint,
      },
    });
  };

  const handleProbeEndpoint = async () => {
    setIsProbing(true);
    setDiscoverError(null);
    setDiscoverResult(null);
    try {
      const argsArray = discoverForm.args.trim() ? discoverForm.args.split(' ').map((s) => s.trim()) : [];
      const res = await api.discoverEndpoint({
        transport_type: discoverForm.transport_type,
        command: discoverForm.command,
        args: argsArray,
        endpoint: discoverForm.endpoint,
        auth_token: discoverForm.auth_token || undefined,
      });
      if (res.success) {
        setDiscoverResult(res);
      } else {
        setDiscoverError(res.error || 'Failed to handshake with MCP endpoint.');
      }
    } catch (err: any) {
      setDiscoverError(err.message || 'Auto-discovery probe failed.');
    } finally {
      setIsProbing(false);
    }
  };

  const handleApproveDiscoveredServer = async () => {
    if (!discoverResult) return;
    const serverName = discoverResult.server_info?.name || 'Discovered MCP Server';
    const serverId = serverName.toLowerCase().replace(/[^a-z0-9]/g, '-') + '-' + Math.floor(Math.random() * 1000);
    const argsArray = discoverForm.args.trim() ? discoverForm.args.split(' ').map((s) => s.trim()) : [];

    registerMutation.mutate({
      name: serverName,
      identifier: serverId,
      description: `Auto-discovered MCP server (Protocol ${discoverResult.protocol_version}). Discovered ${discoverResult.discovered_tools?.length || 0} tools.`,
      transport_type: discoverForm.transport_type,
      command: discoverForm.command,
      args: argsArray,
      endpoint: discoverForm.endpoint || undefined,
      environment: 'Production',
      connection_timeout: 15,
    });
    setShowDiscoverModal(false);
  };

  // Register mutation
  const registerMutation = useMutation({
    mutationFn: (payload: any) => api.registerServer(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mcp-servers'] });
      setShowRegisterModal(false);
      setFormData({
        name: '',
        identifier: '',
        description: '',
        transport_type: 'STDIO',
        endpoint: '',
        command: 'python',
        args: '',
        environment: 'Production',
        connection_timeout: 15,
      });
    },
    onError: (err: any) => alert(`Registration error: ${err.message}`),
  });

  const handleRegisterSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const argsArray = formData.args.trim() ? formData.args.split(' ').map((s) => s.trim()) : [];
    registerMutation.mutate({
      ...formData,
      args: argsArray,
    });
  };

  const handleViewLogs = async (server: MCPServer) => {
    try {
      const data = await api.getServerLogs(server.id);
      setServerLogs(data.logs);
      setShowLogsModal(true);
    } catch (e: any) {
      alert(`Error fetching logs: ${e.message}`);
    }
  };

  const filteredServers = (servers || []).filter((s) => {
    const matchesSearch = s.name.toLowerCase().includes(searchFilter.toLowerCase()) ||
      s.identifier.toLowerCase().includes(searchFilter.toLowerCase());
    const matchesEnv = envFilter === 'ALL' || s.environment === envFilter;
    return matchesSearch && matchesEnv;
  });

  const activeSelected = selectedServer || (filteredServers.length > 0 ? filteredServers[0] : null);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#303640] pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-[#ECEFF4] font-mono">
              MCP SERVER MANAGEMENT
            </h1>
            <span className="text-[11px] px-2 py-0.5 rounded bg-[#48B9D0]/15 text-[#48B9D0] font-mono border border-[#48B9D0]/30">
              REGISTRATION & PROTOCOL HEALTH
            </span>
          </div>
          <p className="text-xs text-[#9DA7B5] mt-1">
            Register and manage Model Context Protocol servers supporting STDIO subprocesses and Streamable HTTP.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              setDiscoverResult(null);
              setDiscoverError(null);
              setShowDiscoverModal(true);
            }}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#181C23] hover:bg-[#303640] border border-[#48B9D0]/40 text-[#48B9D0] font-semibold rounded text-xs transition-colors"
          >
            <Activity className="w-3.5 h-3.5" />
            Auto-Discover Endpoint
          </button>
          <button
            onClick={() => setShowRegisterModal(true)}
            className="flex items-center gap-2 px-3.5 py-1.5 bg-[#F0A43A] hover:bg-[#F0A43A]/90 text-[#101216] font-semibold rounded text-xs transition-colors"
          >
            <Plus className="w-4 h-4" />
            Register MCP Server
          </button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex items-center justify-between gap-4 bg-[#14171D] p-3 border border-[#303640] rounded text-xs font-mono">
        <div className="flex items-center gap-2 flex-1 max-w-sm">
          <Search className="w-3.5 h-3.5 text-[#626D7C]" />
          <input
            type="text"
            placeholder="Filter servers by name or identifier..."
            value={searchFilter}
            onChange={(e) => setSearchFilter(e.target.value)}
            className="w-full bg-[#181C23] border border-[#303640] rounded px-2.5 py-1 text-xs text-[#ECEFF4] placeholder-[#626D7C] focus:outline-none focus:border-[#F0A43A]"
          />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[#626D7C] text-[11px]">ENVIRONMENT:</span>
          {(['ALL', 'Production', 'Staging', 'Development'] as const).map((env) => (
            <button
              key={env}
              onClick={() => setEnvFilter(env)}
              className={`px-2.5 py-1 rounded text-[11px] transition-colors ${
                envFilter === env
                  ? 'bg-[#181C23] text-[#F0A43A] font-bold border border-[#F0A43A]/30'
                  : 'text-[#9DA7B5] hover:text-[#ECEFF4]'
              }`}
            >
              {env}
            </button>
          ))}
        </div>
      </div>

      {/* 2-Column Inspector Grid (7 cols server list, 5 cols detail inspector) */}
      <div className="grid grid-cols-12 gap-6">
        {/* Servers List (7 cols) */}
        <div className="col-span-12 lg:col-span-7 space-y-3">
          {isLoading ? (
            <div className="text-xs text-[#9DA7B5] font-mono py-8 text-center animate-pulse">
              Querying MCP server registry...
            </div>
          ) : filteredServers.length === 0 ? (
            <div className="p-8 text-center border border-[#303640] bg-[#14171D] rounded font-mono text-xs text-[#626D7C]">
              No MCP servers match the current filters.
            </div>
          ) : (
            filteredServers.map((server) => {
              const isSelected = activeSelected?.id === server.id;
              return (
                <div
                  key={server.id}
                  onClick={() => setSelectedServer(server)}
                  className={`p-4 bg-[#14171D] border rounded cursor-pointer transition-all ${
                    isSelected
                      ? 'border-[#F0A43A] shadow-md bg-[#181C23]'
                      : 'border-[#303640] hover:border-[#626D7C]'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <div className="w-8 h-8 rounded bg-[#101216] border border-[#303640] flex items-center justify-center">
                        <Server className="w-4 h-4 text-[#F0A43A]" />
                      </div>
                      <div>
                        <div className="text-xs font-bold font-mono text-[#ECEFF4] flex items-center gap-2">
                          {server.name}
                          <span className={`text-[9px] px-1.5 py-0.2 rounded font-bold ${
                            server.status === 'HEALTHY'
                              ? 'bg-[#43B581]/15 text-[#43B581]'
                              : 'bg-[#EBB346]/15 text-[#EBB346]'
                          }`}>
                            {server.status}
                          </span>
                          <span className={`text-[9px] px-1.5 py-0.2 rounded font-bold ${getDeploymentStateBadge(server.env_vars?.DEPLOYMENT_STATE)}`}>
                            {server.env_vars?.DEPLOYMENT_STATE || 'DISABLED'}
                          </span>
                        </div>
                        <div className="text-[10px] text-[#9DA7B5] font-mono mt-0.5">
                          ID: {server.identifier} • {server.transport_type}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-4 text-right font-mono text-xs">
                      <div>
                        <div className="text-[#ECEFF4] font-semibold">{server.avg_response_time_ms} ms</div>
                        <div className="text-[10px] text-[#626D7C]">Avg Latency</div>
                      </div>
                      <div>
                        <div className="text-[#48B9D0] font-semibold">{server.tools?.length ?? 0}</div>
                        <div className="text-[10px] text-[#626D7C]">Tools Bound</div>
                      </div>
                    </div>
                  </div>

                  <p className="text-[11px] text-[#9DA7B5] mt-2 line-clamp-1">
                    {server.description || 'No description configured.'}
                  </p>
                </div>
              );
            })
          )}
        </div>

        {/* Server Detail Inspector (5 cols) */}
        <div className="col-span-12 lg:col-span-5 bg-[#14171D] border border-[#303640] rounded p-5 space-y-4 font-mono">
          {activeSelected ? (
            <>
              <div className="flex items-start justify-between border-b border-[#303640] pb-3">
                <div>
                  <h3 className="text-sm font-bold text-[#ECEFF4]">{activeSelected.name}</h3>
                  <div className="text-[11px] text-[#F0A43A] mt-0.5">{activeSelected.identifier}</div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleOpenEdit(activeSelected)}
                    className="p-1.5 bg-[#181C23] hover:bg-[#303640] border border-[#303640] rounded text-[#ECEFF4]"
                    title="Edit Server Configuration"
                  >
                    <Edit className="w-3.5 h-3.5 text-[#F0A43A]" />
                  </button>
                  <button
                    onClick={() => connectMutation.mutate(activeSelected.id)}
                    disabled={connectMutation.isPending}
                    className="p-1.5 bg-[#181C23] hover:bg-[#303640] border border-[#303640] rounded text-[#ECEFF4]"
                    title="Probe Health / Reconnect"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${connectMutation.isPending ? 'animate-spin text-[#F0A43A]' : ''}`} />
                  </button>
                  <button
                    onClick={() => toggleMutation.mutate({ id: activeSelected.id, is_enabled: activeSelected.is_enabled })}
                    className={`p-1.5 border rounded ${
                      activeSelected.is_enabled
                        ? 'bg-[#43B581]/15 border-[#43B581]/30 text-[#43B581]'
                        : 'bg-[#E05252]/15 border-[#E05252]/30 text-[#E05252]'
                    }`}
                    title={activeSelected.is_enabled ? 'Disable Server' : 'Enable Server'}
                  >
                    <Power className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => {
                      if (confirm(`Are you sure you want to delete server '${activeSelected.name}'?`)) {
                        deleteMutation.mutate(activeSelected.id);
                      }
                    }}
                    className="p-1.5 bg-[#181C23] hover:bg-[#E05252]/20 border border-[#303640] hover:border-[#E05252] rounded text-[#E05252]"
                    title="Delete Server"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {/* Server Metadata Grid */}
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="p-2 bg-[#181C23] border border-[#303640] rounded">
                  <div className="text-[10px] text-[#626D7C]">TRANSPORT</div>
                  <div className="text-[#ECEFF4] font-bold mt-0.5">{activeSelected.transport_type}</div>
                </div>
                <div className="p-2 bg-[#181C23] border border-[#303640] rounded">
                  <div className="text-[10px] text-[#626D7C]">STATUS</div>
                  <div className="text-[#43B581] font-bold mt-0.5">{activeSelected.status}</div>
                </div>
                <div className="p-2 bg-[#181C23] border border-[#303640] rounded">
                  <div className="text-[10px] text-[#626D7C]">AVG LATENCY</div>
                  <div className="text-[#48B9D0] font-bold mt-0.5">{activeSelected.avg_response_time_ms} ms</div>
                </div>
                <div className="p-2 bg-[#181C23] border border-[#303640] rounded">
                  <div className="text-[10px] text-[#626D7C]">ERROR RATE</div>
                  <div className="text-[#ECEFF4] font-bold mt-0.5">{activeSelected.error_rate}%</div>
                </div>
              </div>

              {/* Deployment Governance & Canary Status */}
              <div className="p-2.5 bg-[#181C23] border border-[#303640] rounded text-xs flex items-center justify-between">
                <div>
                  <div className="text-[10px] text-[#626D7C]">DEPLOYMENT STATE</div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className={`text-[10px] px-2 py-0.5 rounded font-bold ${getDeploymentStateBadge(activeSelected.env_vars?.DEPLOYMENT_STATE)}`}>
                      {activeSelected.env_vars?.DEPLOYMENT_STATE || 'DISABLED'}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  {activeSelected.env_vars?.DEPLOYMENT_STATE === 'ROLLBACK' ? (
                    <button
                      onClick={() => recoverMutation.mutate(activeSelected.id)}
                      disabled={recoverMutation.isPending}
                      className="px-2 py-1 bg-[#43B581]/15 hover:bg-[#43B581]/30 border border-[#43B581]/40 rounded text-[11px] text-[#43B581] font-bold"
                      title="Verify health and recover to PREPARED state"
                    >
                      Recover Server
                    </button>
                  ) : (
                    <button
                      onClick={() => {
                        const reason = prompt(`Enter reason for rolling back '${activeSelected.name}' to legacy transport:`, 'Manual operator rollback');
                        if (reason) {
                          rollbackMutation.mutate({ id: activeSelected.id, reason });
                        }
                      }}
                      disabled={rollbackMutation.isPending}
                      className="px-2 py-1 bg-[#E05252]/15 hover:bg-[#E05252]/30 border border-[#E05252]/40 rounded text-[11px] text-[#E05252] font-bold"
                      title="Trigger server rollback to legacy transport"
                    >
                      Rollback Server
                    </button>
                  )}
                </div>
              </div>

              {/* Configuration Commands */}
              <div className="p-3 bg-[#101216] border border-[#303640] rounded text-xs space-y-1">
                <div className="text-[10px] text-[#626D7C] uppercase">Command / Endpoint Configuration</div>
                {activeSelected.transport_type === 'STDIO' ? (
                  <div className="text-[#ECEFF4] truncate text-[11px]">
                    <span className="text-[#F0A43A]">$ </span>
                    {activeSelected.command} {(activeSelected.args || []).join(' ')}
                  </div>
                ) : (
                  <div className="text-[#ECEFF4] truncate text-[11px]">
                    {activeSelected.endpoint || 'No endpoint URL configured'}
                  </div>
                )}
                <div className="text-[10px] text-[#626D7C] pt-1">
                  Timeout: {activeSelected.connection_timeout}s • Environment: {activeSelected.environment}
                </div>
              </div>

              {/* Action Buttons: Discover & Logs */}
              <div className="flex items-center gap-2">
                <button
                  onClick={() => discoverMutation.mutate(activeSelected.id)}
                  disabled={discoverMutation.isPending}
                  className="flex-1 py-1.5 bg-[#181C23] hover:bg-[#1F242D] border border-[#303640] rounded text-xs text-[#ECEFF4] flex items-center justify-center gap-1.5 transition-colors"
                >
                  <RefreshCw className={`w-3.5 h-3.5 text-[#F0A43A] ${discoverMutation.isPending ? 'animate-spin' : ''}`} />
                  Discover Tools ({activeSelected.tools?.length ?? 0})
                </button>
                <button
                  onClick={() => handleViewLogs(activeSelected)}
                  className="flex-1 py-1.5 bg-[#181C23] hover:bg-[#1F242D] border border-[#303640] rounded text-xs text-[#ECEFF4] flex items-center justify-center gap-1.5 transition-colors"
                >
                  <Terminal className="w-3.5 h-3.5 text-[#48B9D0]" />
                  Server Logs
                </button>
              </div>

              {/* Available Tools List */}
              <div>
                <div className="text-xs font-bold text-[#ECEFF4] mb-2 flex items-center justify-between">
                  <span>Registered MCP Tools</span>
                  <span className="text-[10px] text-[#9DA7B5]">{activeSelected.tools?.length ?? 0} active</span>
                </div>
                <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                  {(activeSelected.tools || []).map((t) => (
                    <div
                      key={t.id}
                      className="p-2 bg-[#181C23] border border-[#303640] rounded text-xs flex items-center justify-between"
                    >
                      <div>
                        <div className="font-semibold text-[#ECEFF4] text-[11px]">{t.name}</div>
                        <div className="text-[10px] text-[#9DA7B5] truncate max-w-[200px]">{t.description}</div>
                      </div>
                      <span className={`text-[9px] px-1.5 py-0.2 rounded font-bold ${
                        t.risk_level === 'CRITICAL' || t.risk_level === 'HIGH'
                          ? 'bg-[#E05252]/15 text-[#E05252]'
                          : 'bg-[#43B581]/15 text-[#43B581]'
                      }`}>
                        {t.risk_level}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </>
          ) : (
            <div className="text-xs text-[#626D7C] text-center py-12">
              Select an MCP server from the list to inspect operational telemetry.
            </div>
          )}
        </div>
      </div>

      {/* REGISTRATION MODAL */}
      {showRegisterModal && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#14171D] border border-[#303640] rounded-lg max-w-xl w-full p-6 space-y-4 font-mono shadow-2xl">
            <div className="flex items-center justify-between border-b border-[#303640] pb-3">
              <h3 className="text-sm font-bold text-[#ECEFF4] flex items-center gap-2">
                <Server className="w-4 h-4 text-[#F0A43A]" />
                Register New MCP Server
              </h3>
              <button onClick={() => setShowRegisterModal(false)}>
                <X className="w-4 h-4 text-[#626D7C] hover:text-[#ECEFF4]" />
              </button>
            </div>

            <form onSubmit={handleRegisterSubmit} className="space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] text-[#9DA7B5] uppercase">Server Display Name</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Telemetry Hub MCP"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="w-full mt-1 bg-[#181C23] border border-[#303640] rounded p-2 text-[#ECEFF4]"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-[#9DA7B5] uppercase">Identifier Code</label>
                  <input
                    type="text"
                    required
                    placeholder="mcp-srv-custom-01"
                    value={formData.identifier}
                    onChange={(e) => setFormData({ ...formData, identifier: e.target.value })}
                    className="w-full mt-1 bg-[#181C23] border border-[#303640] rounded p-2 text-[#ECEFF4]"
                  />
                </div>
              </div>

              <div>
                <label className="text-[10px] text-[#9DA7B5] uppercase">Description</label>
                <textarea
                  rows={2}
                  placeholder="Enterprise purpose and capabilities description..."
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  className="w-full mt-1 bg-[#181C23] border border-[#303640] rounded p-2 text-[#ECEFF4]"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] text-[#9DA7B5] uppercase">Transport Type</label>
                  <select
                    value={formData.transport_type}
                    onChange={(e) => setFormData({ ...formData, transport_type: e.target.value })}
                    className="w-full mt-1 bg-[#181C23] border border-[#303640] rounded p-2 text-[#ECEFF4]"
                  >
                    <option value="STDIO">STDIO (Subprocess JSON-RPC)</option>
                    <option value="HTTP_SSE">HTTP / SSE Stream</option>
                  </select>
                </div>
                <div>
                  <label className="text-[10px] text-[#9DA7B5] uppercase">Environment</label>
                  <select
                    value={formData.environment}
                    onChange={(e) => setFormData({ ...formData, environment: e.target.value })}
                    className="w-full mt-1 bg-[#181C23] border border-[#303640] rounded p-2 text-[#ECEFF4]"
                  >
                    <option value="Production">Production</option>
                    <option value="Staging">Staging</option>
                    <option value="Development">Development</option>
                  </select>
                </div>
              </div>

              {formData.transport_type === 'STDIO' ? (
                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <label className="text-[10px] text-[#9DA7B5] uppercase">Command Executable</label>
                    <input
                      type="text"
                      placeholder="python / npx / uv"
                      value={formData.command}
                      onChange={(e) => setFormData({ ...formData, command: e.target.value })}
                      className="w-full mt-1 bg-[#181C23] border border-[#303640] rounded p-2 text-[#ECEFF4]"
                    />
                  </div>
                  <div className="col-span-2">
                    <label className="text-[10px] text-[#9DA7B5] uppercase">Arguments (space separated)</label>
                    <input
                      type="text"
                      placeholder="-m app.mcp.demo_servers.erp_server"
                      value={formData.args}
                      onChange={(e) => setFormData({ ...formData, args: e.target.value })}
                      className="w-full mt-1 bg-[#181C23] border border-[#303640] rounded p-2 text-[#ECEFF4]"
                    />
                  </div>
                </div>
              ) : (
                <div>
                  <label className="text-[10px] text-[#9DA7B5] uppercase">HTTP Endpoint URL</label>
                  <input
                    type="url"
                    placeholder="https://mcp.internal.lt.corp/v1/sse"
                    value={formData.endpoint}
                    onChange={(e) => setFormData({ ...formData, endpoint: e.target.value })}
                    className="w-full mt-1 bg-[#181C23] border border-[#303640] rounded p-2 text-[#ECEFF4]"
                  />
                </div>
              )}

              <div className="flex justify-end gap-3 pt-3 border-t border-[#303640]">
                <button
                  type="button"
                  onClick={() => setShowRegisterModal(false)}
                  className="px-4 py-1.5 bg-[#181C23] hover:bg-[#1F242D] border border-[#303640] rounded text-[#ECEFF4]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={registerMutation.isPending}
                  className="px-4 py-1.5 bg-[#F0A43A] hover:bg-[#F0A43A]/90 text-[#101216] font-bold rounded"
                >
                  {registerMutation.isPending ? 'Verifying...' : 'Save & Handshake'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* EDIT SERVER MODAL */}
      {showEditModal && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#14171D] border border-[#303640] rounded-lg max-w-xl w-full p-6 space-y-4 font-mono shadow-2xl">
            <div className="flex items-center justify-between border-b border-[#303640] pb-3">
              <h3 className="text-sm font-bold text-[#ECEFF4] flex items-center gap-2">
                <Edit className="w-4 h-4 text-[#F0A43A]" />
                Edit MCP Server Configuration
              </h3>
              <button onClick={() => setShowEditModal(false)}>
                <X className="w-4 h-4 text-[#626D7C] hover:text-[#ECEFF4]" />
              </button>
            </div>

            <form onSubmit={handleEditSubmit} className="space-y-3 text-xs">
              <div>
                <label className="text-[10px] text-[#9DA7B5] uppercase">Server Display Name</label>
                <input
                  type="text"
                  required
                  value={editFormData.name}
                  onChange={(e) => setEditFormData({ ...editFormData, name: e.target.value })}
                  className="w-full mt-1 bg-[#181C23] border border-[#303640] rounded p-2 text-[#ECEFF4]"
                />
              </div>

              <div>
                <label className="text-[10px] text-[#9DA7B5] uppercase">Description</label>
                <textarea
                  rows={2}
                  value={editFormData.description}
                  onChange={(e) => setEditFormData({ ...editFormData, description: e.target.value })}
                  className="w-full mt-1 bg-[#181C23] border border-[#303640] rounded p-2 text-[#ECEFF4]"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] text-[#9DA7B5] uppercase">Environment</label>
                  <select
                    value={editFormData.environment}
                    onChange={(e) => setEditFormData({ ...editFormData, environment: e.target.value })}
                    className="w-full mt-1 bg-[#181C23] border border-[#303640] rounded p-2 text-[#ECEFF4]"
                  >
                    <option value="Production">Production</option>
                    <option value="Staging">Staging</option>
                    <option value="Development">Development</option>
                  </select>
                </div>
                <div>
                  <label className="text-[10px] text-[#9DA7B5] uppercase">Connection Timeout (sec)</label>
                  <input
                    type="number"
                    min="5"
                    max="120"
                    value={editFormData.connection_timeout}
                    onChange={(e) => setEditFormData({ ...editFormData, connection_timeout: Number(e.target.value) })}
                    className="w-full mt-1 bg-[#181C23] border border-[#303640] rounded p-2 text-[#ECEFF4]"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] text-[#9DA7B5] uppercase">Transport Type</label>
                  <select
                    value={editFormData.transport_type}
                    onChange={(e) => setEditFormData({ ...editFormData, transport_type: e.target.value })}
                    className="w-full mt-1 bg-[#181C23] border border-[#303640] rounded p-2 text-[#ECEFF4]"
                  >
                    <option value="STDIO">STDIO (Subprocess JSON-RPC)</option>
                    <option value="HTTP_SSE">HTTP / SSE Stream</option>
                  </select>
                </div>
                {editFormData.transport_type === 'STDIO' ? (
                  <div>
                    <label className="text-[10px] text-[#9DA7B5] uppercase">Command Executable</label>
                    <input
                      type="text"
                      value={editFormData.command}
                      onChange={(e) => setEditFormData({ ...editFormData, command: e.target.value })}
                      className="w-full mt-1 bg-[#181C23] border border-[#303640] rounded p-2 text-[#ECEFF4]"
                    />
                  </div>
                ) : (
                  <div>
                    <label className="text-[10px] text-[#9DA7B5] uppercase">HTTP Endpoint URL</label>
                    <input
                      type="url"
                      value={editFormData.endpoint}
                      onChange={(e) => setEditFormData({ ...editFormData, endpoint: e.target.value })}
                      className="w-full mt-1 bg-[#181C23] border border-[#303640] rounded p-2 text-[#ECEFF4]"
                    />
                  </div>
                )}
              </div>

              {editFormData.transport_type === 'STDIO' && (
                <div>
                  <label className="text-[10px] text-[#9DA7B5] uppercase">Arguments (space separated)</label>
                  <input
                    type="text"
                    value={editFormData.args}
                    onChange={(e) => setEditFormData({ ...editFormData, args: e.target.value })}
                    className="w-full mt-1 bg-[#181C23] border border-[#303640] rounded p-2 text-[#ECEFF4]"
                  />
                </div>
              )}

              <div className="flex justify-end gap-3 pt-3 border-t border-[#303640]">
                <button
                  type="button"
                  onClick={() => setShowEditModal(false)}
                  className="px-4 py-1.5 bg-[#181C23] hover:bg-[#1F242D] border border-[#303640] rounded text-[#ECEFF4]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={editMutation.isPending}
                  className="px-4 py-1.5 bg-[#F0A43A] hover:bg-[#F0A43A]/90 text-[#101216] font-bold rounded"
                >
                  {editMutation.isPending ? 'Updating...' : 'Save Changes'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* AUTO-DISCOVER & CAPABILITY HANDSHAKE MODAL */}
      {showDiscoverModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#14171D] border border-[#303640] rounded-lg max-w-3xl w-full p-6 space-y-4 font-mono shadow-2xl max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-[#303640] pb-3 text-xs">
              <span className="font-bold text-[#ECEFF4] flex items-center gap-2">
                <Activity className="w-4 h-4 text-[#48B9D0]" />
                MCP Auto-Discovery & Capability Negotiation
              </span>
              <button
                onClick={() => {
                  setShowDiscoverModal(false);
                  setDiscoverResult(null);
                  setDiscoverError(null);
                }}
              >
                <X className="w-4 h-4 text-[#626D7C] hover:text-[#ECEFF4]" />
              </button>
            </div>

            <p className="text-xs text-[#9DA7B5] font-sans">
              Probe an external or local MCP endpoint, perform a protocol handshake (JSON-RPC 2.0 initialize), and inspect discovered capabilities, tools, resources, and prompts before administrative activation.
            </p>

            {/* Probe Inputs */}
            <div className="space-y-3 bg-[#101216] p-4 rounded border border-[#303640] text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[#9DA7B5] mb-1 font-semibold">Transport Type</label>
                  <select
                    value={discoverForm.transport_type}
                    onChange={(e) => setDiscoverForm({ ...discoverForm, transport_type: e.target.value })}
                    className="w-full bg-[#181C23] border border-[#303640] rounded px-3 py-1.5 text-[#ECEFF4] focus:outline-none focus:border-[#48B9D0]"
                  >
                    <option value="STDIO">STDIO Subprocess</option>
                    <option value="HTTP_SSE">Streamable HTTP (SSE)</option>
                    <option value="HTTP">Standard HTTP POST</option>
                  </select>
                </div>

                {discoverForm.transport_type === 'STDIO' ? (
                  <div>
                    <label className="block text-[#9DA7B5] mb-1 font-semibold">Executable Command</label>
                    <input
                      type="text"
                      value={discoverForm.command}
                      onChange={(e) => setDiscoverForm({ ...discoverForm, command: e.target.value })}
                      placeholder="e.g. python, uv, node, docker"
                      className="w-full bg-[#181C23] border border-[#303640] rounded px-3 py-1.5 text-[#ECEFF4] focus:outline-none focus:border-[#48B9D0]"
                    />
                  </div>
                ) : (
                  <div>
                    <label className="block text-[#9DA7B5] mb-1 font-semibold">HTTP Endpoint URL</label>
                    <input
                      type="text"
                      value={discoverForm.endpoint}
                      onChange={(e) => setDiscoverForm({ ...discoverForm, endpoint: e.target.value })}
                      placeholder="e.g. http://127.0.0.1:8001/mcp"
                      className="w-full bg-[#181C23] border border-[#303640] rounded px-3 py-1.5 text-[#ECEFF4] focus:outline-none focus:border-[#48B9D0]"
                    />
                  </div>
                )}
              </div>

              {discoverForm.transport_type === 'STDIO' && (
                <div>
                  <label className="block text-[#9DA7B5] mb-1 font-semibold">Subprocess Arguments</label>
                  <input
                    type="text"
                    value={discoverForm.args}
                    onChange={(e) => setDiscoverForm({ ...discoverForm, args: e.target.value })}
                    placeholder="e.g. demo_servers/equipment_server.py"
                    className="w-full bg-[#181C23] border border-[#303640] rounded px-3 py-1.5 text-[#ECEFF4] focus:outline-none focus:border-[#48B9D0]"
                  />
                </div>
              )}

              {discoverForm.transport_type !== 'STDIO' && (
                <div>
                  <label className="block text-[#9DA7B5] mb-1 font-semibold">Bearer Auth Token (Optional)</label>
                  <input
                    type="text"
                    value={discoverForm.auth_token}
                    onChange={(e) => setDiscoverForm({ ...discoverForm, auth_token: e.target.value })}
                    placeholder="Optional Authorization token..."
                    className="w-full bg-[#181C23] border border-[#303640] rounded px-3 py-1.5 text-[#ECEFF4] focus:outline-none focus:border-[#48B9D0]"
                  />
                </div>
              )}

              <div className="flex justify-end pt-1">
                <button
                  type="button"
                  onClick={handleProbeEndpoint}
                  disabled={isProbing}
                  className="flex items-center gap-1.5 px-4 py-1.5 bg-[#48B9D0] hover:bg-[#3ca4ba] text-[#101216] font-bold rounded text-xs transition-colors"
                >
                  <Activity className={`w-3.5 h-3.5 ${isProbing ? 'animate-spin' : ''}`} />
                  {isProbing ? 'Negotiating Protocol...' : 'Probe & Negotiate Capabilities'}
                </button>
              </div>
            </div>

            {/* Error Banner */}
            {discoverError && (
              <div className="p-3 bg-[#E05252]/10 border border-[#E05252]/30 rounded text-xs text-[#E05252] flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                <span>Probe Error: {discoverError}</span>
              </div>
            )}

            {/* Discovery Results */}
            {discoverResult && (
              <div className="space-y-4 pt-2">
                {/* Protocol Header */}
                <div className="p-4 bg-[#181C23] border border-[#303640] rounded space-y-2 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-[#ECEFF4] text-sm">
                      {discoverResult.server_info?.name || 'MCP Endpoint Detected'}
                    </span>
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 rounded text-[10px] bg-[#43B581]/15 text-[#43B581] border border-[#43B581]/30 font-bold">
                        VERSION: {discoverResult.protocol_version}
                      </span>
                      <span className="px-2 py-0.5 rounded text-[10px] bg-[#F0A43A]/15 text-[#F0A43A] border border-[#F0A43A]/30 font-bold">
                        LATENCY: {discoverResult.latency_ms} ms
                      </span>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-2 text-[10px] text-[#9DA7B5] pt-1 border-t border-[#303640]">
                    <span>Negotiated Capabilities:</span>
                    {Object.keys(discoverResult.capabilities || {}).map((c) => (
                      <span key={c} className="px-2 py-0.5 rounded bg-[#101216] border border-[#303640] text-[#48B9D0]">
                        {c}
                      </span>
                    ))}
                    <span className="px-2 py-0.5 rounded bg-[#101216] border border-[#303640] text-[#ECEFF4]">
                      {discoverResult.discovered_tools?.length || 0} Tools
                    </span>
                    <span className="px-2 py-0.5 rounded bg-[#101216] border border-[#303640] text-[#ECEFF4]">
                      {discoverResult.discovered_resources?.length || 0} Resources
                    </span>
                    <span className="px-2 py-0.5 rounded bg-[#101216] border border-[#303640] text-[#ECEFF4]">
                      {discoverResult.discovered_prompts?.length || 0} Prompts
                    </span>
                  </div>
                </div>

                {/* Discovered Tools List */}
                <div>
                  <div className="text-[11px] font-bold text-[#9DA7B5] uppercase mb-2">
                    Discovered Tools ({discoverResult.discovered_tools?.length || 0})
                  </div>
                  <div className="border border-[#303640] rounded overflow-hidden max-h-48 overflow-y-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-[#181C23] text-[#9DA7B5] border-b border-[#303640]">
                        <tr>
                          <th className="py-2 px-3">Tool Name</th>
                          <th className="py-2 px-3">Description</th>
                          <th className="py-2 px-3">Parameters</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#303640] bg-[#101216]">
                        {discoverResult.discovered_tools?.map((tool: any) => (
                          <tr key={tool.name}>
                            <td className="py-2 px-3 font-bold text-[#F0A43A]">{tool.name}</td>
                            <td className="py-2 px-3 text-[#ECEFF4] font-sans text-[11px]">{tool.description}</td>
                            <td className="py-2 px-3 text-[#9DA7B5] text-[10px]">
                              {tool.inputSchema?.properties ? Object.keys(tool.inputSchema.properties).join(', ') : 'none'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="flex items-center justify-end gap-3 pt-3 border-t border-[#303640]">
                  <button
                    type="button"
                    onClick={() => {
                      setShowDiscoverModal(false);
                      setDiscoverResult(null);
                    }}
                    className="px-4 py-1.5 bg-[#181C23] hover:bg-[#1F242D] border border-[#303640] rounded text-xs text-[#ECEFF4]"
                  >
                    Discard
                  </button>
                  <button
                    type="button"
                    onClick={handleApproveDiscoveredServer}
                    className="flex items-center gap-1.5 px-4 py-1.5 bg-[#43B581] hover:bg-[#3aa374] text-[#101216] font-bold rounded text-xs transition-colors"
                  >
                    <CheckCircle className="w-3.5 h-3.5" />
                    Approve & Register Server
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* LOGS MODAL */}
      {showLogsModal && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#14171D] border border-[#303640] rounded-lg max-w-2xl w-full p-5 space-y-3 font-mono shadow-2xl">
            <div className="flex items-center justify-between border-b border-[#303640] pb-2 text-xs">
              <span className="font-bold text-[#ECEFF4] flex items-center gap-2">
                <Terminal className="w-4 h-4 text-[#48B9D0]" />
                Live Subprocess Stream: {activeSelected?.name}
              </span>
              <button onClick={() => setShowLogsModal(false)}>
                <X className="w-4 h-4 text-[#626D7C]" />
              </button>
            </div>
            <div className="bg-[#101216] border border-[#303640] p-3 rounded text-[11px] font-mono text-[#43B581] h-64 overflow-y-auto space-y-1">
              {serverLogs.map((l, i) => (
                <div key={i}>{l}</div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
