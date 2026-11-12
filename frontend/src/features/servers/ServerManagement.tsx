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
  const [serverLogs, setServerLogs] = useState<string[]>([]);
  const [searchFilter, setSearchFilter] = useState('');
  const [envFilter, setEnvFilter] = useState<string>('ALL');

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
        <button
          onClick={() => setShowRegisterModal(true)}
          className="flex items-center gap-2 px-3.5 py-1.5 bg-[#F0A43A] hover:bg-[#F0A43A]/90 text-[#101216] font-semibold rounded text-xs transition-colors"
        >
          <Plus className="w-4 h-4" />
          Register MCP Server
        </button>
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
