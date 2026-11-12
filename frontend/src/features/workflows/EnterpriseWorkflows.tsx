import React, { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { api } from '../../services/api';
import {
  GitMerge,
  Server,
  Wrench,
  Bot,
  Activity,
  CheckCircle,
  AlertTriangle,
  Play,
  Layers,
  ArrowRight,
  TrendingDown,
  Building,
  HardHat,
  Package,
  Download,
  Copy,
  Check,
  RefreshCw
} from 'lucide-react';

interface Scenario {
  id: string;
  title: string;
  category: string;
  description: string;
  query: string;
  serversInvolved: string[];
}

export const EnterpriseWorkflows: React.FC = () => {
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>('SCN-01');
  const [customPrompt, setCustomPrompt] = useState<string>('');
  const [executionResult, setExecutionResult] = useState<any>(null);
  const [isExecuting, setIsExecuting] = useState(false);
  const [copied, setCopied] = useState(false);

  const { data: agents } = useQuery({
    queryKey: ['ai-agents'],
    queryFn: () => api.getAgents(),
  });

  const primaryAgent = (agents || []).find((a) => a.identifier === 'atlas-orchestrator') || (agents || [])[0];

  const scenarios: Scenario[] = [
    {
      id: 'SCN-01',
      title: 'Multi-Domain Civil Project Bottleneck Correlation',
      category: 'Cross-Server Root Cause Correlation',
      description: 'Correlates Hazira LNG Expansion capex and milestone delays with overdue crawler crane maintenance and out-of-stock SS316 cryogenic flanges.',
      query: 'Identify delayed projects across Hazira LNG expansion with crane maintenance alerts and flange stock deficits.',
      serversInvolved: ['ERP MCP Server', 'Equipment MCP Server', 'Inventory MCP Server'],
    },
    {
      id: 'SCN-02',
      title: 'Critical Machinery Telemetry & Preventative Maintenance Gate',
      category: 'Asset Fleet Health & Telemetry',
      description: 'Queries Liebherr crane fleet sensor data for vibration threshold breaches and correlates with spare parts availability.',
      query: 'Retrieve telemetry alarms for Crawler Crane EQP-CRN-8800 and verify overdue overhaul schedules.',
      serversInvolved: ['Equipment MCP Server'],
    },
    {
      id: 'SCN-03',
      title: 'Warehouse Safety Stock Deficit & Procurement Lead Time',
      category: 'Supply Chain & Inventory',
      description: 'Audits safety stock deficits across high-pressure fittings and structural rebar to prevent civil erection halts.',
      query: 'Identify critical low-stock items with safety stock deficit and lead times exceeding 20 days.',
      serversInvolved: ['Inventory MCP Server'],
    },
  ];

  const activeScenario = scenarios.find((s) => s.id === selectedScenarioId) || scenarios[0];

  const handleExecuteWorkflow = async () => {
    if (!primaryAgent) return;
    setIsExecuting(true);
    setExecutionResult(null);

    const promptToSend = customPrompt.trim() || activeScenario.query;
    try {
      const res = await api.orchestrateAgent(primaryAgent.id, promptToSend);
      setExecutionResult(res);
    } catch (err: any) {
      setExecutionResult({
        overall_status: 'FAILED',
        synthesis: `Workflow execution failed: ${err.message || 'Network error'}`,
        tool_executions: [],
        spans: [],
      });
    } finally {
      setIsExecuting(false);
    }
  };

  const copySynthesis = () => {
    if (executionResult?.synthesis) {
      navigator.clipboard.writeText(executionResult.synthesis);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="space-y-6 font-mono">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between border-b border-[#303640] pb-4 gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-[#ECEFF4]">
              ENTERPRISE WORKFLOW INTELLIGENCE
            </h1>
            <span className="text-[11px] px-2 py-0.5 rounded bg-[#F0A43A]/15 text-[#F0A43A] border border-[#F0A43A]/30 font-bold">
              CROSS-SERVER CORRELATION WORKSPACE
            </span>
          </div>
          <p className="text-xs text-[#9DA7B5] mt-1 font-sans">
            Demonstrates autonomous multi-protocol MCP orchestration correlating ERP milestone progress, equipment fleet telemetry, and warehouse inventory.
          </p>
        </div>

        <button
          onClick={handleExecuteWorkflow}
          disabled={isExecuting || !primaryAgent}
          className="flex items-center gap-2 px-4 py-2 bg-[#F0A43A] hover:bg-[#d89332] text-[#101216] text-xs font-bold rounded transition-colors self-start md:self-auto shadow-md"
        >
          {isExecuting ? (
            <>
              <RefreshCw className="w-4 h-4 animate-spin" />
              Dispatching MCP Protocol Calls...
            </>
          ) : (
            <>
              <Play className="w-4 h-4 fill-current" />
              Execute Workflow Correlation
            </>
          )}
        </button>
      </div>

      {/* Scenario Selector Strip */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {scenarios.map((sc) => {
          const isSelected = sc.id === selectedScenarioId;
          return (
            <div
              key={sc.id}
              onClick={() => {
                setSelectedScenarioId(sc.id);
                setCustomPrompt('');
                setExecutionResult(null);
              }}
              className={`p-4 rounded border cursor-pointer transition-all ${
                isSelected
                  ? 'bg-[#181C23] border-[#F0A43A] shadow-lg ring-1 ring-[#F0A43A]/20'
                  : 'bg-[#14171D] border-[#303640] hover:border-[#626D7C]'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] text-[#F0A43A] font-bold">{sc.id}</span>
                <span className="text-[9px] px-1.5 py-0.2 rounded bg-[#101216] border border-[#303640] text-[#9DA7B5]">
                  {sc.category}
                </span>
              </div>
              <div className="text-xs font-bold text-[#ECEFF4] mt-1">{sc.title}</div>
              <p className="text-[11px] text-[#9DA7B5] font-sans mt-1 line-clamp-2">
                {sc.description}
              </p>
              <div className="flex flex-wrap gap-1 mt-3 pt-2 border-t border-[#303640]">
                {sc.serversInvolved.map((srv) => (
                  <span
                    key={srv}
                    className="text-[9px] px-1.5 py-0.5 rounded bg-[#101216] text-[#48B9D0] border border-[#48B9D0]/30"
                  >
                    {srv.split(' ')[0]}
                  </span>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {/* Workflow Topology Architecture Diagram */}
      <div className="p-4 bg-[#14171D] border border-[#303640] rounded space-y-3">
        <div className="flex items-center justify-between text-xs">
          <span className="font-bold text-[#ECEFF4] flex items-center gap-2">
            <GitMerge className="w-4 h-4 text-[#48B9D0]" />
            CONCURRENT MULTI-PROTOCOL PIPELINE TOPOLOGY
          </span>
          <span className="text-[10px] text-[#9DA7B5]">
            Target Agent: <strong className="text-[#F0A43A]">{primaryAgent?.name || 'Atlas'}</strong>
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs pt-1">
          {/* Agent Node */}
          <div className="p-3 bg-[#101216] border border-[#303640] rounded flex flex-col justify-between">
            <div className="flex items-center gap-2 text-[#F0A43A]">
              <Bot className="w-4 h-4" />
              <span className="font-bold">Autonomous Agent</span>
            </div>
            <div className="text-[10px] text-[#9DA7B5] mt-2">
              Atlas Orchestrator
              <div className="text-[#ECEFF4] mt-0.5">Model: {primaryAgent?.model || 'claude-3-5-sonnet'}</div>
            </div>
            <div className="mt-2 text-[9px] text-[#43B581] font-bold">DISPATCHER ACTIVE</div>
          </div>

          {/* Server 1: ERP */}
          <div className="p-3 bg-[#101216] border border-[#303640] rounded flex flex-col justify-between">
            <div className="flex items-center gap-2 text-[#48B9D0]">
              <Building className="w-4 h-4" />
              <span className="font-bold">ERP MCP Server</span>
            </div>
            <div className="text-[10px] text-[#9DA7B5] mt-2">
              Protocol: STDIO
              <div className="text-[#ECEFF4] mt-0.5">get_project_status</div>
            </div>
            <div className="mt-2 text-[9px] text-[#48B9D0]">SAP S/4HANA BRIDGE</div>
          </div>

          {/* Server 2: Equipment */}
          <div className="p-3 bg-[#101216] border border-[#303640] rounded flex flex-col justify-between">
            <div className="flex items-center gap-2 text-[#E05252]">
              <HardHat className="w-4 h-4" />
              <span className="font-bold">Equipment Server</span>
            </div>
            <div className="text-[10px] text-[#9DA7B5] mt-2">
              Protocol: STDIO
              <div className="text-[#ECEFF4] mt-0.5">get_maintenance_schedule</div>
            </div>
            <div className="mt-2 text-[9px] text-[#E05252]">VIBRATION TELEMETRY</div>
          </div>

          {/* Server 3: Inventory */}
          <div className="p-3 bg-[#101216] border border-[#303640] rounded flex flex-col justify-between">
            <div className="flex items-center gap-2 text-[#43B581]">
              <Package className="w-4 h-4" />
              <span className="font-bold">Inventory Server</span>
            </div>
            <div className="text-[10px] text-[#9DA7B5] mt-2">
              Protocol: STDIO
              <div className="text-[#ECEFF4] mt-0.5">get_low_stock_items</div>
            </div>
            <div className="mt-2 text-[9px] text-[#43B581]">SAFETY STOCK RADAR</div>
          </div>
        </div>
      </div>

      {/* Query Execution Box */}
      <div className="p-4 bg-[#14171D] border border-[#303640] rounded space-y-2 text-xs">
        <label className="block text-[#9DA7B5] font-semibold">
          Active Natural-Language Prompt (Editable):
        </label>
        <div className="flex gap-2">
          <input
            type="text"
            value={customPrompt || activeScenario.query}
            onChange={(e) => setCustomPrompt(e.target.value)}
            className="flex-1 bg-[#181C23] border border-[#303640] rounded px-3 py-2 text-xs text-[#ECEFF4] focus:outline-none focus:border-[#F0A43A]"
          />
          <button
            onClick={handleExecuteWorkflow}
            disabled={isExecuting}
            className="px-4 py-2 bg-[#F0A43A] hover:bg-[#d89332] text-[#101216] font-bold rounded transition-colors whitespace-nowrap"
          >
            {isExecuting ? 'Running...' : 'Run Analysis'}
          </button>
        </div>
      </div>

      {/* Structured Executive Correlation Report */}
      {executionResult && (
        <div className="space-y-4">
          <div className="flex items-center justify-between border-b border-[#303640] pb-2">
            <div className="flex items-center gap-2 text-sm font-bold text-[#ECEFF4]">
              <CheckCircle className="w-4 h-4 text-[#43B581]" />
              EXECUTIVE CROSS-SERVER CORRELATION DOSSIER
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={copySynthesis}
                className="flex items-center gap-1 px-2.5 py-1 bg-[#181C23] hover:bg-[#303640] border border-[#303640] rounded text-[11px] text-[#ECEFF4] transition-colors"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-[#43B581]" /> : <Copy className="w-3.5 h-3.5" />}
                {copied ? 'Copied' : 'Copy Synthesis'}
              </button>
            </div>
          </div>

          {/* 3 Domain Telemetry Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
            {/* Card 1: ERP Status */}
            <div className="p-4 bg-[#14171D] border border-[#303640] rounded space-y-2">
              <div className="flex items-center justify-between text-[#48B9D0] font-bold">
                <span className="flex items-center gap-1.5">
                  <Building className="w-4 h-4" />
                  ERP Civil Project Milestone
                </span>
                <span className="text-[10px] px-1.5 py-0.2 rounded bg-[#48B9D0]/15 border border-[#48B9D0]/30">
                  SAP BRIDGE
                </span>
              </div>
              <div className="text-sm font-bold text-[#ECEFF4]">PRJ-HAZ-002</div>
              <div className="text-[11px] text-[#9DA7B5]">Hazira LNG Expansion Package 2</div>
              <div className="pt-2 border-t border-[#303640] space-y-1 text-[11px]">
                <div className="flex justify-between text-[#9DA7B5]">
                  <span>Status:</span>
                  <span className="text-[#E05252] font-bold">DELAYED (CRITICAL)</span>
                </div>
                <div className="flex justify-between text-[#9DA7B5]">
                  <span>Completion:</span>
                  <span className="text-[#ECEFF4]">48.5%</span>
                </div>
                <div className="flex justify-between text-[#9DA7B5]">
                  <span>Capex Incurred:</span>
                  <span className="text-[#ECEFF4]">₹3,150 Cr / ₹4,200 Cr</span>
                </div>
              </div>
            </div>

            {/* Card 2: Equipment Fleet */}
            <div className="p-4 bg-[#14171D] border border-[#303640] rounded space-y-2">
              <div className="flex items-center justify-between text-[#E05252] font-bold">
                <span className="flex items-center gap-1.5">
                  <HardHat className="w-4 h-4" />
                  Heavy Machinery Health
                </span>
                <span className="text-[10px] px-1.5 py-0.2 rounded bg-[#E05252]/15 border border-[#E05252]/30">
                  ALARM ACTIVE
                </span>
              </div>
              <div className="text-sm font-bold text-[#ECEFF4]">EQP-CRN-8800</div>
              <div className="text-[11px] text-[#9DA7B5]">Liebherr LR 11000 (1000t Crawler)</div>
              <div className="pt-2 border-t border-[#303640] space-y-1 text-[11px]">
                <div className="flex justify-between text-[#9DA7B5]">
                  <span>Maintenance Schedule:</span>
                  <span className="text-[#E05252] font-bold">42 DAYS OVERDUE</span>
                </div>
                <div className="flex justify-between text-[#9DA7B5]">
                  <span>Vibration Sensor:</span>
                  <span className="text-[#E05252] font-bold">6.8 mm/s (Limit: 3.5)</span>
                </div>
                <div className="flex justify-between text-[#9DA7B5]">
                  <span>Operational Status:</span>
                  <span className="text-[#ECEFF4]">Halted for Safety Overhaul</span>
                </div>
              </div>
            </div>

            {/* Card 3: Inventory Deficit */}
            <div className="p-4 bg-[#14171D] border border-[#303640] rounded space-y-2">
              <div className="flex items-center justify-between text-[#43B581] font-bold">
                <span className="flex items-center gap-1.5">
                  <Package className="w-4 h-4" />
                  Warehouse Stock Shortage
                </span>
                <span className="text-[10px] px-1.5 py-0.2 rounded bg-[#43B581]/15 border border-[#43B581]/30">
                  ZERO STOCK
                </span>
              </div>
              <div className="text-sm font-bold text-[#ECEFF4]">MAT-FLG-SS316</div>
              <div className="text-[11px] text-[#9DA7B5]">Cryogenic Flange 600# (SS316)</div>
              <div className="pt-2 border-t border-[#303640] space-y-1 text-[11px]">
                <div className="flex justify-between text-[#9DA7B5]">
                  <span>Stock on Hand:</span>
                  <span className="text-[#E05252] font-bold">0 Units Available</span>
                </div>
                <div className="flex justify-between text-[#9DA7B5]">
                  <span>Safety Stock Deficit:</span>
                  <span className="text-[#E05252] font-bold">-40 Units</span>
                </div>
                <div className="flex justify-between text-[#9DA7B5]">
                  <span>Procurement Lead Time:</span>
                  <span className="text-[#ECEFF4]">28 Days (Domestic Supplier)</span>
                </div>
              </div>
            </div>
          </div>

          {/* Consolidated Executive Synthesis Dossier */}
          <div className="p-5 bg-[#14171D] border border-[#F0A43A]/40 rounded space-y-3">
            <div className="flex items-center justify-between">
              <div className="text-xs font-bold text-[#F0A43A] flex items-center gap-2">
                <Activity className="w-4 h-4" />
                CONSOLIDATED EXECUTIVE ROOT-CAUSE SYNTHESIS
              </div>
              <span className="text-[10px] px-2 py-0.5 rounded bg-[#43B581]/15 text-[#43B581] border border-[#43B581]/30 font-bold">
                TRIPLE-SERVER CORRELATION COMPLETE
              </span>
            </div>

            <div className="text-xs text-[#ECEFF4] font-sans whitespace-pre-line leading-relaxed bg-[#101216] p-4 rounded border border-[#303640]">
              {executionResult.synthesis}
            </div>

            <div className="grid grid-cols-2 gap-4 text-xs pt-2">
              <div className="p-3 bg-[#181C23] border border-[#303640] rounded">
                <span className="font-bold text-[#ECEFF4] block mb-1">Recommended Remediation Action:</span>
                <p className="text-[11px] text-[#9DA7B5] font-sans">
                  1. Issue emergency preventative overhaul work order for Crawler Crane EQP-CRN-8800 to prevent catastrophic slewing ring seizure.
                  <br />
                  2. Initiate expedited emergency air-freight procurement for 40 units of MAT-FLG-SS316 cryogenic flanges to resume Jetty 3 erection.
                </p>
              </div>

              <div className="p-3 bg-[#181C23] border border-[#303640] rounded">
                <span className="font-bold text-[#ECEFF4] block mb-1">Execution Telemetry Metadata:</span>
                <div className="text-[10px] text-[#9DA7B5] space-y-0.5">
                  <div>Trace ID: <strong className="text-[#48B9D0]">{executionResult.trace_id}</strong></div>
                  <div>Execution Duration: <strong className="text-[#F0A43A]">{executionResult.duration_ms} ms</strong></div>
                  <div>Tools Invoked: <strong className="text-[#ECEFF4]">{executionResult.tool_executions?.length || 0} Tools across 3 Servers</strong></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
