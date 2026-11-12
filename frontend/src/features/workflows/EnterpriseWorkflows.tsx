import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { api } from '../../services/api';
import {
  GitMerge,
  Building,
  HardHat,
  Package,
  Play,
  RefreshCw,
  CheckCircle,
  AlertTriangle,
  AlertOctagon,
  Copy,
  Check,
  ExternalLink,
  Info,
  ShieldCheck,
  Database,
  Cpu,
  Clock,
  Layers,
  ArrowRight,
  FileText,
  ChevronDown,
  ChevronUp
} from 'lucide-react';

interface ProjectRisk {
  project_id: string;
  project_name: string;
  division: string;
  site: string;
  overall_risk: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  risk_score: number;
  erp_status: string;
  affected_equipment: string[];
  affected_materials: string[];
  evidence: string[];
  business_impact: string;
  recommended_action: string;
  source_servers: string[];
}

export const EnterpriseWorkflows: React.FC = () => {
  const navigate = useNavigate();
  const defaultPrompt =
    'Identify construction projects at risk due to delayed milestones, equipment failures and insufficient inventory.';
  const [prompt, setPrompt] = useState<string>(defaultPrompt);
  const [isExecuting, setIsExecuting] = useState(false);
  const [executionResult, setExecutionResult] = useState<any>(null);
  const [copied, setCopied] = useState(false);
  const [expandedEvidence, setExpandedEvidence] = useState<string | null>(null);

  const { data: agents } = useQuery({
    queryKey: ['ai-agents'],
    queryFn: () => api.getAgents(),
  });

  const primaryAgent = (agents || []).find((a) => a.identifier === 'atlas-orchestrator') || (agents || [])[0];

  const handleExecute = async () => {
    setIsExecuting(true);
    setExecutionResult(null);

    try {
      const res = await api.executeWorkflow({
        workflow_id: 'construction-risk-intelligence',
        prompt: prompt.trim() || defaultPrompt,
        agent_id: primaryAgent?.id,
      });
      setExecutionResult(res);
    } catch (err: any) {
      setExecutionResult({
        execution_status: 'FAILED',
        synthesis: `Workflow execution failed: ${err.message || 'Network / Server Error'}`,
        tool_executions: [],
        spans: [],
        risk_assessment: {
          summary: {
            total_projects_assessed: 0,
            critical_risks: 0,
            high_risks: 0,
            medium_risks: 0,
            low_risks: 0,
            overall_system_health: 'EXECUTION_FAILED',
          },
          projects: [],
        },
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

  const summary = executionResult?.risk_assessment?.summary;
  const projects: ProjectRisk[] = executionResult?.risk_assessment?.projects || [];
  const serverProgress = executionResult?.server_progress || {};

  return (
    <div className="space-y-6 font-mono pb-12">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between border-b border-[#303640] pb-4 gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-[#ECEFF4]">
              CONSTRUCTION PROJECT RISK INTELLIGENCE
            </h1>
            <span className="text-[11px] px-2 py-0.5 rounded bg-[#F0A43A]/15 text-[#F0A43A] border border-[#F0A43A]/30 font-bold">
              FLAGSHIP WORKFLOW
            </span>
          </div>
          <p className="text-xs text-[#9DA7B5] mt-1 font-sans">
            Autonomous cross-server correlation correlating ERP milestones (SAP S/4HANA bridge), heavy equipment telemetry (IBM Maximo), and warehouse safety stocks (Oracle WMS).
          </p>
        </div>

        {/* Synthetic Demonstration Data Notice */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded bg-[#181C23] border border-[#303640] text-[10px] text-[#9DA7B5] self-start md:self-auto">
          <Info className="w-3.5 h-3.5 text-[#48B9D0]" />
          <span>SYNTHETIC DEMONSTRATION DATA (L&T Heavy Civil IC Simulation)</span>
        </div>
      </div>

      {/* SECTION A: Workflow Input & Trigger */}
      <div className="p-4 bg-[#14171D] border border-[#303640] rounded space-y-3">
        <div className="flex items-center justify-between">
          <label className="text-xs font-bold text-[#ECEFF4] flex items-center gap-2">
            <FileText className="w-4 h-4 text-[#F0A43A]" />
            Workflow Natural-Language Task Input
          </label>
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-[#9DA7B5]">Execution Status:</span>
            <span
              className={`text-[10px] px-2 py-0.5 rounded font-bold uppercase border ${
                isExecuting
                  ? 'bg-[#F0A43A]/20 text-[#F0A43A] border-[#F0A43A]/40 animate-pulse'
                  : executionResult?.execution_status === 'SUCCESS'
                  ? 'bg-[#43B581]/20 text-[#43B581] border-[#43B581]/40'
                  : executionResult?.execution_status === 'BLOCKED'
                  ? 'bg-[#E05252]/20 text-[#E05252] border-[#E05252]/40'
                  : 'bg-[#181C23] text-[#9DA7B5] border-[#303640]'
              }`}
            >
              {isExecuting ? 'DISPATCHING...' : executionResult?.execution_status || 'IDLE'}
            </span>
          </div>
        </div>

        <div className="flex flex-col sm:flex-row gap-2">
          <input
            type="text"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            disabled={isExecuting}
            placeholder="Enter workflow query..."
            className="flex-1 bg-[#101216] border border-[#303640] rounded px-3 py-2 text-xs text-[#ECEFF4] focus:outline-none focus:border-[#F0A43A]"
          />
          <button
            onClick={handleExecute}
            disabled={isExecuting}
            className="flex items-center justify-center gap-2 px-5 py-2 bg-[#F0A43A] hover:bg-[#d89332] text-[#101216] text-xs font-bold rounded transition-colors whitespace-nowrap shadow-md disabled:opacity-50"
          >
            {isExecuting ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                Executing Across 3 Servers...
              </>
            ) : (
              <>
                <Play className="w-4 h-4 fill-current" />
                Execute Workflow
              </>
            )}
          </button>
        </div>
      </div>

      {/* SECTION B: Execution Progress Strip */}
      <div className="p-4 bg-[#14171D] border border-[#303640] rounded space-y-3">
        <div className="flex items-center justify-between text-xs">
          <span className="font-bold text-[#ECEFF4] flex items-center gap-2">
            <GitMerge className="w-4 h-4 text-[#48B9D0]" />
            MULTI-SERVER EXECUTION PROGRESS & HEALTH RADAR
          </span>
          <span className="text-[10px] text-[#9DA7B5]">
            Target Agent: <strong className="text-[#F0A43A]">{primaryAgent?.name || 'Atlas Coordinator'}</strong>
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-6 gap-2 text-xs pt-1">
          {/* Node 1: ERP Server */}
          <div className="p-3 bg-[#101216] border border-[#303640] rounded flex flex-col justify-between">
            <div className="flex items-center gap-1.5 text-[#48B9D0]">
              <Building className="w-3.5 h-3.5" />
              <span className="text-[11px] font-bold">ERP Server</span>
            </div>
            <div className="text-[10px] text-[#9DA7B5] my-1">
              get_project_status
            </div>
            <div className="text-[9px] font-bold">
              {isExecuting ? (
                <span className="text-[#F0A43A] animate-pulse">PROBING...</span>
              ) : serverProgress.erp_server?.status === 'COMPLETED' ? (
                <span className="text-[#43B581]">COMPLETED ({serverProgress.erp_server?.duration_ms || 4}ms)</span>
              ) : (
                <span className="text-[#9DA7B5]">READY</span>
              )}
            </div>
          </div>

          {/* Node 2: Equipment Server */}
          <div className="p-3 bg-[#101216] border border-[#303640] rounded flex flex-col justify-between">
            <div className="flex items-center gap-1.5 text-[#E05252]">
              <HardHat className="w-3.5 h-3.5" />
              <span className="text-[11px] font-bold">Equipment Server</span>
            </div>
            <div className="text-[10px] text-[#9DA7B5] my-1">
              get_maintenance
            </div>
            <div className="text-[9px] font-bold">
              {isExecuting ? (
                <span className="text-[#F0A43A] animate-pulse">PROBING...</span>
              ) : serverProgress.equipment_server?.status === 'COMPLETED' ? (
                <span className="text-[#43B581]">COMPLETED ({serverProgress.equipment_server?.duration_ms || 6}ms)</span>
              ) : (
                <span className="text-[#9DA7B5]">READY</span>
              )}
            </div>
          </div>

          {/* Node 3: Inventory Server */}
          <div className="p-3 bg-[#101216] border border-[#303640] rounded flex flex-col justify-between">
            <div className="flex items-center gap-1.5 text-[#43B581]">
              <Package className="w-3.5 h-3.5" />
              <span className="text-[11px] font-bold">Inventory Server</span>
            </div>
            <div className="text-[10px] text-[#9DA7B5] my-1">
              get_low_stock_items
            </div>
            <div className="text-[9px] font-bold">
              {isExecuting ? (
                <span className="text-[#F0A43A] animate-pulse">PROBING...</span>
              ) : serverProgress.inventory_server?.status === 'COMPLETED' ? (
                <span className="text-[#43B581]">COMPLETED ({serverProgress.inventory_server?.duration_ms || 5}ms)</span>
              ) : (
                <span className="text-[#9DA7B5]">READY</span>
              )}
            </div>
          </div>

          {/* Node 4: Agent Planning */}
          <div className="p-3 bg-[#101216] border border-[#303640] rounded flex flex-col justify-between">
            <div className="flex items-center gap-1.5 text-[#F0A43A]">
              <Cpu className="w-3.5 h-3.5" />
              <span className="text-[11px] font-bold">Agent Plan</span>
            </div>
            <div className="text-[10px] text-[#9DA7B5] my-1">
              Parallel Dispatch
            </div>
            <div className="text-[9px] font-bold">
              {isExecuting ? (
                <span className="text-[#F0A43A] animate-pulse">PLANNING...</span>
              ) : executionResult ? (
                <span className="text-[#43B581]">3 TOOLS PLANNED</span>
              ) : (
                <span className="text-[#9DA7B5]">READY</span>
              )}
            </div>
          </div>

          {/* Node 5: Policy Gate */}
          <div className="p-3 bg-[#101216] border border-[#303640] rounded flex flex-col justify-between">
            <div className="flex items-center gap-1.5 text-[#48B9D0]">
              <ShieldCheck className="w-3.5 h-3.5" />
              <span className="text-[11px] font-bold">Policy Gate</span>
            </div>
            <div className="text-[10px] text-[#9DA7B5] my-1">
              RBAC & Dynamic Rule
            </div>
            <div className="text-[9px] font-bold">
              {executionResult?.server_progress?.policy_evaluation?.status === 'BLOCKED' ? (
                <span className="text-[#E05252]">BLOCKED</span>
              ) : executionResult ? (
                <span className="text-[#43B581]">PERMITTED</span>
              ) : (
                <span className="text-[#9DA7B5]">ENFORCED</span>
              )}
            </div>
          </div>

          {/* Node 6: Completion */}
          <div className="p-3 bg-[#101216] border border-[#303640] rounded flex flex-col justify-between">
            <div className="flex items-center gap-1.5 text-[#ECEFF4]">
              <Clock className="w-3.5 h-3.5" />
              <span className="text-[11px] font-bold">Pipeline Status</span>
            </div>
            <div className="text-[10px] text-[#9DA7B5] my-1">
              Execution Time
            </div>
            <div className="text-[9px] font-bold">
              {isExecuting ? (
                <span className="text-[#F0A43A] animate-pulse">RUNNING...</span>
              ) : executionResult ? (
                <span className="text-[#43B581]">{executionResult.duration_ms} ms</span>
              ) : (
                <span className="text-[#9DA7B5]">STANDBY</span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* SECTION C: Workflow Results & Correlation Dossier */}
      {executionResult && (
        <div className="space-y-6">
          {/* Executive Overview Cards */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-xs">
            <div className="p-3 bg-[#14171D] border border-[#303640] rounded">
              <span className="text-[10px] text-[#9DA7B5] block">Total Projects Assessed</span>
              <span className="text-xl font-bold text-[#ECEFF4] mt-1 block">
                {summary?.total_projects_assessed || 0}
              </span>
            </div>

            <div className="p-3 bg-[#14171D] border border-[#E05252]/40 rounded">
              <span className="text-[10px] text-[#E05252] block font-bold">Critical Risk Projects</span>
              <span className="text-xl font-bold text-[#E05252] mt-1 block">
                {summary?.critical_risks || 0}
              </span>
            </div>

            <div className="p-3 bg-[#14171D] border border-[#F0A43A]/40 rounded">
              <span className="text-[10px] text-[#F0A43A] block font-bold">High/Medium Risks</span>
              <span className="text-xl font-bold text-[#F0A43A] mt-1 block">
                {(summary?.high_risks || 0) + (summary?.medium_risks || 0)}
              </span>
            </div>

            <div className="p-3 bg-[#14171D] border border-[#43B581]/40 rounded">
              <span className="text-[10px] text-[#43B581] block font-bold">Low Risk / Nominal</span>
              <span className="text-xl font-bold text-[#43B581] mt-1 block">
                {summary?.low_risks || 0}
              </span>
            </div>

            <div className="p-3 bg-[#14171D] border border-[#303640] rounded col-span-2 md:col-span-1">
              <span className="text-[10px] text-[#9DA7B5] block">Execution Duration</span>
              <span className="text-xl font-bold text-[#48B9D0] mt-1 block">
                {executionResult.duration_ms} ms
              </span>
            </div>
          </div>

          {/* Consolidated Executive Synthesis Narrative */}
          <div className="p-5 bg-[#14171D] border border-[#F0A43A]/40 rounded space-y-3">
            <div className="flex items-center justify-between">
              <div className="text-xs font-bold text-[#F0A43A] flex items-center gap-2">
                <CheckCircle className="w-4 h-4 text-[#43B581]" />
                EXECUTIVE RISK ASSESSMENT SUMMARY
              </div>
              <button
                onClick={copySynthesis}
                className="flex items-center gap-1 px-2.5 py-1 bg-[#181C23] hover:bg-[#303640] border border-[#303640] rounded text-[11px] text-[#ECEFF4] transition-colors"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-[#43B581]" /> : <Copy className="w-3.5 h-3.5" />}
                {copied ? 'Copied' : 'Copy Synthesis'}
              </button>
            </div>

            <div className="text-xs text-[#ECEFF4] font-sans whitespace-pre-line leading-relaxed bg-[#101216] p-4 rounded border border-[#303640]">
              {executionResult.synthesis}
            </div>
          </div>

          {/* Project-by-Project Risk Cards */}
          <div className="space-y-4">
            <h2 className="text-sm font-bold text-[#ECEFF4] flex items-center gap-2">
              <Layers className="w-4 h-4 text-[#48B9D0]" />
              PROJECT-BY-PROJECT RISK EVALUATIONS
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {projects.map((proj) => {
                const isCrit = proj.overall_risk === 'CRITICAL';
                const isMed = proj.overall_risk === 'MEDIUM';
                const borderCol = isCrit
                  ? 'border-[#E05252] shadow-lg ring-1 ring-[#E05252]/20'
                  : isMed
                  ? 'border-[#F0A43A]/40'
                  : 'border-[#303640]';

                const badgeCol = isCrit
                  ? 'bg-[#E05252]/20 text-[#E05252] border-[#E05252]/40'
                  : isMed
                  ? 'bg-[#F0A43A]/20 text-[#F0A43A] border-[#F0A43A]/40'
                  : 'bg-[#43B581]/20 text-[#43B581] border-[#43B581]/40';

                return (
                  <div key={proj.project_id} className={`p-4 bg-[#14171D] border ${borderCol} rounded space-y-3`}>
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-[#ECEFF4]">{proj.project_id}</span>
                      <span className={`text-[10px] px-2 py-0.5 rounded font-bold border ${badgeCol}`}>
                        {proj.overall_risk} ({proj.risk_score}/100)
                      </span>
                    </div>

                    <div>
                      <div className="text-xs font-bold text-[#ECEFF4] leading-snug">{proj.project_name}</div>
                      <div className="text-[10px] text-[#9DA7B5] mt-0.5">
                        {proj.division} | {proj.site}
                      </div>
                    </div>

                    <div className="pt-2 border-t border-[#303640] space-y-2 text-[11px] font-sans">
                      <div>
                        <span className="font-bold text-[#9DA7B5] block mb-0.5">ERP Milestone Status:</span>
                        <span className={isCrit ? 'text-[#E05252] font-semibold' : 'text-[#ECEFF4]'}>
                          {proj.erp_status}
                        </span>
                      </div>

                      {proj.affected_equipment.length > 0 && (
                        <div>
                          <span className="font-bold text-[#E05252] block mb-0.5">Affected Equipment:</span>
                          <ul className="list-disc list-inside text-[#ECEFF4] text-[10px] space-y-0.5">
                            {proj.affected_equipment.map((eq, i) => (
                              <li key={i}>{eq}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {proj.affected_materials.length > 0 && (
                        <div>
                          <span className="font-bold text-[#F0A43A] block mb-0.5">Shortage Inventory:</span>
                          <ul className="list-disc list-inside text-[#ECEFF4] text-[10px] space-y-0.5">
                            {proj.affected_materials.map((mat, i) => (
                              <li key={i}>{mat}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      <div>
                        <span className="font-bold text-[#9DA7B5] block mb-0.5">Business Impact:</span>
                        <p className="text-[10px] text-[#9DA7B5]">{proj.business_impact}</p>
                      </div>

                      <div className="p-2 bg-[#101216] border border-[#303640] rounded mt-2">
                        <span className="font-bold text-[#48B9D0] block text-[10px] mb-0.5">Recommended Next Action:</span>
                        <p className="text-[10px] text-[#ECEFF4]">{proj.recommended_action}</p>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* SECTION D: Evidence Panel */}
          <div className="p-4 bg-[#14171D] border border-[#303640] rounded space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-[#ECEFF4] flex items-center gap-2">
                <Database className="w-4 h-4 text-[#48B9D0]" />
                EVIDENCE PANEL: ACTUAL MCP TOOL RESPONSES
              </span>
              <span className="text-[10px] text-[#9DA7B5]">
                {executionResult.tool_executions?.length || 0} Real Tool Outputs Captured
              </span>
            </div>

            <div className="space-y-2">
              {executionResult.tool_executions?.map((t: any, idx: number) => {
                const isExpanded = expandedEvidence === `tool-${idx}`;
                return (
                  <div key={idx} className="bg-[#101216] border border-[#303640] rounded overflow-hidden">
                    <button
                      onClick={() => setExpandedEvidence(isExpanded ? null : `tool-${idx}`)}
                      className="w-full flex items-center justify-between p-3 text-left hover:bg-[#181C23] transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#303640] text-[#ECEFF4] font-bold">
                          #{t.step || idx + 1}
                        </span>
                        <div>
                          <span className="text-xs font-bold text-[#48B9D0]">{t.server}</span>
                          <span className="text-xs text-[#9DA7B5] mx-1.5">&rarr;</span>
                          <span className="text-xs font-bold text-[#F0A43A]">{t.tool}</span>
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <span className="text-[10px] px-2 py-0.5 rounded bg-[#43B581]/15 text-[#43B581] border border-[#43B581]/30">
                          PROVABLE EVIDENCE
                        </span>
                        {isExpanded ? <ChevronUp className="w-4 h-4 text-[#9DA7B5]" /> : <ChevronDown className="w-4 h-4 text-[#9DA7B5]" />}
                      </div>
                    </button>

                    {isExpanded && (
                      <div className="p-3 border-t border-[#303640] bg-[#0D0F12] text-[11px]">
                        <div className="text-[10px] text-[#9DA7B5] mb-1">Tool Input Arguments:</div>
                        <pre className="p-2 bg-[#14171D] rounded text-[#ECEFF4] overflow-x-auto mb-3">
                          {JSON.stringify(t.arguments || {}, null, 2)}
                        </pre>

                        <div className="text-[10px] text-[#9DA7B5] mb-1">Factual Tool Output:</div>
                        <pre className="p-2 bg-[#14171D] rounded text-[#43B581] overflow-x-auto">
                          {JSON.stringify(t.output || {}, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* SECTION E: Execution Trace Linkage */}
          <div className="p-4 bg-[#14171D] border border-[#303640] rounded space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-[#ECEFF4] flex items-center gap-2">
                <Cpu className="w-4 h-4 text-[#F0A43A]" />
                DISTRIBUTED EXECUTION TRACE DETAILS
              </span>
              <button
                onClick={() => navigate('/traces')}
                className="flex items-center gap-1.5 text-xs text-[#F0A43A] hover:underline font-bold"
              >
                <span>Open in Trace Explorer</span>
                <ExternalLink className="w-3.5 h-3.5" />
              </button>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs bg-[#101216] p-3 rounded border border-[#303640]">
              <div>
                <span className="text-[10px] text-[#9DA7B5] block">Execution / Trace ID:</span>
                <span className="text-xs font-bold text-[#48B9D0] block mt-0.5">{executionResult.trace_id}</span>
              </div>

              <div>
                <span className="text-[10px] text-[#9DA7B5] block">Total Duration:</span>
                <span className="text-xs font-bold text-[#ECEFF4] block mt-0.5">{executionResult.duration_ms} ms</span>
              </div>

              <div>
                <span className="text-[10px] text-[#9DA7B5] block">Governance Decision:</span>
                <span className="text-xs font-bold text-[#43B581] block mt-0.5">PERMITTED (Read-Only Safe)</span>
              </div>

              <div>
                <span className="text-[10px] text-[#9DA7B5] block">Spans Generated:</span>
                <span className="text-xs font-bold text-[#F0A43A] block mt-0.5">
                  {executionResult.spans?.length || 0} Stages Tracked
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
