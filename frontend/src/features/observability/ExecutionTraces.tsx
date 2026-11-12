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
  Bot,
  Filter,
  Layers,
  Copy,
  Check,
  RefreshCw,
  FileText
} from 'lucide-react';

export const ExecutionTraces: React.FC = () => {
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedSpanIdx, setSelectedSpanIdx] = useState<number | null>(null);
  const [copiedText, setCopiedText] = useState<string | null>(null);

  const { data: traces, isLoading, refetch, isFetching } = useQuery({
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
    { key: 'AGENT_DECISION', label: 'AGENT PLANNING', icon: Activity },
    { key: 'POLICY_VALIDATION', label: 'POLICY EVAL', icon: ShieldAlert },
    { key: 'MCP_SERVER', label: 'MCP PROTOCOL', icon: Server },
    { key: 'TOOL_EXECUTION', label: 'TOOL EXECUTION', icon: Wrench },
    { key: 'RESPONSE', label: 'SYNTHESIS', icon: CheckCircle },
  ];

  const filteredTraces = (traces || []).filter((t) => {
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchId = t.trace_id.toLowerCase().includes(q);
      const matchTool = t.tool_name.toLowerCase().includes(q);
      const matchServer = (t.server_name || '').toLowerCase().includes(q);
      const matchQuery = (t.user_query || '').toLowerCase().includes(q);
      if (!matchId && !matchTool && !matchServer && !matchQuery) return false;
    }
    return true;
  });

  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopiedText(label);
    setTimeout(() => setCopiedText(null), 2000);
  };

  // Metrics summary
  const totalCount = traces?.length || 0;
  const successCount = traces?.filter((t) => t.status === 'SUCCESS').length || 0;
  const blockedCount = traces?.filter((t) => t.status === 'BLOCKED').length || 0;
  const avgDuration = totalCount > 0 ? Math.round(traces!.reduce((acc, t) => acc + t.duration_ms, 0) / totalCount) : 0;
  const successRate = totalCount > 0 ? Math.round((successCount / totalCount) * 100) : 100;

  // Active span in selected trace
  const activeSpan =
    selectedTrace?.spans && selectedSpanIdx !== null && selectedSpanIdx < selectedTrace.spans.length
      ? selectedTrace.spans[selectedSpanIdx]
      : selectedTrace?.spans?.[0] || null;

  return (
    <div className="space-y-6 font-mono">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between border-b border-[#303640] pb-4 gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-[#ECEFF4]">
              WATERFALL EXECUTION TRACE EXPLORER
            </h1>
            <span className="text-[11px] px-2 py-0.5 rounded bg-[#48B9D0]/15 text-[#48B9D0] border border-[#48B9D0]/30">
              DISTRIBUTED PROTOCOL TELEMETRY
            </span>
          </div>
          <p className="text-xs text-[#9DA7B5] mt-1 font-sans">
            End-to-end distributed execution spans tracing queries through policy validation, MCP transport dispatch, tool execution and response synthesis.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#181C23] hover:bg-[#303640] border border-[#303640] rounded text-xs text-[#ECEFF4] transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? 'animate-spin text-[#F0A43A]' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Summary KPI Strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
        <div className="p-3 bg-[#14171D] border border-[#303640] rounded">
          <div className="text-[10px] text-[#9DA7B5] uppercase">Total Executions</div>
          <div className="text-lg font-bold text-[#ECEFF4] mt-0.5">{totalCount}</div>
          <div className="text-[10px] text-[#48B9D0] mt-0.5">Recorded spans</div>
        </div>
        <div className="p-3 bg-[#14171D] border border-[#303640] rounded">
          <div className="text-[10px] text-[#9DA7B5] uppercase">Avg Pipeline Latency</div>
          <div className="text-lg font-bold text-[#F0A43A] mt-0.5">{avgDuration} ms</div>
          <div className="text-[10px] text-[#9DA7B5] mt-0.5">End-to-end roundtrip</div>
        </div>
        <div className="p-3 bg-[#14171D] border border-[#303640] rounded">
          <div className="text-[10px] text-[#9DA7B5] uppercase">Success Rate</div>
          <div className="text-lg font-bold text-[#43B581] mt-0.5">{successRate}%</div>
          <div className="text-[10px] text-[#43B581] mt-0.5">{successCount} successful operations</div>
        </div>
        <div className="p-3 bg-[#14171D] border border-[#303640] rounded">
          <div className="text-[10px] text-[#9DA7B5] uppercase">Governance Interceptions</div>
          <div className="text-lg font-bold text-[#EBB346] mt-0.5">{blockedCount}</div>
          <div className="text-[10px] text-[#9DA7B5] mt-0.5">Halted by Policy Engine</div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 bg-[#14171D] p-3 border border-[#303640] rounded text-xs">
        <div className="relative flex-1 max-w-md">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-[#9DA7B5]" />
          <input
            type="text"
            placeholder="Search by Trace ID, tool, server, or query..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-[#181C23] border border-[#303640] rounded pl-8 pr-3 py-1.5 text-xs text-[#ECEFF4] focus:outline-none focus:border-[#F0A43A]"
          />
        </div>

        <div className="flex items-center space-x-1 bg-[#101216] p-1 border border-[#303640] rounded text-xs">
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
              <th className="py-2.5 px-3">Target Server</th>
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
            ) : filteredTraces.length === 0 ? (
              <tr>
                <td colSpan={8} className="py-8 text-center text-[#626D7C]">
                  No execution traces matching current filters.
                </td>
              </tr>
            ) : (
              filteredTraces.map((t) => (
                <tr
                  key={t.id}
                  className="hover:bg-[#181C23]/60 cursor-pointer transition-colors"
                  onClick={() => {
                    setSelectedTraceId(t.id);
                    setSelectedSpanIdx(0);
                  }}
                >
                  <td className="py-2.5 px-3 font-bold text-[#48B9D0]">{t.trace_id}</td>
                  <td className="py-2.5 px-3 font-semibold text-[#ECEFF4] max-w-xs truncate">{t.tool_name}</td>
                  <td className="py-2.5 px-3 text-[#9DA7B5]">{t.server_name || 'Multi-Server'}</td>
                  <td className="py-2.5 px-3">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        t.status === 'SUCCESS'
                          ? 'bg-[#43B581]/15 text-[#43B581] border border-[#43B581]/30'
                          : t.status === 'BLOCKED'
                          ? 'bg-[#EBB346]/15 text-[#EBB346] border border-[#EBB346]/30'
                          : 'bg-[#E05252]/15 text-[#E05252] border border-[#E05252]/30'
                      }`}
                    >
                      {t.status}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-[#ECEFF4]">{t.duration_ms} ms</td>
                  <td className="py-2.5 px-3">
                    <span
                      className={`text-[10px] ${
                        t.risk_level === 'CRITICAL' || t.risk_level === 'HIGH' ? 'text-[#E05252]' : 'text-[#43B581]'
                      }`}
                    >
                      {t.risk_level}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-[#626D7C] whitespace-nowrap">
                    {new Date(t.created_at).toLocaleTimeString()}
                  </td>
                  <td className="py-2.5 px-3 text-right">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedTraceId(t.id);
                        setSelectedSpanIdx(0);
                      }}
                      className="px-2.5 py-1 bg-[#181C23] hover:bg-[#303640] border border-[#303640] rounded text-[10px] text-[#F0A43A] font-semibold transition-colors"
                    >
                      Inspect Waterfall
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* WATERFALL TRACE DETAIL MODAL / INSPECTOR */}
      {selectedTraceId && (
        <div className="fixed inset-0 bg-black/85 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#14171D] border border-[#303640] rounded-lg max-w-5xl w-full max-h-[92vh] flex flex-col font-mono shadow-2xl overflow-hidden">
            {/* Modal Header */}
            <div className="p-4 border-b border-[#303640] flex items-center justify-between bg-[#181C23]">
              <div className="flex items-center gap-3">
                <Activity className="w-5 h-5 text-[#F0A43A]" />
                <div>
                  <h3 className="text-sm font-bold text-[#ECEFF4] flex items-center gap-2">
                    Execution Trace: {selectedTrace?.trace_id}
                    <span
                      className={`text-[10px] px-2 py-0.5 rounded font-bold ${
                        selectedTrace?.status === 'SUCCESS'
                          ? 'bg-[#43B581]/15 text-[#43B581] border border-[#43B581]/30'
                          : selectedTrace?.status === 'BLOCKED'
                          ? 'bg-[#EBB346]/15 text-[#EBB346] border border-[#EBB346]/30'
                          : 'bg-[#E05252]/15 text-[#E05252] border border-[#E05252]/30'
                      }`}
                    >
                      {selectedTrace?.status}
                    </span>
                  </h3>
                  <div className="text-[10px] text-[#9DA7B5] mt-0.5">
                    Request ID: {selectedTrace?.request_id} • Server: {selectedTrace?.server_name} • Duration: {selectedTrace?.duration_ms} ms
                  </div>
                </div>
              </div>
              <button
                onClick={() => {
                  setSelectedTraceId(null);
                  setSelectedSpanIdx(null);
                }}
                className="p-1 hover:bg-[#303640] text-[#9DA7B5] hover:text-[#ECEFF4] rounded transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto space-y-6">
              {/* Pipeline Gates Visualization */}
              <div>
                <div className="text-[11px] font-bold text-[#9DA7B5] uppercase mb-2">
                  Pipeline Execution Gates (Full Lifecycle)
                </div>
                <div className="grid grid-cols-2 md:grid-cols-6 gap-2">
                  {stagesList.map((st, i) => {
                    const Icon = st.icon;
                    return (
                      <div key={st.key} className="p-2.5 bg-[#101216] border border-[#303640] rounded flex flex-col items-center text-center space-y-1">
                        <Icon className="w-4 h-4 text-[#F0A43A]" />
                        <span className="text-[9px] font-bold text-[#ECEFF4] leading-tight">
                          {st.label}
                        </span>
                        <span className="text-[8px] text-[#48B9D0]">GATE {i + 1}</span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Waterfall Gantt Chart */}
              {selectedTrace?.spans && selectedTrace.spans.length > 0 && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-bold text-[#9DA7B5] uppercase">
                      Waterfall Gantt Timeline ({selectedTrace.spans.length} Spans)
                    </span>
                    <span className="text-[10px] text-[#626D7C]">
                      Click any span to inspect payload details
                    </span>
                  </div>

                  <div className="bg-[#101216] border border-[#303640] rounded p-4 space-y-2">
                    {selectedTrace.spans.map((span, idx) => {
                      const totalDur = Math.max(selectedTrace.duration_ms, 1.0);
                      const spanDur = Math.max(span.duration_ms, 0.5);
                      const widthPct = Math.min(100, Math.max(4, Math.round((spanDur / totalDur) * 100)));
                      const isSelected = selectedSpanIdx === idx;

                      const barColor =
                        span.status === 'FAILED'
                          ? 'bg-[#E05252]'
                          : span.status === 'BLOCKED'
                          ? 'bg-[#EBB346]'
                          : span.stage === 'TOOL_EXECUTION'
                          ? 'bg-[#43B581]'
                          : span.stage === 'MCP_SERVER'
                          ? 'bg-[#48B9D0]'
                          : 'bg-[#F0A43A]';

                      return (
                        <div
                          key={idx}
                          onClick={() => setSelectedSpanIdx(idx)}
                          className={`p-2 rounded cursor-pointer transition-colors border ${
                            isSelected
                              ? 'bg-[#181C23] border-[#F0A43A]'
                              : 'bg-[#14171D] border-[#303640] hover:border-[#626D7C]'
                          }`}
                        >
                          <div className="flex items-center justify-between text-[11px] mb-1">
                            <div className="flex items-center gap-2">
                              <span className="text-[#626D7C] text-[10px]">#{idx + 1}</span>
                              <span className="font-bold text-[#ECEFF4]">{span.name}</span>
                              <span className="text-[10px] px-1.5 py-0.2 rounded bg-[#181C23] text-[#9DA7B5] border border-[#303640]">
                                {span.stage}
                              </span>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="text-[#9DA7B5]">{span.duration_ms} ms</span>
                              <span
                                className={`text-[9px] px-1.5 py-0.2 rounded font-bold ${
                                  span.status === 'COMPLETED'
                                    ? 'text-[#43B581]'
                                    : span.status === 'BLOCKED'
                                    ? 'text-[#EBB346]'
                                    : 'text-[#E05252]'
                                }`}
                              >
                                {span.status}
                              </span>
                            </div>
                          </div>

                          {/* Relative Horizontal Bar */}
                          <div className="w-full bg-[#181C23] h-2 rounded overflow-hidden">
                            <div
                              className={`h-full rounded ${barColor}`}
                              style={{ width: `${widthPct}%` }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Span Inspector Panel */}
              {activeSpan && (
                <div className="space-y-2 p-4 bg-[#101216] border border-[#303640] rounded">
                  <div className="flex items-center justify-between border-b border-[#303640] pb-2">
                    <div className="flex items-center gap-2">
                      <Terminal className="w-4 h-4 text-[#F0A43A]" />
                      <span className="text-xs font-bold text-[#ECEFF4]">
                        Span Inspector: {activeSpan.name}
                      </span>
                    </div>
                    <button
                      onClick={() =>
                        copyToClipboard(JSON.stringify(activeSpan, null, 2), 'span_details')
                      }
                      className="flex items-center gap-1 text-[10px] text-[#9DA7B5] hover:text-[#ECEFF4]"
                    >
                      {copiedText === 'span_details' ? (
                        <>
                          <Check className="w-3 h-3 text-[#43B581]" />
                          Copied
                        </>
                      ) : (
                        <>
                          <Copy className="w-3 h-3" />
                          Copy JSON
                        </>
                      )}
                    </button>
                  </div>

                  <div className="grid grid-cols-3 gap-2 text-[10px] text-[#9DA7B5] pt-1">
                    <div>Stage: <span className="text-[#ECEFF4] font-bold">{activeSpan.stage}</span></div>
                    <div>Status: <span className="text-[#43B581] font-bold">{activeSpan.status}</span></div>
                    <div>Duration: <span className="text-[#F0A43A] font-bold">{activeSpan.duration_ms} ms</span></div>
                  </div>

                  <pre className="text-[11px] text-[#ECEFF4] bg-[#14171D] p-3 rounded border border-[#303640] overflow-x-auto max-h-56 mt-2">
                    {JSON.stringify(activeSpan.details, null, 2)}
                  </pre>
                </div>
              )}

              {/* Input Parameters & Final Synthesis Output */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                <div>
                  <div className="flex items-center justify-between text-[11px] font-bold text-[#9DA7B5] uppercase mb-1">
                    <span>Input Parameters / Query</span>
                    <button
                      onClick={() =>
                        copyToClipboard(
                          JSON.stringify(selectedTrace?.input_parameters, null, 2),
                          'input_copy'
                        )
                      }
                      className="text-[10px] text-[#626D7C] hover:text-[#ECEFF4] flex items-center gap-1"
                    >
                      {copiedText === 'input_copy' ? <Check className="w-3 h-3 text-[#43B581]" /> : <Copy className="w-3 h-3" />}
                    </button>
                  </div>
                  <pre className="p-3 bg-[#101216] border border-[#303640] rounded text-[11px] text-[#43B581] overflow-x-auto max-h-48">
                    {JSON.stringify(selectedTrace?.input_parameters, null, 2)}
                  </pre>
                </div>

                <div>
                  <div className="flex items-center justify-between text-[11px] font-bold text-[#9DA7B5] uppercase mb-1">
                    <span>Execution Output & Synthesis</span>
                    <button
                      onClick={() =>
                        copyToClipboard(
                          JSON.stringify(selectedTrace?.output_response, null, 2),
                          'output_copy'
                        )
                      }
                      className="text-[10px] text-[#626D7C] hover:text-[#ECEFF4] flex items-center gap-1"
                    >
                      {copiedText === 'output_copy' ? <Check className="w-3 h-3 text-[#43B581]" /> : <Copy className="w-3 h-3" />}
                    </button>
                  </div>
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
