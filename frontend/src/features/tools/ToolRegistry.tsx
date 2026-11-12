import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../services/api';
import type { MCPTool } from '../../types';
import {
  Wrench,
  Play,
  CheckCircle,
  AlertTriangle,
  Clock,
  Shield,
  Terminal,
  Code,
  Copy,
  Search,
  Filter,
  Check,
  Power,
  SlidersHorizontal,
  X
} from 'lucide-react';

const SAMPLE_PAYLOADS: Record<string, any> = {
  get_project_details: {
    project_id: "PRJ-MUM-001"
  },
  get_financial_summary: {
    project_id: "PRJ-HAZ-002"
  },
  get_project_status: {},
  get_inventory: {
    category: "Structural Materials",
    warehouse_id: "WH-HAZ-CENTRAL"
  },
  check_stock_availability: {
    item_code: "MAT-FLG-SS316",
    quantity: 10
  },
  get_low_stock_items: {
    threshold_multiplier: 1.2
  },
  get_equipment_status: {
    equipment_id: "EQP-CRN-8800"
  },
  get_maintenance_schedule: {
    overdue_only: true
  },
  report_equipment_issue: {
    equipment_id: "EQP-CRN-8800",
    severity: "CRITICAL",
    description: "Abnormal ultrasonic reading on main hoist gearbox during cold lift test."
  }
};

