import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../services/api';
import type { SecurityPolicy } from '../../types';
import {
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  Plus,
  Trash2,
  Edit2,
  X,
  Filter,
  CheckCircle,
  XCircle,
  HelpCircle,
  Lock,
  Globe,
  Server,
  Wrench
} from 'lucide-react';

export const SecurityPolicies: React.FC = () => {
  const queryClient = useQueryClient();
  const [envFilter, setEnvFilter] = useState<string>('ALL');
  const [actionFilter, setActionFilter] = useState<string>('ALL');

  // Modals
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [editingPolicy, setEditingPolicy] = useState<SecurityPolicy | null>(null);

  // Form states
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [action, setAction] = useState<'ALLOW' | 'DENY' | 'REQUIRE_APPROVAL'>('REQUIRE_APPROVAL');
  const [riskLevel, setRiskLevel] = useState<'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' | 'ANY'>('HIGH');
  const [environment, setEnvironment] = useState<'ALL' | 'PRODUCTION' | 'STAGING' | 'DEVELOPMENT'>('ALL');
  const [scope, setScope] = useState<'GLOBAL' | 'SERVER' | 'TOOL'>('TOOL');
  const [toolPattern, setToolPattern] = useState('');
  const [isEnabled, setIsEnabled] = useState(true);

  const { data: policies, isLoading } = useQuery({
    queryKey: ['security-policies'],
    queryFn: () => api.getPolicies(),
  });

  const createMutation = useMutation({
    mutationFn: (data: Partial<SecurityPolicy>) => api.createPolicy(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['security-policies'] });
      setIsCreateModalOpen(false);
      resetForm();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<SecurityPolicy> }) =>
      api.updatePolicy(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['security-policies'] });
      setEditingPolicy(null);
      resetForm();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deletePolicy(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['security-policies'] });
    },
  });

  const resetForm = () => {
    setName('');
    setDescription('');
    setAction('REQUIRE_APPROVAL');
    setRiskLevel('HIGH');
    setEnvironment('ALL');
    setScope('TOOL');
    setToolPattern('');
    setIsEnabled(true);
  };

  const handleOpenEdit = (p: SecurityPolicy) => {
    setEditingPolicy(p);
    setName(p.name);
    setDescription(p.description || '');
    setAction(p.action);
    setRiskLevel(p.risk_level);
    setEnvironment(p.environment);
    setScope(p.scope);
    setToolPattern(p.tool_pattern || '');
    setIsEnabled(p.is_enabled);
  };

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    const payload = {
      name,
      description,
      action,
      risk_level: riskLevel,
      environment,
      scope,
      tool_pattern: toolPattern || undefined,
      is_enabled: isEnabled,
    };

    if (editingPolicy) {
      updateMutation.mutate({ id: editingPolicy.id, data: payload });
    } else {
      createMutation.mutate(payload);
    }
  };

  const filteredPolicies = (policies || []).filter((p) => {
    if (envFilter !== 'ALL' && p.environment !== envFilter && p.environment !== 'ALL') return false;
    if (actionFilter !== 'ALL' && p.action !== actionFilter) return false;
    return true;
  });

  const getActionBadge = (act: string) => {
    switch (act) {
      case 'ALLOW':
        return (
          <span className="text-[10px] px-2 py-0.5 rounded font-bold bg-[#43B581]/15 text-[#43B581] border border-[#43B581]/30">
            ALLOW
          </span>
        );
      case 'DENY':
        return (
          <span className="text-[10px] px-2 py-0.5 rounded font-bold bg-[#E05252]/15 text-[#E05252] border border-[#E05252]/30">
            DENY
          </span>
        );
      case 'REQUIRE_APPROVAL':
        return (
          <span className="text-[10px] px-2 py-0.5 rounded font-bold bg-[#F0A43A]/15 text-[#F0A43A] border border-[#F0A43A]/30">
            REQUIRE APPROVAL
          </span>
        );
      default:
        return null;
    }
  };

  const getRiskBadge = (risk: string) => {
    const colors: Record<string, string> = {
      CRITICAL: 'text-[#E05252] border-[#E05252]/30 bg-[#E05252]/10',
      HIGH: 'text-[#F0A43A] border-[#F0A43A]/30 bg-[#F0A43A]/10',
      MEDIUM: 'text-[#48B9D0] border-[#48B9D0]/30 bg-[#48B9D0]/10',
      LOW: 'text-[#9DA7B5] border-[#9DA7B5]/30 bg-[#9DA7B5]/10',
      ANY: 'text-[#ECEFF4] border-[#ECEFF4]/30 bg-[#ECEFF4]/10',
    };
    return (
      <span className={`text-[10px] px-1.5 py-0.5 rounded border ${colors[risk] || colors.LOW}`}>
        {risk}
      </span>
    );
  };

  return (
    <div className="space-y-6 font-mono">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between border-b border-[#303640] pb-4 gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-[#ECEFF4]">
              SECURITY POLICIES & CONSTRAINTS
            </h1>
            <span className="text-[11px] px-2 py-0.5 rounded bg-[#43B581]/15 text-[#43B581] border border-[#43B581]/30">
              POLICY INTELLIGENCE ENGINE
            </span>
          </div>
          <p className="text-xs text-[#9DA7B5] mt-1 font-sans">
            Declarative governance rules evaluated synchronously before any MCP tool invocation across environments.
          </p>
        </div>

        <button
          onClick={() => {
            resetForm();
            setIsCreateModalOpen(true);
          }}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-[#F0A43A] hover:bg-[#d89332] text-[#101216] text-xs font-bold rounded transition-colors self-start md:self-auto"
        >
          <Plus className="w-3.5 h-3.5" />
          Create Policy Rule
        </button>
      </div>

      {/* Filter bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-[#14171D] p-3 border border-[#303640] rounded text-xs">
        <div className="flex items-center gap-2">
          <Filter className="w-3.5 h-3.5 text-[#9DA7B5]" />
          <span className="text-[#9DA7B5]">Environment:</span>
          {(['ALL', 'PRODUCTION', 'STAGING', 'DEVELOPMENT'] as const).map((env) => (
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

        <div className="flex items-center gap-2">
          <span className="text-[#9DA7B5]">Action:</span>
          {(['ALL', 'REQUIRE_APPROVAL', 'DENY', 'ALLOW'] as const).map((act) => (
            <button
              key={act}
              onClick={() => setActionFilter(act)}
              className={`px-2.5 py-1 rounded text-[11px] transition-colors ${
                actionFilter === act
                  ? 'bg-[#181C23] text-[#48B9D0] font-bold border border-[#48B9D0]/30'
                  : 'text-[#9DA7B5] hover:text-[#ECEFF4]'
              }`}
            >
              {act === 'REQUIRE_APPROVAL' ? 'APPROVAL' : act}
            </button>
          ))}
        </div>
      </div>

      {/* Policies Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {isLoading ? (
          <div className="col-span-2 text-center text-xs text-[#9DA7B5] py-8">
            Loading governance policies...
          </div>
        ) : filteredPolicies.length === 0 ? (
          <div className="col-span-2 text-center text-xs text-[#9DA7B5] py-12 bg-[#14171D] border border-[#303640] rounded">
            No policies matching current filters.
          </div>
        ) : (
          filteredPolicies.map((pol) => (
            <div
              key={pol.id}
              className={`p-5 bg-[#14171D] border rounded space-y-3 transition-colors ${
                pol.is_enabled ? 'border-[#303640]' : 'border-[#303640]/50 opacity-60'
              }`}
            >
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-[#F0A43A] font-bold">{pol.id}</span>
                    <span className="text-xs font-bold text-[#ECEFF4]">{pol.name}</span>
                  </div>
                  <div className="flex items-center gap-2 text-[10px] text-[#48B9D0] mt-1">
                    <span className="flex items-center gap-1">
                      {pol.scope === 'GLOBAL' && <Globe className="w-3 h-3" />}
                      {pol.scope === 'SERVER' && <Server className="w-3 h-3" />}
                      {pol.scope === 'TOOL' && <Wrench className="w-3 h-3" />}
                      Scope: {pol.scope}
                    </span>
                    <span>•</span>
                    <span>Env: {pol.environment}</span>
                    {pol.tool_pattern && (
                      <>
                        <span>•</span>
                        <span>Pattern: {pol.tool_pattern}</span>
                      </>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {getRiskBadge(pol.risk_level)}
                  {getActionBadge(pol.action)}
                </div>
              </div>

              <p className="text-xs text-[#9DA7B5] font-sans leading-relaxed">
                {pol.description || 'No description provided.'}
              </p>

              {pol.argument_conditions && Object.keys(pol.argument_conditions).length > 0 && (
                <div className="p-2 bg-[#181C23] border border-[#303640] rounded text-[11px] text-[#9DA7B5]">
                  <span className="text-[#ECEFF4] font-semibold">Conditions: </span>
                  {JSON.stringify(pol.argument_conditions)}
                </div>
              )}

              <div className="pt-2 border-t border-[#303640] flex items-center justify-between text-[11px]">
                <div className="flex items-center gap-2">
                  <button
                    onClick={() =>
                      updateMutation.mutate({
                        id: pol.id,
                        data: { is_enabled: !pol.is_enabled },
                      })
                    }
                    className={`px-2 py-0.5 rounded text-[10px] font-bold border transition-colors ${
                      pol.is_enabled
                        ? 'bg-[#43B581]/15 text-[#43B581] border-[#43B581]/30 hover:bg-[#43B581]/25'
                        : 'bg-[#9DA7B5]/15 text-[#9DA7B5] border-[#9DA7B5]/30 hover:bg-[#9DA7B5]/25'
                    }`}
                  >
                    {pol.is_enabled ? 'STATUS: ENFORCING' : 'STATUS: DISABLED'}
                  </button>
                </div>

                <div className="flex items-center gap-1">
                  <button
                    onClick={() => handleOpenEdit(pol)}
                    className="p-1.5 hover:bg-[#181C23] text-[#9DA7B5] hover:text-[#ECEFF4] rounded transition-colors"
                    title="Edit Policy"
                  >
                    <Edit2 className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => {
                      if (confirm(`Delete policy ${pol.id} (${pol.name})?`)) {
                        deleteMutation.mutate(pol.id);
                      }
                    }}
                    className="p-1.5 hover:bg-[#181C23] text-[#9DA7B5] hover:text-[#E05252] rounded transition-colors"
                    title="Delete Policy"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Create / Edit Modal */}
      {(isCreateModalOpen || editingPolicy) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-[#14171D] border border-[#303640] rounded w-full max-w-lg p-6 space-y-4 shadow-xl">
            <div className="flex items-center justify-between border-b border-[#303640] pb-3">
              <h2 className="text-sm font-bold text-[#ECEFF4]">
                {editingPolicy ? `Edit Policy Rule: ${editingPolicy.id}` : 'Create Security Policy Rule'}
              </h2>
              <button
                onClick={() => {
                  setIsCreateModalOpen(false);
                  setEditingPolicy(null);
                  resetForm();
                }}
                className="text-[#9DA7B5] hover:text-[#ECEFF4]"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleSave} className="space-y-3 text-xs">
              <div>
                <label className="block text-[#9DA7B5] mb-1 font-semibold">Policy Name</label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Production Equipment Maintenance Gate"
                  className="w-full bg-[#181C23] border border-[#303640] rounded px-3 py-2 text-[#ECEFF4] focus:outline-none focus:border-[#F0A43A]"
                />
              </div>

              <div>
                <label className="block text-[#9DA7B5] mb-1 font-semibold">Description</label>
                <textarea
                  rows={2}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Explain the security constraint and governance rationale..."
                  className="w-full bg-[#181C23] border border-[#303640] rounded px-3 py-2 text-[#ECEFF4] focus:outline-none focus:border-[#F0A43A]"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[#9DA7B5] mb-1 font-semibold">Governance Action</label>
                  <select
                    value={action}
                    onChange={(e) => setAction(e.target.value as any)}
                    className="w-full bg-[#181C23] border border-[#303640] rounded px-3 py-2 text-[#ECEFF4] focus:outline-none focus:border-[#F0A43A]"
                  >
                    <option value="REQUIRE_APPROVAL">REQUIRE_APPROVAL</option>
                    <option value="DENY">DENY (Hard Block)</option>
                    <option value="ALLOW">ALLOW (Explicit Permit)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-[#9DA7B5] mb-1 font-semibold">Risk Classification</label>
                  <select
                    value={riskLevel}
                    onChange={(e) => setRiskLevel(e.target.value as any)}
                    className="w-full bg-[#181C23] border border-[#303640] rounded px-3 py-2 text-[#ECEFF4] focus:outline-none focus:border-[#F0A43A]"
                  >
                    <option value="LOW">LOW</option>
                    <option value="MEDIUM">MEDIUM</option>
                    <option value="HIGH">HIGH</option>
                    <option value="CRITICAL">CRITICAL</option>
                    <option value="ANY">ANY</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[#9DA7B5] mb-1 font-semibold">Environment Scope</label>
                  <select
                    value={environment}
                    onChange={(e) => setEnvironment(e.target.value as any)}
                    className="w-full bg-[#181C23] border border-[#303640] rounded px-3 py-2 text-[#ECEFF4] focus:outline-none focus:border-[#F0A43A]"
                  >
                    <option value="ALL">ALL (Global)</option>
                    <option value="PRODUCTION">PRODUCTION</option>
                    <option value="STAGING">STAGING</option>
                    <option value="DEVELOPMENT">DEVELOPMENT</option>
                  </select>
                </div>

                <div>
                  <label className="block text-[#9DA7B5] mb-1 font-semibold">Evaluation Target Scope</label>
                  <select
                    value={scope}
                    onChange={(e) => setScope(e.target.value as any)}
                    className="w-full bg-[#181C23] border border-[#303640] rounded px-3 py-2 text-[#ECEFF4] focus:outline-none focus:border-[#F0A43A]"
                  >
                    <option value="TOOL">TOOL (Pattern Match)</option>
                    <option value="SERVER">SERVER (Server Match)</option>
                    <option value="GLOBAL">GLOBAL (All Invocations)</option>
                  </select>
                </div>
              </div>

              {scope === 'TOOL' && (
                <div>
                  <label className="block text-[#9DA7B5] mb-1 font-semibold">
                    Tool Pattern (Wildcard supported)
                  </label>
                  <input
                    type="text"
                    value={toolPattern}
                    onChange={(e) => setToolPattern(e.target.value)}
                    placeholder="e.g. report_* or *delete* or get_project_*"
                    className="w-full bg-[#181C23] border border-[#303640] rounded px-3 py-2 text-[#ECEFF4] focus:outline-none focus:border-[#F0A43A]"
                  />
                </div>
              )}

              <div className="flex items-center gap-2 pt-2">
                <input
                  type="checkbox"
                  id="pol_enabled"
                  checked={isEnabled}
                  onChange={(e) => setIsEnabled(e.target.checked)}
                  className="rounded border-[#303640] text-[#F0A43A] focus:ring-0"
                />
                <label htmlFor="pol_enabled" className="text-[#ECEFF4] cursor-pointer">
                  Enable policy immediately upon saving
                </label>
              </div>

              <div className="flex items-center justify-end gap-2 pt-4 border-t border-[#303640]">
                <button
                  type="button"
                  onClick={() => {
                    setIsCreateModalOpen(false);
                    setEditingPolicy(null);
                    resetForm();
                  }}
                  className="px-3 py-1.5 bg-[#181C23] hover:bg-[#1e232c] text-[#ECEFF4] rounded transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending || updateMutation.isPending}
                  className="px-4 py-1.5 bg-[#F0A43A] hover:bg-[#d89332] text-[#101216] font-bold rounded transition-colors"
                >
                  {editingPolicy ? 'Save Changes' : 'Create Policy'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
