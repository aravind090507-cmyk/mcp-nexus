import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../services/api';
import type { AIAgent } from '../../types';
import {
  Bot,
  Play,
  Sparkles,
  Layers,
  ShieldAlert,
  CheckCircle2,
  AlertCircle,
  Clock,
  Terminal,
  ArrowRight,
  Server,
  Wrench,
  Search,
  Cpu,
  ChevronDown,
  ChevronUp,
  Info,
  Plus,
  X
} from 'lucide-react';

const PRESET_QUERIES = [
  {
    title: 'Cross-Server Bottleneck Correlation',
    prompt: 'Find all projects with delayed equipment maintenance and insufficient inventory.',
    desc: 'Orchestrates ERP + Equipment + Inventory servers to uncover supply chain & plant failures.'
  },
  {
    title: 'Heavy Plant Overdue Telemetry',
    prompt: 'Find all equipment requiring maintenance within the next 30 days and check vibration alarms.',
    desc: 'Queries Equipment fleet telemetry and preventative maintenance schedules.'
  },
  {
    title: 'Warehouse Critical Stock Check',
    prompt: 'Check stock availability and low stock warnings for structural materials across all yards.',
    desc: 'Inspects central warehouse inventory against safety stock multipliers.'
  },
  {
    title: 'Hazira Project Financial CAPEX Audit',
    prompt: 'Get project details and financial summary for project PRJ-HAZ-002.',
    desc: 'Fetches ERP milestone billings, burn rates, and margin variances.'
  }
];