export const ToolRegistry: React.FC = () => {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<'registry' | 'playground'>('registry');
  const [selectedTool, setSelectedTool] = useState<MCPTool | null>(null);
  const [searchFilter, setSearchFilter] = useState('');
  const [riskFilter, setRiskFilter] = useState<string>('ALL');
  const [configuringTool, setConfiguringTool] = useState<MCPTool | null>(null);
  const [configFormData, setConfigFormData] = useState({
    risk_level: 'LOW',
    requires_approval: false,
    is_enabled: true,
    description: '',
  });

  // Playground state
  const [playgroundToolName, setPlaygroundToolName] = useState<string>('get_project_details');
  const [jsonInput, setJsonInput] = useState<string>(
    JSON.stringify(SAMPLE_PAYLOADS['get_project_details'], null, 2)
  );
  const [executionResult, setExecutionResult] = useState<any>(null);
  const [copied, setCopied] = useState(false);

  const { data: tools, isLoading } = useQuery({
    queryKey: ['mcp-tools'],
    queryFn: () => api.getTools(),
  });

  const { data: servers } = useQuery({
    queryKey: ['mcp-servers'],
    queryFn: () => api.getServers(),
  });

  // Toggle tool
  const toggleMutation = useMutation({
    mutationFn: (toolId: string) => api.toggleTool(toolId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mcp-tools'] });
    },
  });

  // Configure tool policy mutation
  const configMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => api.updateToolConfig(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mcp-tools'] });
      setConfiguringTool(null);
    },
    onError: (err: any) => alert(`Configuration update failed: ${err.message}`),
  });

  const handleOpenConfig = (tool: MCPTool) => {
    setConfiguringTool(tool);
    setConfigFormData({
      risk_level: tool.risk_level,
      requires_approval: tool.requires_approval,
      is_enabled: tool.is_enabled,
      description: tool.description || '',
    });
  };

  // Execute playground tool
  const executeMutation = useMutation({
    mutationFn: ({ name, args }: { name: string; args: any }) =>
      api.executePlaygroundTool(name, args),
    onSuccess: (data) => {
      setExecutionResult(data);
      queryClient.invalidateQueries({ queryKey: ['mcp-tools'] });
      queryClient.invalidateQueries({ queryKey: ['command-center-metrics'] });
    },
    onError: (err: any) => {
      setExecutionResult({
        is_success: false,
        error: err.message,
        duration_ms: 0,
      });
    },
  });

  const handleToolSelectForPlayground = (toolName: string) => {
    setPlaygroundToolName(toolName);
    const sample = SAMPLE_PAYLOADS[toolName] || {};
    setJsonInput(JSON.stringify(sample, null, 2));
    setExecutionResult(null);
  };

  const handleExecute = () => {
    try {
      const parsed = JSON.parse(jsonInput);
      executeMutation.mutate({ name: playgroundToolName, args: parsed });
    } catch (e: any) {
      alert(`Invalid JSON payload: ${e.message}`);
    }
  };

  const filteredTools = (tools || []).filter((t) => {
    const matchesSearch = t.name.toLowerCase().includes(searchFilter.toLowerCase()) ||
      (t.description || '').toLowerCase().includes(searchFilter.toLowerCase());
    const matchesRisk = riskFilter === 'ALL' || t.risk_level === riskFilter;
    return matchesSearch && matchesRisk;
  });

  const getServerName = (serverId: string) => {
    const s = (servers || []).find((srv) => srv.id === serverId);
    return s ? s.name : 'MCP Server';
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#303640] pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-[#ECEFF4] font-mono">
              CENTRAL TOOL REGISTRY & PLAYGROUND
            </h1>
            <span className="text-[11px] px-2 py-0.5 rounded bg-[#F0A43A]/15 text-[#F0A43A] font-mono border border-[#F0A43A]/30">
              SCHEMA INSPECTION & TEST EXECUTION
            </span>
          </div>
          <p className="text-xs text-[#9DA7B5] mt-1">
            Discover, configure policies, and interactively execute Model Context Protocol tools.
          </p>
        </div>

        {/* Tab Toggle */}
        <div className="flex items-center space-x-1 bg-[#14171D] p-1 border border-[#303640] rounded text-xs font-mono">
          <button
            onClick={() => setActiveTab('registry')}
            className={`px-3 py-1.5 rounded transition-colors flex items-center gap-1.5 ${
              activeTab === 'registry'
                ? 'bg-[#181C23] text-[#F0A43A] font-bold border border-[#F0A43A]/30'
                : 'text-[#9DA7B5] hover:text-[#ECEFF4]'
            }`}
          >
            <Wrench className="w-3.5 h-3.5" />
            Tool Registry ({tools?.length ?? 0})
          </button>
          <button
            onClick={() => setActiveTab('playground')}
            className={`px-3 py-1.5 rounded transition-colors flex items-center gap-1.5 ${
              activeTab === 'playground'
                ? 'bg-[#181C23] text-[#48B9D0] font-bold border border-[#48B9D0]/30'
                : 'text-[#9DA7B5] hover:text-[#ECEFF4]'
            }`}
          >
            <Play className="w-3.5 h-3.5" />
            Execution Playground
          </button>
        </div>
      </div>

      {activeTab === 'registry' ? (
        <>
          {/* Filters */}
          <div className="flex items-center justify-between gap-4 bg-[#14171D] p-3 border border-[#303640] rounded text-xs font-mono">
            <div className="flex items-center gap-2 flex-1 max-w-sm">
              <Search className="w-3.5 h-3.5 text-[#626D7C]" />
              <input
                type="text"
                placeholder="Search tools or input parameters..."
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
                className="w-full bg-[#181C23] border border-[#303640] rounded px-2.5 py-1 text-xs text-[#ECEFF4] placeholder-[#626D7C] focus:outline-none focus:border-[#F0A43A]"
              />
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[#626D7C] text-[11px]">RISK CLASSIFICATION:</span>
              {(['ALL', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] as const).map((r) => (
                <button
                  key={r}
                  onClick={() => setRiskFilter(r)}
                  className={`px-2.5 py-1 rounded text-[11px] transition-colors ${
                    riskFilter === r
                      ? 'bg-[#181C23] text-[#F0A43A] font-bold border border-[#F0A43A]/30'
                      : 'text-[#9DA7B5] hover:text-[#ECEFF4]'
                  }`}
                >
                  {r}
                </button>
              ))}
            </div>
          </div>

          {/* Tools Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {isLoading ? (
              <div className="col-span-3 text-center text-xs text-[#9DA7B5] py-12 font-mono">
                Discovering tools from connected MCP servers...
              </div>
            ) : (
              filteredTools.map((tool) => (
                <div
                  key={tool.id}
                  className={`bg-[#14171D] border rounded p-4 flex flex-col justify-between font-mono space-y-3 transition-colors ${
                    tool.is_enabled ? 'border-[#303640] hover:border-[#626D7C]' : 'border-[#303640]/50 opacity-60'
                  }`}
                >
                  <div>
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="text-xs font-bold text-[#ECEFF4] flex items-center gap-2">
                          <Wrench className="w-3.5 h-3.5 text-[#F0A43A]" />
                          {tool.name}
                        </div>
                        <div className="text-[10px] text-[#48B9D0] mt-0.5">
                          {getServerName(tool.server_id)}
                        </div>
                      </div>
                      <span className={`text-[9px] px-1.5 py-0.5 rounded font-bold ${
                        tool.risk_level === 'CRITICAL'
                          ? 'bg-[#E05252]/15 text-[#E05252] border border-[#E05252]/30'
                          : tool.risk_level === 'HIGH'
                          ? 'bg-[#EBB346]/15 text-[#EBB346] border border-[#EBB346]/30'
                          : 'bg-[#43B581]/15 text-[#43B581] border border-[#43B581]/30'
                      }`}>
                        {tool.risk_level} RISK
                      </span>
                    </div>

                    <p className="text-[11px] text-[#9DA7B5] mt-2 font-sans line-clamp-2">
                      {tool.description}
                    </p>
                  </div>

                  {/* Schema Preview */}
                  <div className="p-2 bg-[#101216] border border-[#303640] rounded text-[10px] text-[#626D7C] truncate">
                    Properties: {Object.keys(tool.input_schema?.properties || {}).join(', ') || 'No required arguments'}
                  </div>

                  <div className="pt-2 border-t border-[#303640] flex items-center justify-between text-[11px]">
                    <div className="flex items-center gap-3 text-[#9DA7B5]">
                      <span>Calls: {tool.total_executions}</span>
                      <span>Fails: {tool.failed_executions}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleOpenConfig(tool)}
                        className="px-2 py-1 bg-[#181C23] hover:bg-[#303640] border border-[#303640] rounded text-[10px] text-[#F0A43A] flex items-center gap-1"
                        title="Configure Tool Risk & Approvals"
                      >
                        <SlidersHorizontal className="w-2.5 h-2.5 text-[#F0A43A]" />
                        Config
                      </button>
                      <button
                        onClick={() => toggleMutation.mutate(tool.id)}
                        className={`p-1 rounded border text-[10px] ${
                          tool.is_enabled ? 'border-[#43B581]/40 text-[#43B581]' : 'border-[#E05252]/40 text-[#E05252]'
                        }`}
                        title={tool.is_enabled ? 'Disable Tool' : 'Enable Tool'}
                      >
                        <Power className="w-3 h-3" />
                      </button>
                      <button
                        onClick={() => {
                          handleToolSelectForPlayground(tool.name);
                          setActiveTab('playground');
                        }}
                        className="px-2 py-1 bg-[#181C23] hover:bg-[#303640] border border-[#303640] rounded text-[10px] text-[#ECEFF4] flex items-center gap-1"
                      >
                        <Play className="w-2.5 h-2.5 text-[#48B9D0]" />
                        Test
                      </button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </>
      ) : (
        /* PLAYGROUND WORKSPACE */
        <div className="grid grid-cols-12 gap-6 font-mono">
          {/* Playground Left: Tool Selector & JSON Input (6 cols) */}
          <div className="col-span-12 lg:col-span-6 space-y-4">
            <div className="bg-[#14171D] border border-[#303640] p-4 rounded space-y-3">
              <label className="text-[10px] text-[#9DA7B5] uppercase font-bold tracking-wider">
                Select Target MCP Tool
              </label>
              <select
                value={playgroundToolName}
                onChange={(e) => handleToolSelectForPlayground(e.target.value)}
                className="w-full bg-[#181C23] border border-[#303640] rounded p-2 text-xs text-[#ECEFF4] focus:outline-none focus:border-[#F0A43A]"
              >
                {(tools || []).map((t) => (
                  <option key={t.id} value={t.name}>
                    {t.name} ({getServerName(t.server_id)} - {t.risk_level} Risk)
                  </option>
                ))}
              </select>

              {/* Quick Preset Buttons */}
              <div className="flex flex-wrap gap-1.5 pt-1">
                <span className="text-[10px] text-[#626D7C] self-center mr-1">Quick Presets:</span>
                {['get_project_details', 'get_inventory', 'get_equipment_status', 'report_equipment_issue'].map((p) => (
                  <button
                    key={p}
                    onClick={() => handleToolSelectForPlayground(p)}
                    className={`text-[10px] px-2 py-0.5 rounded border transition-colors ${
                      playgroundToolName === p
                        ? 'bg-[#F0A43A]/20 text-[#F0A43A] border-[#F0A43A]/40'
                        : 'bg-[#181C23] text-[#9DA7B5] border-[#303640] hover:text-[#ECEFF4]'
                    }`}
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>

            {/* JSON Input Editor */}
            <div className="bg-[#14171D] border border-[#303640] p-4 rounded space-y-3">
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold text-[#ECEFF4] flex items-center gap-2">
                  <Code className="w-3.5 h-3.5 text-[#F0A43A]" />
                  JSON Input Arguments
                </span>
                <button
                  onClick={() => {
                    try {
                      setJsonInput(JSON.stringify(JSON.parse(jsonInput), null, 2));
                    } catch (_) {}
                  }}
                  className="text-[10px] text-[#48B9D0] hover:underline"
                >
                  Format JSON
                </button>
              </div>

              <textarea
                rows={10}
                value={jsonInput}
                onChange={(e) => setJsonInput(e.target.value)}
                className="w-full bg-[#101216] border border-[#303640] rounded p-3 text-xs text-[#43B581] font-mono focus:outline-none focus:border-[#F0A43A]"
              />

              <div className="flex items-center justify-between pt-2">
                <span className="text-[10px] text-[#626D7C]">
                  Protocol transport: STDIO / JSON-RPC 2.0
                </span>
                <button
                  onClick={handleExecute}
                  disabled={executeMutation.isPending}
                  className="flex items-center gap-2 px-5 py-2 bg-[#F0A43A] hover:bg-[#F0A43A]/90 text-[#101216] font-bold rounded text-xs transition-colors"
                >
                  <Play className={`w-3.5 h-3.5 ${executeMutation.isPending ? 'animate-spin' : ''}`} />
                  {executeMutation.isPending ? 'Executing Tool...' : 'Execute Tool Call'}
                </button>
              </div>
            </div>
          </div>

          {/* Playground Right: Live Output Inspector (6 cols) */}
          <div className="col-span-12 lg:col-span-6 bg-[#14171D] border border-[#303640] p-4 rounded flex flex-col justify-between space-y-3">
            <div>
              <div className="flex items-center justify-between border-b border-[#303640] pb-2 text-xs">
                <span className="font-bold text-[#ECEFF4] flex items-center gap-2">
                  <Terminal className="w-3.5 h-3.5 text-[#48B9D0]" />
                  MCP Protocol Execution Result
                </span>
                {executionResult && (
                  <div className="flex items-center gap-3 text-[10px]">
                    <span className="text-[#9DA7B5]">{executionResult.duration_ms} ms</span>
                    <span className={`px-2 py-0.5 rounded font-bold ${
                      executionResult.is_success
                        ? 'bg-[#43B581]/15 text-[#43B581]'
                        : 'bg-[#E05252]/15 text-[#E05252]'
                    }`}>
                      {executionResult.is_success ? 'SUCCESS' : 'HALTED'}
                    </span>
                  </div>
                )}
              </div>

              {/* Result Body */}
              <div className="mt-3">
                {executionResult ? (
                  <div className="space-y-3">
                    {executionResult.error && (
                      <div className="p-3 bg-[#E05252]/15 border border-[#E05252]/30 rounded text-xs text-[#E05252]">
                        <div className="font-bold flex items-center gap-1.5">
                          <AlertTriangle className="w-3.5 h-3.5" />
                          Governance Intervention / Execution Block
                        </div>
                        <div className="mt-1 text-[11px]">{executionResult.error}</div>
                      </div>
                    )}

                    <div className="relative">
                      <pre className="bg-[#101216] border border-[#303640] p-3 rounded text-[11px] text-[#ECEFF4] overflow-x-auto max-h-80">
                        {JSON.stringify(executionResult.result, null, 2)}
                      </pre>
                      <button
                        onClick={() => {
                          navigator.clipboard.writeText(JSON.stringify(executionResult.result, null, 2));
                          setCopied(true);
                          setTimeout(() => setCopied(false), 2000);
                        }}
                        className="absolute right-2 top-2 p-1 bg-[#181C23] border border-[#303640] rounded text-[10px] text-[#9DA7B5] hover:text-[#ECEFF4]"
                      >
                        {copied ? <Check className="w-3 h-3 text-[#43B581]" /> : <Copy className="w-3 h-3" />}
                      </button>
                    </div>

                    {executionResult.trace_id && (
                      <div className="text-[10px] text-[#626D7C] flex items-center justify-between">
                        <span>Recorded Trace ID: {executionResult.trace_id}</span>
                        <span className="text-[#43B581]">Audit Log Enqueued</span>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="h-64 flex flex-col items-center justify-center text-[#626D7C] text-xs">
                    <Terminal className="w-8 h-8 opacity-40 mb-2" />
                    Click "Execute Tool Call" to trigger real MCP JSON-RPC execution.
                  </div>
                )}
              </div>
            </div>

            <div className="p-2.5 bg-[#181C23] border border-[#303640] rounded text-[10px] text-[#9DA7B5]">
              <span className="text-[#F0A43A] font-bold">DEFENSE-IN-DEPTH NOTE:</span> Sensitive destructive tools (e.g. reporting critical breakdown) automatically trigger the backend policy engine and enter the Administrative Approval Queue.
            </div>
          </div>
        </div>
      )}

      {/* CONFIGURE TOOL POLICY MODAL */}
      {configuringTool && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex items-center justify-center p-4 font-mono">
          <div className="bg-[#14171D] border border-[#303640] rounded-lg max-w-lg w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-[#303640] pb-3">
              <h3 className="text-sm font-bold text-[#ECEFF4] flex items-center gap-2">
                <SlidersHorizontal className="w-4 h-4 text-[#F0A43A]" />
                Configure Tool Policy: {configuringTool.name}
              </h3>
              <button onClick={() => setConfiguringTool(null)}>
                <X className="w-4 h-4 text-[#626D7C] hover:text-[#ECEFF4]" />
              </button>
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                configMutation.mutate({
                  id: configuringTool.id,
                  data: configFormData,
                });
              }}
              className="space-y-3 text-xs"
            >
              <div>
                <label className="text-[10px] text-[#9DA7B5] uppercase">Risk Classification</label>
                <select
                  value={configFormData.risk_level}
                  onChange={(e) => setConfigFormData({ ...configFormData, risk_level: e.target.value })}
                  className="w-full mt-1 bg-[#181C23] border border-[#303640] rounded p-2 text-[#ECEFF4]"
                >
                  <option value="LOW">LOW (Safe query / read-only)</option>
                  <option value="MEDIUM">MEDIUM (Standard business operation)</option>
                  <option value="HIGH">HIGH (High risk / elevated mutation)</option>
                  <option value="CRITICAL">CRITICAL (Destructive / Safety sensitive)</option>
                </select>
              </div>

              <div>
                <label className="text-[10px] text-[#9DA7B5] uppercase">Tool Description</label>
                <textarea
                  rows={2}
                  value={configFormData.description}
                  onChange={(e) => setConfigFormData({ ...configFormData, description: e.target.value })}
                  className="w-full mt-1 bg-[#181C23] border border-[#303640] rounded p-2 text-[#ECEFF4]"
                />
              </div>

              <div className="p-3 bg-[#181C23] border border-[#303640] rounded space-y-2">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={configFormData.requires_approval}
                    onChange={(e) => setConfigFormData({ ...configFormData, requires_approval: e.target.checked })}
                    className="accent-[#F0A43A]"
                  />
                  <div>
                    <div className="text-[#ECEFF4] font-semibold text-[11px]">Require Prior Approval</div>
                    <div className="text-[10px] text-[#9DA7B5]">Every execution will halt and queue into the Administrative Approval Queue.</div>
                  </div>
                </label>

                <label className="flex items-center gap-2 cursor-pointer pt-2 border-t border-[#303640]">
                  <input
                    type="checkbox"
                    checked={configFormData.is_enabled}
                    onChange={(e) => setConfigFormData({ ...configFormData, is_enabled: e.target.checked })}
                    className="accent-[#43B581]"
                  />
                  <div>
                    <div className="text-[#ECEFF4] font-semibold text-[11px]">Tool Enabled</div>
                    <div className="text-[10px] text-[#9DA7B5]">When disabled, tool execution requests are rejected immediately.</div>
                  </div>
                </label>
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-[#303640]">
                <button
                  type="button"
                  onClick={() => setConfiguringTool(null)}
                  className="px-4 py-1.5 bg-[#181C23] hover:bg-[#1F242D] border border-[#303640] rounded text-[#ECEFF4]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={configMutation.isPending}
                  className="px-4 py-1.5 bg-[#F0A43A] hover:bg-[#F0A43A]/90 text-[#101216] font-bold rounded"
                >
                  {configMutation.isPending ? 'Updating...' : 'Save Configuration'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
