import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../services/api';
import {
  AlertTriangle,
  ShieldAlert,
  Clock,
  Terminal,
  Activity,
  CheckCircle2,
  RefreshCw,
  Power,
  RotateCcw,
  Zap,
  Server,
  Layers,
  ChevronRight
} from 'lucide-react';

export const AlertsIncidents: React.FC = () => {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<'INCIDENTS' | 'SECURITY'>('INCIDENTS');
  const [severityFilter, setSeverityFilter] = useState<string>('ALL');

  const { data: metrics, isLoading: isMetricsLoading } = useQuery({
    queryKey: ['command-center-metrics'],
    queryFn: api.getMetrics,
    refetchInterval: 10000,
  });

  const { data: incidents, isLoading: isIncidentsLoading, refetch: refetchIncidents, isFetching } = useQuery({
    queryKey: ['circuit-incidents'],
    queryFn: api.getIncidents,
    refetchInterval: 6000,
  });

  const { data: servers } = useQuery({
    queryKey: ['mcp-servers'],
    queryFn: () => api.getServers(),
  });

  const resetMutation = useMutation({
    mutationFn: (serverId: string) => api.resetCircuit(serverId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['circuit-incidents'] });
      queryClient.invalidateQueries({ queryKey: ['mcp-servers'] });
      queryClient.invalidateQueries({ queryKey: ['command-center-metrics'] });
    },
  });

  const filteredIncidents = (incidents || []).filter((inc: any) => {
    if (severityFilter !== 'ALL' && inc.severity !== severityFilter) return false;
    return true;
  });

  const filteredSecurityEvents = (metrics?.security_events || []).filter((evt) => {
    if (severityFilter !== 'ALL' && evt.severity !== severityFilter) return false;
    return true;
  });

  return (
    <div className="space-y-6 font-mono">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between border-b border-[#303640] pb-4 gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-[#ECEFF4]">
              INCIDENTS & RESILIENCE RADAR
            </h1>
            <span className="text-[11px] px-2 py-0.5 rounded bg-[#E05252]/15 text-[#E05252] border border-[#E05252]/30">
              SELF-HEALING CONTROL PLANE
            </span>
          </div>
          <p className="text-xs text-[#9DA7B5] mt-1 font-sans">
            Real-time infrastructure resilience telemetry, circuit breaker trip states, automatic failovers, and governance security alarms.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => refetchIncidents()}
            disabled={isFetching}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#181C23] hover:bg-[#303640] border border-[#303640] rounded text-xs text-[#ECEFF4] transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? 'animate-spin text-[#F0A43A]' : ''}`} />
            Refresh Telemetry
          </button>
        </div>
      </div>

      {/* Circuit Breaker Status Banner across active servers */}
      <div className="p-4 bg-[#14171D] border border-[#303640] rounded space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs font-bold text-[#ECEFF4]">
            <Zap className="w-4 h-4 text-[#F0A43A]" />
            ACTIVE CIRCUIT BREAKER STATES & SUBPROCESS HEALTH
          </div>
          <span className="text-[10px] text-[#9DA7B5]">Threshold: 3 Consecutive Failures</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {(servers || []).map((srv) => {
            const isUnhealthy = srv.status === 'UNHEALTHY' || srv.status === 'ERROR' || srv.error_rate > 0.3;
            return (
              <div
                key={srv.id}
                className="p-3 bg-[#101216] border border-[#303640] rounded flex items-center justify-between text-xs"
              >
                <div>
                  <div className="font-bold text-[#ECEFF4] text-xs">{srv.name}</div>
                  <div className="text-[10px] text-[#9DA7B5] mt-0.5">
                    Transport: {srv.transport_type} • Calls: {srv.total_calls}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                      isUnhealthy
                        ? 'bg-[#E05252]/15 text-[#E05252] border-[#E05252]/30'
                        : 'bg-[#43B581]/15 text-[#43B581] border-[#43B581]/30'
                    }`}
                  >
                    {isUnhealthy ? 'CIRCUIT OPEN' : 'CLOSED (HEALTHY)'}
                  </span>
                  {isUnhealthy && (
                    <button
                      onClick={() => resetMutation.mutate(srv.id)}
                      disabled={resetMutation.isPending}
                      className="px-2 py-0.5 bg-[#F0A43A] hover:bg-[#d89332] text-[#101216] font-bold text-[10px] rounded transition-colors"
                    >
                      Reset
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Tabs & Filter Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-[#14171D] p-3 border border-[#303640] rounded text-xs">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveTab('INCIDENTS')}
            className={`px-3 py-1.5 rounded transition-colors text-xs font-bold ${
              activeTab === 'INCIDENTS'
                ? 'bg-[#181C23] text-[#F0A43A] border border-[#F0A43A]/30'
                : 'text-[#9DA7B5] hover:text-[#ECEFF4]'
            }`}
          >
            Infrastructure Incidents ({(incidents || []).length})
          </button>
          <button
            onClick={() => setActiveTab('SECURITY')}
            className={`px-3 py-1.5 rounded transition-colors text-xs font-bold ${
              activeTab === 'SECURITY'
                ? 'bg-[#181C23] text-[#48B9D0] border border-[#48B9D0]/30'
                : 'text-[#9DA7B5] hover:text-[#ECEFF4]'
            }`}
          >
            Security & Telemetry Alarms ({(metrics?.security_events || []).length})
          </button>
        </div>

        <div className="flex items-center gap-1.5">
          <span className="text-[#9DA7B5] text-[11px]">Severity:</span>
          {(['ALL', 'CRITICAL', 'HIGH', 'MEDIUM'] as const).map((sev) => (
            <button
              key={sev}
              onClick={() => setSeverityFilter(sev)}
              className={`px-2.5 py-1 rounded text-[11px] transition-colors ${
                severityFilter === sev
                  ? 'bg-[#181C23] text-[#ECEFF4] font-bold border border-[#303640]'
                  : 'text-[#9DA7B5] hover:text-[#ECEFF4]'
              }`}
            >
              {sev}
            </button>
          ))}
        </div>
      </div>

      {/* Tab 1: Infrastructure Incidents */}
      {activeTab === 'INCIDENTS' && (
        <div className="space-y-3">
          {isIncidentsLoading ? (
            <div className="text-center py-8 text-xs text-[#9DA7B5]">
              Loading infrastructure incidents...
            </div>
          ) : filteredIncidents.length === 0 ? (
            <div className="text-center py-12 text-xs text-[#626D7C] bg-[#14171D] border border-[#303640] rounded">
              No active or historical incidents recorded.
            </div>
          ) : (
            filteredIncidents.map((inc: any) => (
              <div
                key={inc.id}
                className="p-5 bg-[#14171D] border border-[#303640] rounded space-y-3"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-[#F0A43A] font-bold">{inc.id}</span>
                      <span className="text-sm font-bold text-[#ECEFF4]">{inc.title}</span>
                    </div>
                    <div className="text-[11px] text-[#48B9D0] mt-0.5">
                      Target Server: {inc.server_name} • Detected: {new Date(inc.timestamp).toLocaleString()}
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <span
                      className={`text-[10px] px-2 py-0.5 rounded font-bold border ${
                        inc.severity === 'CRITICAL'
                          ? 'bg-[#E05252]/15 text-[#E05252] border-[#E05252]/30'
                          : 'bg-[#F0A43A]/15 text-[#F0A43A] border-[#F0A43A]/30'
                      }`}
                    >
                      {inc.severity}
                    </span>
                    <span
                      className={`text-[10px] px-2 py-0.5 rounded font-bold border ${
                        inc.status === 'ACTIVE'
                          ? 'bg-[#E05252]/15 text-[#E05252] border-[#E05252]/30'
                          : inc.status === 'MITIGATED'
                          ? 'bg-[#F0A43A]/15 text-[#F0A43A] border-[#F0A43A]/30'
                          : 'bg-[#43B581]/15 text-[#43B581] border-[#43B581]/30'
                      }`}
                    >
                      {inc.status}
                    </span>
                  </div>
                </div>

                <div className="p-3 bg-[#101216] border border-[#303640] rounded text-xs space-y-1.5">
                  <div className="text-[#9DA7B5]">
                    <span className="text-[#ECEFF4] font-semibold">Root Cause: </span>
                    {inc.root_cause}
                  </div>
                  <div className="text-[#9DA7B5]">
                    <span className="text-[#43B581] font-semibold">Self-Healing Mitigation: </span>
                    {inc.actions_taken}
                  </div>
                </div>

                <div className="pt-2 border-t border-[#303640] flex items-center justify-between text-[11px] text-[#626D7C]">
                  <div>
                    {inc.resolved_at ? (
                      <span className="text-[#43B581]">
                        Resolved at: {new Date(inc.resolved_at).toLocaleString()}
                      </span>
                    ) : (
                      <span className="text-[#E05252]">Active Mitigation in Progress</span>
                    )}
                  </div>

                  {inc.status === 'ACTIVE' && (
                    <button
                      onClick={() => resetMutation.mutate(inc.server_id)}
                      disabled={resetMutation.isPending}
                      className="flex items-center gap-1.5 px-3 py-1 bg-[#F0A43A] hover:bg-[#d89332] text-[#101216] font-bold text-xs rounded transition-colors"
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                      Reset Circuit & Restore Server
                    </button>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Tab 2: Security & Telemetry Alarms */}
      {activeTab === 'SECURITY' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredSecurityEvents.length === 0 ? (
            <div className="col-span-2 text-center py-12 text-xs text-[#626D7C] bg-[#14171D] border border-[#303640] rounded">
              No security events matching current severity filter.
            </div>
          ) : (
            filteredSecurityEvents.map((evt) => (
              <div
                key={evt.id}
                className="p-4 bg-[#14171D] border border-[#303640] rounded space-y-2"
              >
                <div className="flex items-center justify-between">
                  <span
                    className={`text-[10px] px-2 py-0.5 rounded font-bold ${
                      evt.severity === 'CRITICAL' || evt.severity === 'HIGH'
                        ? 'bg-[#E05252]/15 text-[#E05252] border border-[#E05252]/30'
                        : 'bg-[#EBB346]/15 text-[#EBB346] border border-[#EBB346]/30'
                    }`}
                  >
                    {evt.severity} SEVERITY
                  </span>
                  <span className="text-[10px] text-[#626D7C]">{evt.timestamp}</span>
                </div>

                <div className="text-xs font-bold text-[#ECEFF4]">{evt.type}</div>
                <p className="text-xs text-[#9DA7B5] font-sans">{evt.description}</p>

                <div className="pt-2 border-t border-[#303640] flex items-center justify-between text-[10px] text-[#626D7C]">
                  <span>Actor: {evt.actor}</span>
                  <span>Target: {evt.resource}</span>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
};
