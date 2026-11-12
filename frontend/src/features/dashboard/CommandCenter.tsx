import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../services/api';
import {
  Server,
  Activity,
  Bot,
  CheckCircle,
  AlertOctagon,
  Clock,
  ShieldAlert,
  ArrowUpRight,
  TrendingUp,
  Cpu,
  Layers,
  Zap,
  Terminal,
  ShieldCheck
} from 'lucide-react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell
} from 'recharts';
import { Link } from 'react-router-dom';

export const CommandCenter: React.FC = () => {
  const { data: metrics, isLoading, refetch } = useQuery({
    queryKey: ['command-center-metrics'],
    queryFn: api.getMetrics,
    refetchInterval: 10000,
  });

  if (isLoading || !metrics) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-20 bg-[#181C23] border border-[#303640] rounded"></div>
        <div className="grid grid-cols-6 gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-24 bg-[#181C23] border border-[#303640] rounded"></div>
          ))}
        </div>
        <div className="grid grid-cols-12 gap-6">
          <div className="col-span-8 h-80 bg-[#181C23] border border-[#303640] rounded"></div>
          <div className="col-span-4 h-80 bg-[#181C23] border border-[#303640] rounded"></div>
        </div>
      </div>
    );
  }

  const { top_metrics, infra_health, activity_chart, server_distribution, recent_executions, security_events, system_timeline } = metrics;

  return (
    <div className="space-y-6">
      {/* Platform Title Banner */}
      <div className="flex items-center justify-between border-b border-[#303640] pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-[#ECEFF4] font-mono">
              ENTERPRISE COMMAND CENTER
            </h1>
            <span className="text-[11px] px-2 py-0.5 rounded bg-[#F0A43A]/15 text-[#F0A43A] font-mono border border-[#F0A43A]/30">
              INDUSTRIAL CONTROL PLANE
            </span>
          </div>
          <p className="text-xs text-[#9DA7B5] mt-1">
            Real-time telemetry, model context protocol execution orchestration, and defense-in-depth policy governance.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            to="/agents"
            className="flex items-center gap-2 px-3 py-1.5 bg-[#F0A43A] hover:bg-[#F0A43A]/90 text-[#101216] font-semibold rounded text-xs transition-colors"
          >
            <Bot className="w-3.5 h-3.5" />
            Launch AI Orchestrator
          </Link>
          <Link
            to="/tools"
            className="flex items-center gap-2 px-3 py-1.5 bg-[#181C23] hover:bg-[#1F242D] border border-[#303640] text-[#ECEFF4] rounded text-xs transition-colors font-mono"
          >
            <Terminal className="w-3.5 h-3.5 text-[#48B9D0]" />
            Tool Playground
          </Link>
        </div>
      </div>

      {/* TOP METRICS (12-col grid) */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {/* Metric 1 */}
        <div className="bg-[#14171D] border border-[#303640] p-3 rounded flex flex-col justify-between">
          <div className="flex items-center justify-between text-[#9DA7B5]">
            <span className="text-[10px] font-mono uppercase tracking-wider">Registered Servers</span>
            <Server className="w-4 h-4 text-[#48B9D0]" />
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-2xl font-bold font-mono text-[#ECEFF4]">{top_metrics.registered_servers}</span>
            <span className="text-[10px] text-[#43B581] font-mono">100% Configured</span>
          </div>
        </div>

        {/* Metric 2 */}
        <div className="bg-[#14171D] border border-[#303640] p-3 rounded flex flex-col justify-between">
          <div className="flex items-center justify-between text-[#9DA7B5]">
            <span className="text-[10px] font-mono uppercase tracking-wider">Active MCP Servers</span>
            <CheckCircle className="w-4 h-4 text-[#43B581]" />
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-2xl font-bold font-mono text-[#43B581]">{top_metrics.active_servers}</span>
            <span className="text-[10px] text-[#9DA7B5] font-mono">Live STDIO</span>
          </div>
        </div>

        {/* Metric 3 */}
        <div className="bg-[#14171D] border border-[#303640] p-3 rounded flex flex-col justify-between">
          <div className="flex items-center justify-between text-[#9DA7B5]">
            <span className="text-[10px] font-mono uppercase tracking-wider">Connected Agents</span>
            <Bot className="w-4 h-4 text-[#F0A43A]" />
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-2xl font-bold font-mono text-[#ECEFF4]">{top_metrics.connected_agents}</span>
            <span className="text-[10px] text-[#F0A43A] font-mono">Atlas & Aegis</span>
          </div>
        </div>

        {/* Metric 4 */}
        <div className="bg-[#14171D] border border-[#303640] p-3 rounded flex flex-col justify-between">
          <div className="flex items-center justify-between text-[#9DA7B5]">
            <span className="text-[10px] font-mono uppercase tracking-wider">Total Executions</span>
            <Activity className="w-4 h-4 text-[#48B9D0]" />
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-2xl font-bold font-mono text-[#ECEFF4]">{top_metrics.total_executions}</span>
            <span className="text-[10px] text-[#43B581] font-mono">{top_metrics.success_rate_pct}% Pass</span>
          </div>
        </div>

        {/* Metric 5 */}
        <div className="bg-[#14171D] border border-[#303640] p-3 rounded flex flex-col justify-between">
          <div className="flex items-center justify-between text-[#9DA7B5]">
            <span className="text-[10px] font-mono uppercase tracking-wider">Failed Executions</span>
            <AlertOctagon className="w-4 h-4 text-[#E05252]" />
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-2xl font-bold font-mono text-[#E05252]">{top_metrics.failed_executions}</span>
            <span className="text-[10px] text-[#626D7C] font-mono">Blocked / Policy</span>
          </div>
        </div>

        {/* Metric 6 */}
        <Link
          to="/governance/approvals"
          className={`border p-3 rounded flex flex-col justify-between transition-colors ${
            top_metrics.pending_approvals > 0
              ? 'bg-[#181C23] border-[#E05252]/60 hover:border-[#E05252]'
              : 'bg-[#14171D] border-[#303640] hover:border-[#F0A43A]/40'
          }`}
        >
          <div className="flex items-center justify-between text-[#9DA7B5]">
            <span className="text-[10px] font-mono uppercase tracking-wider">Pending Approvals</span>
            <Clock className={`w-4 h-4 ${top_metrics.pending_approvals > 0 ? 'text-[#E05252]' : 'text-[#9DA7B5]'}`} />
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <span className={`text-2xl font-bold font-mono ${top_metrics.pending_approvals > 0 ? 'text-[#E05252]' : 'text-[#ECEFF4]'}`}>
              {top_metrics.pending_approvals}
            </span>
            <span className="text-[10px] text-[#F0A43A] font-mono flex items-center">
              Review Queue <ArrowUpRight className="w-3 h-3 ml-0.5" />
            </span>
          </div>
        </Link>
      </div>

      {/* CHARTS ROW (12-column layout: 8 cols activity, 4 cols distribution) */}
      <div className="grid grid-cols-12 gap-6">
        {/* Execution Activity Over Time (8 cols) */}
        <div className="col-span-12 lg:col-span-8 bg-[#14171D] border border-[#303640] rounded p-4">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-xs font-bold font-mono uppercase text-[#ECEFF4] tracking-wider flex items-center gap-2">
                <TrendingUp className="w-3.5 h-3.5 text-[#F0A43A]" />
                MCP Protocol Execution Activity (24H Aggregate)
              </h2>
              <p className="text-[11px] text-[#9DA7B5] mt-0.5">
                Hourly throughput across registered ERP, Inventory, and Equipment tools.
              </p>
            </div>
            <div className="flex items-center gap-3 text-[11px] font-mono">
              <span className="flex items-center gap-1.5 text-[#48B9D0]">
                <span className="w-2 h-2 rounded-full bg-[#48B9D0]"></span> Executions
              </span>
              <span className="flex items-center gap-1.5 text-[#E05252]">
                <span className="w-2 h-2 rounded-full bg-[#E05252]"></span> Errors / Blocked
              </span>
            </div>
          </div>

          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={activity_chart}>
                <defs>
                  <linearGradient id="colorExec" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#48B9D0" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#48B9D0" stopOpacity={0.0} />
                  </linearGradient>
                  <linearGradient id="colorErr" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#E05252" stopOpacity={0.5} />
                    <stop offset="95%" stopColor="#E05252" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="time" stroke="#626D7C" fontSize={10} fontStyle="JetBrains Mono" />
                <YAxis stroke="#626D7C" fontSize={10} fontStyle="JetBrains Mono" />
                <Tooltip
                  contentStyle={{ backgroundColor: '#181C23', borderColor: '#303640', fontSize: '11px', color: '#ECEFF4', fontFamily: 'JetBrains Mono' }}
                />
                <Area type="monotone" dataKey="executions" stroke="#48B9D0" strokeWidth={2} fillOpacity={1} fill="url(#colorExec)" />
                <Area type="monotone" dataKey="errors" stroke="#E05252" strokeWidth={2} fillOpacity={1} fill="url(#colorErr)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Server Distribution (4 cols) */}
        <div className="col-span-12 lg:col-span-4 bg-[#14171D] border border-[#303640] rounded p-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-xs font-bold font-mono uppercase text-[#ECEFF4] tracking-wider flex items-center gap-2">
                <Cpu className="w-3.5 h-3.5 text-[#43B581]" />
                Server Health Distribution
              </h2>
            </div>
            <p className="text-[11px] text-[#9DA7B5]">
              Real-time JSON-RPC connection states across all deployment environments.
            </p>
          </div>

          <div className="h-44 my-auto flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={server_distribution}
                  cx="50%"
                  cy="50%"
                  innerRadius={45}
                  outerRadius={70}
                  paddingAngle={4}
                  dataKey="count"
                >
                  {server_distribution.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ backgroundColor: '#181C23', borderColor: '#303640', fontSize: '11px', color: '#ECEFF4', fontFamily: 'JetBrains Mono' }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>

          <div className="pt-3 border-t border-[#303640] grid grid-cols-3 gap-2 text-center">
            {server_distribution.map((item) => (
              <div key={item.name} className="p-1.5 bg-[#181C23] border border-[#303640] rounded">
                <div className="text-[10px] text-[#9DA7B5] font-mono">{item.name}</div>
                <div className="text-sm font-bold font-mono" style={{ color: item.color }}>
                  {item.count}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* A. INFRASTRUCTURE HEALTH OVERVIEW */}
      <div className="bg-[#14171D] border border-[#303640] rounded p-4">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="text-xs font-bold font-mono uppercase text-[#ECEFF4] tracking-wider flex items-center gap-2">
              <Server className="w-3.5 h-3.5 text-[#48B9D0]" />
              Infrastructure Health Overview
            </h2>
            <p className="text-[11px] text-[#9DA7B5] mt-0.5">
              Protocol transport health, average response latencies, and active tool bindings.
            </p>
          </div>
          <Link
            to="/servers"
            className="text-xs text-[#F0A43A] hover:underline font-mono flex items-center gap-1"
          >
            Manage Servers <ArrowUpRight className="w-3 h-3" />
          </Link>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-[#181C23] text-[#9DA7B5] border-b border-[#303640]">
              <tr>
                <th className="py-2 px-3">Server Name</th>
                <th className="py-2 px-3">Identifier</th>
                <th className="py-2 px-3">Transport</th>
                <th className="py-2 px-3">Environment</th>
                <th className="py-2 px-3">Status</th>
                <th className="py-2 px-3">Avg Latency</th>
                <th className="py-2 px-3">Error Rate</th>
                <th className="py-2 px-3">Total Dispatches</th>
                <th className="py-2 px-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#303640]/60">
              {infra_health.map((server) => (
                <tr key={server.id} className="hover:bg-[#181C23]/40 transition-colors">
                  <td className="py-2.5 px-3 font-semibold text-[#ECEFF4] flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${server.status === 'HEALTHY' ? 'bg-[#43B581]' : 'bg-[#EBB346]'}`} />
                    {server.name}
                  </td>
                  <td className="py-2.5 px-3 text-[#9DA7B5]">{server.identifier}</td>
                  <td className="py-2.5 px-3">
                    <span className="px-1.5 py-0.5 bg-[#181C23] border border-[#303640] rounded text-[10px] text-[#48B9D0]">
                      {server.transport}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-[#ECEFF4]">{server.environment}</td>
                  <td className="py-2.5 px-3">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      server.status === 'HEALTHY'
                        ? 'bg-[#43B581]/15 text-[#43B581] border border-[#43B581]/30'
                        : 'bg-[#EBB346]/15 text-[#EBB346] border border-[#EBB346]/30'
                    }`}>
                      {server.status}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-[#ECEFF4]">{server.avg_response_time_ms} ms</td>
                  <td className="py-2.5 px-3 text-[#9DA7B5]">{server.error_rate}%</td>
                  <td className="py-2.5 px-3 text-[#ECEFF4]">{server.total_calls}</td>
                  <td className="py-2.5 px-3 text-right">
                    <Link
                      to={`/servers`}
                      className="px-2 py-1 bg-[#181C23] hover:bg-[#303640] border border-[#303640] rounded text-[10px] text-[#ECEFF4]"
                    >
                      Inspect
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* LOWER SECTION: 3 Columns (Recent Executions, Security Events, Activity Timeline) */}
      <div className="grid grid-cols-12 gap-6">
        {/* D. Recent Executions (5 cols) */}
        <div className="col-span-12 lg:col-span-5 bg-[#14171D] border border-[#303640] rounded p-4">
          <div className="flex items-center justify-between mb-3 border-b border-[#303640] pb-2">
            <h3 className="text-xs font-bold font-mono uppercase text-[#ECEFF4] tracking-wider flex items-center gap-2">
              <Activity className="w-3.5 h-3.5 text-[#F0A43A]" />
              Recent Tool Executions
            </h3>
            <Link to="/observability/traces" className="text-[11px] text-[#F0A43A] hover:underline font-mono">
              View All
            </Link>
          </div>
          <div className="space-y-2">
            {recent_executions.length === 0 ? (
              <div className="text-xs text-[#626D7C] py-4 text-center font-mono">
                No executions recorded yet. Run a query in Agent Orchestrator or Tool Playground.
              </div>
            ) : (
              recent_executions.map((ex) => (
                <div
                  key={ex.id}
                  className="p-2.5 bg-[#181C23] border border-[#303640] rounded flex items-center justify-between text-xs font-mono"
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-[#ECEFF4]">{ex.tool_executed}</span>
                      <span className={`text-[9px] px-1.5 py-0.2 rounded font-bold ${
                        ex.status === 'SUCCESS' ? 'text-[#43B581] bg-[#43B581]/15' : 'text-[#E05252] bg-[#E05252]/15'
                      }`}>
                        {ex.status}
                      </span>
                    </div>
                    <div className="text-[10px] text-[#9DA7B5] mt-1">
                      {ex.mcp_server} • {ex.duration_ms}ms
                    </div>
                  </div>
                  <div className="text-right">
                    <span className="text-[10px] text-[#626D7C]">{ex.timestamp}</span>
                    <div className="text-[10px] text-[#F0A43A] font-semibold">{ex.risk_level} Risk</div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* E. Security Events (4 cols) */}
        <div className="col-span-12 lg:col-span-4 bg-[#14171D] border border-[#303640] rounded p-4">
          <div className="flex items-center justify-between mb-3 border-b border-[#303640] pb-2">
            <h3 className="text-xs font-bold font-mono uppercase text-[#ECEFF4] tracking-wider flex items-center gap-2">
              <ShieldAlert className="w-3.5 h-3.5 text-[#E05252]" />
              Security & Policy Events
            </h3>
            <Link to="/governance/policies" className="text-[11px] text-[#F0A43A] hover:underline font-mono">
              Policies
            </Link>
          </div>
          <div className="space-y-2">
            {security_events.map((se) => (
              <div
                key={se.id}
                className="p-2.5 bg-[#181C23] border border-[#303640] rounded text-xs font-mono space-y-1"
              >
                <div className="flex items-center justify-between">
                  <span className="text-[#E05252] font-bold text-[10px]">{se.type}</span>
                  <span className="text-[10px] text-[#626D7C]">{se.timestamp}</span>
                </div>
                <div className="text-[#ECEFF4] text-[11px]">{se.description}</div>
                <div className="text-[10px] text-[#9DA7B5]">Actor: {se.actor}</div>
              </div>
            ))}
          </div>
        </div>

        {/* F. System Activity Timeline (3 cols) */}
        <div className="col-span-12 lg:col-span-3 bg-[#14171D] border border-[#303640] rounded p-4">
          <div className="flex items-center justify-between mb-3 border-b border-[#303640] pb-2">
            <h3 className="text-xs font-bold font-mono uppercase text-[#ECEFF4] tracking-wider flex items-center gap-2">
              <Terminal className="w-3.5 h-3.5 text-[#48B9D0]" />
              Audit Stream
            </h3>
            <Link to="/governance/audit-logs" className="text-[11px] text-[#F0A43A] hover:underline font-mono">
              Logs
            </Link>
          </div>
          <div className="space-y-2">
            {system_timeline.slice(0, 5).map((log) => (
              <div key={log.id} className="p-2 bg-[#181C23] border border-[#303640] rounded text-[11px] font-mono">
                <div className="flex items-center justify-between text-[#F0A43A] font-bold text-[10px]">
                  <span>{log.action}</span>
                  <span className="text-[#626D7C] font-normal">{log.timestamp.split(' ')[1]}</span>
                </div>
                <div className="text-[#9DA7B5] truncate mt-0.5">{log.details}</div>
                <div className="text-[9px] text-[#626D7C] mt-0.5">By: {log.user} ({log.role})</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