export const AgentOrchestration: React.FC = () => {
  const queryClient = useQueryClient();
  const [selectedAgentId, setSelectedAgentId] = useState<string>('');
  const [userPrompt, setUserPrompt] = useState<string>(PRESET_QUERIES[0].prompt);
  const [orchestrationResult, setOrchestrationResult] = useState<any>(null);
  const [expandedSpan, setExpandedSpan] = useState<number | null>(null);
  const [showRegisterModal, setShowRegisterModal] = useState(false);

  const [newAgentData, setNewAgentData] = useState({
    name: '',
    identifier: '',
    description: '',
    llm_provider: 'GEMINI',
    model: 'gemini-1.5-pro',
    system_prompt: '',
    max_execution_steps: 5,
    execution_policy: 'STRICT',
    assigned_server_ids: [] as string[],
  });

  const { data: agents, isLoading: isAgentsLoading } = useQuery({
    queryKey: ['ai-agents'],
    queryFn: () => api.getAgents(),
  });

  const { data: servers } = useQuery({
    queryKey: ['mcp-servers'],
    queryFn: () => api.getServers(),
  });

  const registerAgentMutation = useMutation({
    mutationFn: (payload: any) => api.createAgent(payload),
    onSuccess: (newAgent) => {
      queryClient.invalidateQueries({ queryKey: ['ai-agents'] });
      setShowRegisterModal(false);
      setSelectedAgentId(newAgent.id);
      setNewAgentData({
        name: '',
        identifier: '',
        description: '',
        llm_provider: 'GEMINI',
        model: 'gemini-1.5-pro',
        system_prompt: '',
        max_execution_steps: 5,
        execution_policy: 'STRICT',
        assigned_server_ids: [],
      });
    },
    onError: (err: any) => alert(`Agent registration failed: ${err.message}`),
  });

  const activeAgent = (agents || []).find((a) => a.id === selectedAgentId) || (agents && agents[0]);

  const orchestrateMutation = useMutation({
    mutationFn: ({ agent_id, prompt }: { agent_id: string; prompt: string }) =>
      api.orchestrate(agent_id, prompt),
    onSuccess: (data) => {
      setOrchestrationResult(data);
      queryClient.invalidateQueries({ queryKey: ['ai-agents'] });
      queryClient.invalidateQueries({ queryKey: ['command-center-metrics'] });
      queryClient.invalidateQueries({ queryKey: ['execution-traces'] });
    },
    onError: (err: any) => {
      setOrchestrationResult({
        overall_status: 'FAILED',
        synthesis: `Orchestration Error: ${err.message}`,
        duration_ms: 0,
        tool_executions: [],
        spans: []
      });
    }
  });

  const handleRunOrchestration = () => {
    if (!activeAgent) return;
    orchestrateMutation.mutate({
      agent_id: activeAgent.id,
      prompt: userPrompt
    });
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#303640] pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-[#ECEFF4] font-mono">
              AI AGENT ORCHESTRATION WORKSPACE
            </h1>
            <span className="text-[11px] px-2 py-0.5 rounded bg-[#F0A43A]/15 text-[#F0A43A] font-mono border border-[#F0A43A]/30">
              CROSS-SERVER MULTI-STEP REASONING
            </span>
          </div>
          <p className="text-xs text-[#9DA7B5] mt-1">
            Empower AI agents to dynamically discover, evaluate governance policies, and coordinate sequential tool calls across multiple MCP servers.
          </p>
        </div>
        <button
          onClick={() => setShowRegisterModal(true)}
          className="flex items-center gap-2 px-3.5 py-1.5 bg-[#F0A43A] hover:bg-[#F0A43A]/90 text-[#101216] font-semibold rounded text-xs transition-colors"
        >
          <Plus className="w-4 h-4" />
          Register AI Agent
        </button>
      </div>

      {/* Agent Selector Card */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {(agents || []).map((agent) => {
          const isSelected = (activeAgent?.id === agent.id);
          return (
            <div
              key={agent.id}
              onClick={() => setSelectedAgentId(agent.id)}
              className={`p-4 bg-[#14171D] border rounded cursor-pointer transition-all font-mono ${
                isSelected
                  ? 'border-[#F0A43A] shadow-md bg-[#181C23]'
                  : 'border-[#303640] hover:border-[#626D7C]'
              }`}
            >
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded bg-[#101216] border border-[#303640] flex items-center justify-center">
                    <Bot className="w-5 h-5 text-[#F0A43A]" />
                  </div>
                  <div>
                    <div className="text-xs font-bold text-[#ECEFF4] flex items-center gap-2">
                      {agent.name}
                      <span className="text-[9px] px-1.5 py-0.2 rounded font-bold bg-[#43B581]/15 text-[#43B581]">
                        {agent.status}
                      </span>
                    </div>
                    <div className="text-[10px] text-[#9DA7B5] mt-0.5">
                      {agent.llm_provider} • Model: {agent.model} • Max Steps: {agent.max_execution_steps}
                    </div>
                  </div>
                </div>
                <span className="text-[10px] text-[#626D7C]">
                  {agent.total_orchestrations} Runs
                </span>
              </div>
              <p className="text-[11px] text-[#9DA7B5] mt-2 line-clamp-2 font-sans">
                {agent.description}
              </p>
            </div>
          );
        })}
      </div>

      {/* Main Orchestration Arena (12-column layout) */}
      <div className="grid grid-cols-12 gap-6 font-mono">
        {/* Left: Query Composer & Quick Presets (5 cols) */}
        <div className="col-span-12 lg:col-span-5 space-y-4">
          <div className="bg-[#14171D] border border-[#303640] p-4 rounded space-y-3">
            <div className="flex items-center justify-between text-xs">
              <span className="font-bold text-[#ECEFF4] flex items-center gap-2">
                <Sparkles className="w-3.5 h-3.5 text-[#F0A43A]" />
                Natural Language Instruction
              </span>
              <span className="text-[10px] text-[#626D7C]">
                Agent: {activeAgent?.name}
              </span>
            </div>

            <textarea
              rows={4}
              value={userPrompt}
              onChange={(e) => setUserPrompt(e.target.value)}
              placeholder="Enter cross-server instruction (e.g. Find all equipment with delayed maintenance...)"
              className="w-full bg-[#101216] border border-[#303640] rounded p-3 text-xs text-[#ECEFF4] focus:outline-none focus:border-[#F0A43A]"
            />

            <button
              onClick={handleRunOrchestration}
              disabled={orchestrateMutation.isPending || !activeAgent}
              className="w-full py-2.5 bg-[#F0A43A] hover:bg-[#F0A43A]/90 text-[#101216] font-bold rounded text-xs flex items-center justify-center gap-2 transition-colors"
            >
              <Play className={`w-3.5 h-3.5 ${orchestrateMutation.isPending ? 'animate-spin' : ''}`} />
              {orchestrateMutation.isPending ? 'Orchestrating Protocol Calls...' : 'Execute AI Orchestration'}
            </button>
          </div>

          {/* Quick Preset Workflows */}
          <div className="bg-[#14171D] border border-[#303640] p-4 rounded space-y-2">
            <div className="text-[10px] font-bold text-[#626D7C] uppercase tracking-wider">
              Recommended Enterprise Workflows (L&T Operations)
            </div>
            <div className="space-y-2">
              {PRESET_QUERIES.map((item, idx) => (
                <div
                  key={idx}
                  onClick={() => setUserPrompt(item.prompt)}
                  className={`p-2.5 rounded border cursor-pointer text-xs transition-colors ${
                    userPrompt === item.prompt
                      ? 'bg-[#181C23] border-[#F0A43A] text-[#ECEFF4]'
                      : 'bg-[#101216] border-[#303640] text-[#9DA7B5] hover:border-[#626D7C]'
                  }`}
                >
                  <div className="font-bold text-[11px] text-[#F0A43A] flex items-center justify-between">
                    <span>{item.title}</span>
                    <ArrowRight className="w-3 h-3 text-[#626D7C]" />
                  </div>
                  <div className="text-[10px] text-[#626D7C] mt-1">{item.desc}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right: Real-time Execution Pipeline & Synthesis (7 cols) */}
        <div className="col-span-12 lg:col-span-7 bg-[#14171D] border border-[#303640] p-5 rounded space-y-4">
          <div className="flex items-center justify-between border-b border-[#303640] pb-3 text-xs">
            <span className="font-bold text-[#ECEFF4] flex items-center gap-2">
              <Cpu className="w-4 h-4 text-[#48B9D0]" />
              Execution Pipeline & Synthesis
            </span>

            {orchestrationResult && (
              <div className="flex items-center gap-3 text-[10px]">
                {/* Transparent Mode Badge (Requirement: Never mislead user about demo mode vs live LLM) */}
                <span className={`px-2 py-0.5 rounded font-bold border ${
                  orchestrationResult.execution_mode === 'LIVE_LLM'
                    ? 'bg-[#43B581]/15 text-[#43B581] border-[#43B581]/40'
                    : 'bg-[#48B9D0]/15 text-[#48B9D0] border-[#48B9D0]/40'
                }`}>
                  MODE: {orchestrationResult.execution_mode}
                </span>
                <span className="text-[#9DA7B5]">{orchestrationResult.duration_ms} ms</span>
              </div>
            )}
          </div>

          {orchestrationResult ? (
            <div className="space-y-4">
              {/* Consolidated Synthesis Card */}
              <div className="p-4 bg-[#181C23] border border-[#F0A43A]/40 rounded space-y-2">
                <div className="text-xs font-bold text-[#F0A43A] flex items-center gap-2">
                  <Sparkles className="w-3.5 h-3.5 text-[#F0A43A]" />
                  Consolidated Operational Intelligence
                </div>
                <div className="text-xs text-[#ECEFF4] leading-relaxed whitespace-pre-line font-sans">
                  {orchestrationResult.synthesis}
                </div>
              </div>

              {/* Sequential Tool Dispatches */}
              {orchestrationResult.tool_executions?.length > 0 && (
                <div className="space-y-2">
                  <div className="text-[11px] font-bold text-[#9DA7B5] uppercase">
                    Cross-Server Tool Invocations ({orchestrationResult.tool_executions.length})
                  </div>
                  <div className="space-y-2">
                    {orchestrationResult.tool_executions.map((exec: any) => (
                      <div
                        key={exec.step}
                        className="p-3 bg-[#101216] border border-[#303640] rounded text-xs space-y-1.5"
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2 font-bold text-[#ECEFF4]">
                            <span className="w-4 h-4 rounded-full bg-[#181C23] border border-[#303640] text-[10px] flex items-center justify-center text-[#F0A43A]">
                              {exec.step}
                            </span>
                            <span>{exec.tool}</span>
                            <span className="text-[10px] font-normal text-[#48B9D0]">({exec.server})</span>
                          </div>
                          <span className="text-[9px] px-1.5 py-0.2 rounded font-bold bg-[#43B581]/15 text-[#43B581]">
                            DISPATCH OK
                          </span>
                        </div>
                        <div className="text-[10px] text-[#626D7C] truncate">
                          Args: {JSON.stringify(exec.arguments)}
                        </div>
                        <div className="bg-[#181C23] p-2 rounded text-[10px] text-[#9DA7B5] max-h-24 overflow-y-auto">
                          {JSON.stringify(exec.output, null, 2)}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Step-by-Step Spans Timeline */}
              {orchestrationResult.spans?.length > 0 && (
                <div className="space-y-2">
                  <div className="text-[11px] font-bold text-[#9DA7B5] uppercase">
                    Stage Trace Breakdown (6 Stages)
                  </div>
                  <div className="space-y-1.5">
                    {orchestrationResult.spans.map((span: any, index: number) => {
                      const isExpanded = expandedSpan === index;
                      return (
                        <div
                          key={index}
                          className="bg-[#101216] border border-[#303640] rounded text-xs"
                        >
                          <div
                            onClick={() => setExpandedSpan(isExpanded ? null : index)}
                            className="p-2 flex items-center justify-between cursor-pointer hover:bg-[#181C23]/60 transition-colors"
                          >
                            <div className="flex items-center gap-2">
                              <span className={`w-2 h-2 rounded-full ${span.status === 'COMPLETED' ? 'bg-[#43B581]' : 'bg-[#E05252]'}`} />
                              <span className="font-semibold text-[#ECEFF4] text-[11px]">{span.name}</span>
                              <span className="text-[9px] px-1 bg-[#181C23] text-[#626D7C] rounded">
                                {span.stage}
                              </span>
                            </div>
                            <div className="flex items-center gap-3 text-[10px] text-[#9DA7B5]">
                              <span>{span.duration_ms} ms</span>
                              {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                            </div>
                          </div>

                          {isExpanded && (
                            <div className="p-3 border-t border-[#303640] bg-[#14171D] text-[10px] space-y-1">
                              <pre className="text-[#ECEFF4] overflow-x-auto">
                                {JSON.stringify(span.details, null, 2)}
                              </pre>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="h-96 flex flex-col items-center justify-center text-[#626D7C] text-xs space-y-2">
              <Bot className="w-10 h-10 opacity-30 text-[#F0A43A]" />
              <div>Select an enterprise instruction and click "Execute AI Orchestration".</div>
              <div className="text-[10px] text-[#626D7C]">Cross-server protocol tracing will appear here in real-time.</div>
            </div>
          )}
        </div>
      </div>

      {/* REGISTER AGENT MODAL */}
      {showRegisterModal && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#14171D] border border-[#303640] rounded-lg max-w-xl w-full p-6 space-y-4 font-mono shadow-2xl">
            <div className="flex items-center justify-between border-b border-[#303640] pb-3">
              <h3 className="text-sm font-bold text-[#ECEFF4] flex items-center gap-2">
                <Bot className="w-4 h-4 text-[#F0A43A]" />
                Register New Enterprise AI Agent
              </h3>
              <button onClick={() => setShowRegisterModal(false)}>
                <X className="w-4 h-4 text-[#626D7C] hover:text-[#ECEFF4]" />
              </button>
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                registerAgentMutation.mutate({
                  ...newAgentData,
                  max_execution_steps: Number(newAgentData.max_execution_steps),
                });
              }}
              className="space-y-3 text-xs"
            >
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] text-[#9DA7B5] uppercase">Agent Name</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Titan-Procure"
                    value={newAgentData.name}
                    onChange={(e) => setNewAgentData({ ...newAgentData, name: e.target.value })}
                    className="w-full mt-1 bg-[#181C23] border border-[#303640] rounded p-2 text-[#ECEFF4]"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-[#9DA7B5] uppercase">Identifier Code</label>
                  <input
                    type="text"
                    required
                    placeholder="agent-titan-02"
                    value={newAgentData.identifier}
                    onChange={(e) => setNewAgentData({ ...newAgentData, identifier: e.target.value })}
                    className="w-full mt-1 bg-[#181C23] border border-[#303640] rounded p-2 text-[#ECEFF4]"
                  />
                </div>
              </div>

              <div>
                <label className="text-[10px] text-[#9DA7B5] uppercase">Description</label>
                <textarea
                  rows={2}
                  placeholder="Specialized multi-server orchestration role and mission..."
                  value={newAgentData.description}
                  onChange={(e) => setNewAgentData({ ...newAgentData, description: e.target.value })}
                  className="w-full mt-1 bg-[#181C23] border border-[#303640] rounded p-2 text-[#ECEFF4]"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] text-[#9DA7B5] uppercase">LLM Provider</label>
                  <select
                    value={newAgentData.llm_provider}
                    onChange={(e) => setNewAgentData({ ...newAgentData, llm_provider: e.target.value })}
                    className="w-full mt-1 bg-[#181C23] border border-[#303640] rounded p-2 text-[#ECEFF4]"
                  >
                    <option value="GEMINI">Google Gemini</option>
                    <option value="ANTHROPIC">Anthropic Claude</option>
                    <option value="OPENAI">OpenAI</option>
                    <option value="DATABRICKS">Databricks Foundation</option>
                  </select>
                </div>
                <div>
                  <label className="text-[10px] text-[#9DA7B5] uppercase">Model Name</label>
                  <input
                    type="text"
                    required
                    placeholder="gemini-1.5-pro"
                    value={newAgentData.model}
                    onChange={(e) => setNewAgentData({ ...newAgentData, model: e.target.value })}
                    className="w-full mt-1 bg-[#181C23] border border-[#303640] rounded p-2 text-[#ECEFF4]"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] text-[#9DA7B5] uppercase">Execution Policy</label>
                  <select
                    value={newAgentData.execution_policy}
                    onChange={(e) => setNewAgentData({ ...newAgentData, execution_policy: e.target.value })}
                    className="w-full mt-1 bg-[#181C23] border border-[#303640] rounded p-2 text-[#ECEFF4]"
                  >
                    <option value="STRICT">STRICT (Require Approval for Destructive Tools)</option>
                    <option value="SUPERVISED">SUPERVISED (Log & Notify All Actions)</option>
                    <option value="AUTONOMOUS">AUTONOMOUS (Allow Safe Read Tools)</option>
                  </select>
                </div>
                <div>
                  <label className="text-[10px] text-[#9DA7B5] uppercase">Max Execution Steps</label>
                  <input
                    type="number"
                    min="1"
                    max="20"
                    value={newAgentData.max_execution_steps}
                    onChange={(e) => setNewAgentData({ ...newAgentData, max_execution_steps: Number(e.target.value) })}
                    className="w-full mt-1 bg-[#181C23] border border-[#303640] rounded p-2 text-[#ECEFF4]"
                  />
                </div>
              </div>

              <div>
                <label className="text-[10px] text-[#9DA7B5] uppercase">Assigned MCP Servers</label>
                <div className="grid grid-cols-2 gap-2 mt-1 max-h-28 overflow-y-auto p-2 bg-[#101216] border border-[#303640] rounded">
                  {(servers || []).map((srv) => {
                    const isChecked = newAgentData.assigned_server_ids.includes(srv.id);
                    return (
                      <label key={srv.id} className="flex items-center gap-2 text-[11px] cursor-pointer">
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setNewAgentData({
                                ...newAgentData,
                                assigned_server_ids: [...newAgentData.assigned_server_ids, srv.id]
                              });
                            } else {
                              setNewAgentData({
                                ...newAgentData,
                                assigned_server_ids: newAgentData.assigned_server_ids.filter((id) => id !== srv.id)
                              });
                            }
                          }}
                          className="accent-[#F0A43A]"
                        />
                        <span className="text-[#ECEFF4] truncate">{srv.name}</span>
                      </label>
                    );
                  })}
                </div>
              </div>

              <div>
                <label className="text-[10px] text-[#9DA7B5] uppercase">System Prompt Instructions</label>
                <textarea
                  rows={2}
                  placeholder="You are an enterprise AI agent orchestrating multi-server operations..."
                  value={newAgentData.system_prompt}
                  onChange={(e) => setNewAgentData({ ...newAgentData, system_prompt: e.target.value })}
                  className="w-full mt-1 bg-[#181C23] border border-[#303640] rounded p-2 text-[#ECEFF4]"
                />
              </div>

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
                  disabled={registerAgentMutation.isPending}
                  className="px-4 py-1.5 bg-[#F0A43A] hover:bg-[#F0A43A]/90 text-[#101216] font-bold rounded"
                >
                  {registerAgentMutation.isPending ? 'Registering...' : 'Register Agent'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
