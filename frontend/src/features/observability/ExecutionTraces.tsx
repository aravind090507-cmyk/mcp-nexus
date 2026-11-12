import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../services/api';
import type { ExecutionTrace, Span } from '../../types';
import {
  Activity,
  Search,
  CheckCircle,
  AlertOctagon,
  Clock,
  ArrowRight,
  Terminal,
  ChevronRight,
  X,
  ShieldAlert,
  Server,
  Wrench,
  Bot
} from 'lucide-react';

export const ExecutionTraces: React.FC = () => {
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('ALL');

  const { data: traces, isLoading } = useQuery({
    queryKey: ['execution-traces', statusFilter],
    queryFn: () => api.getTraces(statusFilter === 'ALL' ? undefined : statusFilter),
    refetchInterval: 8000,
  });

  const { data: selectedTrace, isLoading: isTraceLoading } = useQuery({
    queryKey: ['execution-trace-detail', selectedTraceId],
    queryFn: () => (selectedTraceId ? api.getTrace(selectedTraceId) : null),
    enabled: !!selectedTraceId,
  });

  const stagesList = [
    { key: 'USER_REQUEST', label: 'USER REQUEST', icon: Bot },
    { key: 'AGENT_DECISION', label: 'AGENT DECISION', icon: Activity },
    { key: 'POLICY_VALIDATION', label: 'POLICY VALIDATION', icon: ShieldAlert },
    { key: 'MCP_SERVER', label: 'MCP SERVER', icon: Server },
    { key: 'TOOL_EXECUTION', label: 'TOOL EXECUTION', icon: Wrench },
    { key: 'RESPONSE', label: 'RESPONSE', icon: CheckCircle },
  ];

  return (
    <div className="space-y-6 font-mono">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#303640] pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-[#ECEFF4]">
              EXECUTION TRACE EXPLORER
            </h1>
            <span className="text-[11px] px-2 py-0.5 rounded bg-[#48B9D0]/15 text-[#48B9D0] border border-[#48B9D0]/30">
              DISTRIBUTED PROTOCOL TELEMETRY
            </span>
          </div>
          <p className="text-xs text-[#9DA7B5] mt-1 font-sans">
            End-to-end distributed execution spans tracing queries from user input through policy validation, MCP transport dispatch, to tool execution.
          </p>
        </div>

        {/* Status Filter */}
        <div className="flex items-center space-x-1 bg-[#14171D] p-1 border border-[#303640] rounded text-xs">
          {(['ALL', 'SUCCESS', 'FAILED', 'BLOCKED', 'PENDING_APPROVAL'] as const).map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`px-3 py-1 rounded transition-colors text-[11px] ${
                statusFilter === st
                  ? 'bg-[#181C23] text-[#F0A43A] font-bold border border-[#F0A43A]/30'
                  : 'text-[#9DA7B5] hover:text-[#ECEFF4]'
              }`}
            >
              {st}
            </button>
          ))}
        </div>
      </div>

      {/* Traces List Table */}
      <div className="bg-[#14171D] border border-[#303640] rounded overflow-hidden">
        <table className="w-full text-left text-xs">
          <thead className="bg-[#181C23] text-[#9DA7B5] border-b border-[#303640]">
            <tr>
              <th className="py-2.5 px-3">Trace ID</th>
              <th className="py-2.5 px-3">Tool Invocations</th>
              <th className="py-2.5 px-3">Parent Server</th>
              <th className="py-2.5 px-3">Status</th>
              <th className="py-2.5 px-3">Duration</th>
              <th className="py-2.5 px-3">Risk Level</th>
              <th className="py-2.5 px-3">Timestamp</th>
              <th className="py-2.5 px-3 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#303640]">
            {isLoading ? (
              <tr>
                <td colSpan={8} className="py-8 text-center text-[#9DA7B5]">
                  Reading execution traces...
                </td>
              </tr>
            ) : (traces || []).length === 0 ? (
              <tr>
                <td colSpan={8} className="py-8 text-center text-[#626D7C]">
                  No execution traces recorded yet. Run a tool in the Playground or Agent Orchestrator.
                </td>
              </tr>
            ) : (
              (traces || []).map((t) => (
                <tr key={t.id} className="hover:bg-[#181C23]/40 cursor-pointer" onClick={() => setSelectedTraceId(t.id)}>
                  <td className="py-2.5 px-3 font-bold text-[#48B9D0]">{t.trace_id}</td>
                  <td className="py-2.5 px-3 font-semibold text-[#ECEFF4] max-w-xs truncate">{t.tool_name}</td>
                  <td className="py-2.5 px-3 text-[#9DA7B5]">{t.server_name || 'Multi-Server'}</td>
                  <td className="py-2.5 px-3">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      t.status === 'SUCCESS'
                        ? 'bg-[#43B581]/15 text-[#43B581]'
                        : t.status === 'BLOCKED'
                        ? 'bg-[#EBB346]/15 text-[#EBB346]'
                        : 'bg-[#E05252]/15 text-[#E05252]'
                    }`}>
                      {t.status}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-[#ECEFF4]">{t.duration_ms} ms</td>
                  <td className="py-2.5 px-3">
                    <span className={`text-[10px] ${t.risk_level === 'CRITICAL' || t.risk_level === 'HIGH' ? 'text-[#E05252]' : 'text-[#43B581]'}`}>
                      {t.risk_level}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-[#626D7C] whitespace-nowrap">
                    {new Date(t.created_at).toLocaleTimeString()}
                  </td>
                  <td className="py-2.5 px-3 text-right">
                    <button
                      onClick={() => setSelectedTraceId(t.id)}
                      className="px-2 py-1 bg-[#181C23] hover:bg-[#303640] border border-[#303640] rounded text-[10px] text-[#ECEFF4]"
                    >
                      Inspect Timeline
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* TRACE DETAIL MODAL / INSPECTOR */}
      {selectedTraceId && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#14171D] border border-[#303640] rounded-lg max-w-4xl w-full max-h-[90vh] flex flex-col font-mono shadow-2xl">
            {/* Modal Header */}
            <div className="p-4 border-b border-[#303640] flex items-center justify-between bg-[#181C23]">
              <div className="flex items-center gap-3">
                <Activity className="w-5 h-5 text-[#F0A43A]" />
                <div>
                  <h3 className="text-sm font-bold text-[#ECEFF4] flex items-center gap-2">
                    Execution Trace: {selectedTrace?.trace_id}
                    <span className={`text-[10px] px-2 py-0.2 rounded font-bold ${
                      selectedTrace?.status === 'SUCCESS' ? 'bg-[#43B581]/15 text-[#43B581]' : 'bg-[#E05252]/15 text-[#E05252]'
                    }`}>
                      {selectedTrace?.status}
                    </span>
                  </h3>
                  <div className="text-[10px] text-[#9DA7B5]">
                    Request: {selectedTrace?.request_id} • Duration: {selectedTrace?.duration_ms} ms
                  </div>
                </div>
              </div>
              <button onClick={() => setSelectedTraceId(null)}>
                <X className="w-4 h-4 text-[#626D7C] hover:text-[#ECEFF4]" />
              </button>
            </div>

            {/* Modal Body: Visual 6-Stage Timeline */}
            <div className="p-6 overflow-y-auto space-y-6">
              {/* STAGE TIMELINE DIAGRAM (USER REQUEST -> AGENT DECISION -> POLICY VALIDATION -> MCP SERVER -> TOOL EXECUTION -> RESPONSE) */}
              <div>
                <div className="text-[11px] font-bold text-[#9DA7B5] uppercase mb-3">
                  Visual Execution Timeline (6 Critical Pipeline Gates)
                </div>
                <div className="grid grid-cols-6 gap-2">
                  {stagesList.map((st, i) => {
                    const Icon = st.icon;
                    return (
                      <div key={st.key} className="relative">
                        <div className="p-3 bg-[#101216] border border-[#303640] rounded flex flex-col items-center text-center space-y-1">
                          <Icon className="w-4 h-4 text-[#F0A43A]" />
                          <span className="text-[9px] font-bold text-[#ECEFF4] leading-tight">
                            {st.label}
                          </span>
                          <span className="text-[8px] text-[#43B581] font-mono">GATE {i + 1}</span>
                        </div>
                        {i < 5 && (
                          <div className="hidden lg:block absolute -right-2 top-1/2 -translate-y-1/2 z-10 text-[#626D7C]">
                            →
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Spans breakdown */}
              {selectedTrace?.spans && selectedTrace.spans.length > 0 && (
                <div className="space-y-2">
                  <div className="text-[11px] font-bold text-[#9DA7B5] uppercase">
                    Detailed Stage Telemetry Spans
                  </div>
                  <div className="space-y-2">
                    {selectedTrace.spans.map((span, idx) => (
                      <div key={idx} className="p-3 bg-[#101216] border border-[#303640] rounded text-xs space-y-1">
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-[#48B9D0]">{span.name}</span>
                          <span className="text-[#ECEFF4]">{span.duration_ms} ms</span>
                        </div>
                        <div className="text-[10px] text-[#626D7C]">Stage: {span.stage} • Time: {span.timestamp}</div>
                        <pre className="text-[10px] text-[#9DA7B5] bg-[#181C23] p-2 rounded overflow-x-auto mt-1">
                          {JSON.stringify(span.details, null, 2)}
                        </pre>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Input & Output */}
              <div className="grid grid-cols-2 gap-4 text-xs">
                <div>
                  <div className="text-[11px] font-bold text-[#9DA7B5] uppercase mb-1">Input Parameters</div>
                  <pre className="p-3 bg-[#101216] border border-[#303640] rounded text-[11px] text-[#43B581] overflow-x-auto max-h-48">
                    {JSON.stringify(selectedTrace?.input_parameters, null, 2)}
                  </pre>
                </div>
                <div>
                  <div className="text-[11px] font-bold text-[#9DA7B5] uppercase mb-1">Execution Response</div>
                  <pre className="p-3 bg-[#101216] border border-[#303640] rounded text-[11px] text-[#ECEFF4] overflow-x-auto max-h-48">
                    {JSON.stringify(selectedTrace?.output_response, null, 2)}
                  </pre>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
