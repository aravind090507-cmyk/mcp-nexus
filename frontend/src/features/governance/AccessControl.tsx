import React, { useState } from 'react';
import {
  ShieldCheck,
  Check,
  X,
  User,
  Lock,
  Sliders,
  ShieldAlert,
  ArrowRight
} from 'lucide-react';
import { getActiveRole, setActiveRole } from '../../services/api';
import type { Role } from '../../types';

interface PermissionRow {
  permission: string;
  category: string;
  description: string;
  superAdmin: boolean;
  admin: boolean;
  developer: boolean;
  operator: boolean;
  viewer: boolean;
}

const PERMISSIONS_MATRIX: PermissionRow[] = [
  // Servers
  { permission: 'servers:read', category: 'MCP Servers', description: 'View registered MCP servers & telemetry', superAdmin: true, admin: true, developer: true, operator: true, viewer: true },
  { permission: 'servers:write', category: 'MCP Servers', description: 'Register new servers & edit endpoints', superAdmin: true, admin: true, developer: true, operator: false, viewer: false },
  { permission: 'servers:delete', category: 'MCP Servers', description: 'Decommission and remove server instances', superAdmin: true, admin: false, developer: false, operator: false, viewer: false },
  { permission: 'servers:connect', category: 'MCP Servers', description: 'Initiate JSON-RPC handshake & restart transport', superAdmin: true, admin: true, developer: true, operator: false, viewer: false },

  // Tools
  { permission: 'tools:read', category: 'Tool Registry', description: 'Inspect tools and view JSON input schemas', superAdmin: true, admin: true, developer: true, operator: true, viewer: true },
  { permission: 'tools:execute', category: 'Tool Registry', description: 'Invoke operational tool dispatches', superAdmin: true, admin: true, developer: false, operator: true, viewer: false },
  { permission: 'tools:test', category: 'Tool Registry', description: 'Execute tools inside interactive playground', superAdmin: true, admin: true, developer: true, operator: false, viewer: false },
  { permission: 'tools:config', category: 'Tool Registry', description: 'Enable/disable tools & adjust risk levels', superAdmin: true, admin: true, developer: true, operator: false, viewer: false },

  // Agents
  { permission: 'agents:read', category: 'AI Agents', description: 'Inspect agents, system prompts & histories', superAdmin: true, admin: true, developer: true, operator: true, viewer: true },
  { permission: 'agents:write', category: 'AI Agents', description: 'Create and configure agent parameters', superAdmin: true, admin: true, developer: true, operator: false, viewer: false },
  { permission: 'agents:orchestrate', category: 'AI Agents', description: 'Execute multi-step autonomous workflows', superAdmin: true, admin: true, developer: false, operator: true, viewer: false },

  // Governance
  { permission: 'governance:read', category: 'Governance', description: 'View audit logs, approval items & policies', superAdmin: true, admin: true, developer: false, operator: false, viewer: true },
  { permission: 'governance:approve', category: 'Governance', description: 'Authorize pending destructive tool operations', superAdmin: true, admin: true, developer: false, operator: false, viewer: false },
  { permission: 'governance:policies', category: 'Governance', description: 'Create and enforce platform security policies', superAdmin: true, admin: true, developer: false, operator: false, viewer: false },

  // Observability & Settings
  { permission: 'traces:read', category: 'Observability', description: 'Inspect full execution trace timeline and spans', superAdmin: true, admin: true, developer: true, operator: true, viewer: true },
  { permission: 'metrics:read', category: 'Observability', description: 'View system health, latencies, and volume', superAdmin: true, admin: true, developer: true, operator: true, viewer: true },
  { permission: 'settings:write', category: 'Settings', description: 'Modify organization and user credentials', superAdmin: true, admin: false, developer: false, operator: false, viewer: false },
];

export const AccessControl: React.FC = () => {
  const [activeRole, setLocalRole] = useState<Role>(getActiveRole());

  const handleRoleChange = (role: Role) => {
    setActiveRole(role);
    setLocalRole(role);
  };

  return (
    <div className="space-y-6 font-mono">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#303640] pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-[#ECEFF4]">
              ROLE-BASED ACCESS CONTROL (RBAC)
            </h1>
            <span className="text-[11px] px-2 py-0.5 rounded bg-[#48B9D0]/15 text-[#48B9D0] border border-[#48B9D0]/30">
              LEAST-PRIVILEGE ENFORCEMENT
            </span>
          </div>
          <p className="text-xs text-[#9DA7B5] mt-1 font-sans">
            Strict backend authorization matrix mapping roles to tool execution rights, server operations, and approval authority.
          </p>
        </div>
      </div>

      {/* Active Session Simulation Banner */}
      <div className="bg-[#14171D] border border-[#303640] p-4 rounded flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="text-xs font-bold text-[#ECEFF4] flex items-center gap-2">
            <User className="w-4 h-4 text-[#F0A43A]" />
            Active Session Simulator (Live Role Switching)
          </div>
          <p className="text-[11px] text-[#9DA7B5] mt-1 font-sans">
            Switch your active role below to experience live backend policy gating in the Tool Playground and AI Orchestrator.
          </p>
        </div>
        <div className="flex items-center gap-1.5 bg-[#101216] p-1 border border-[#303640] rounded text-xs">
          {(['SUPER_ADMIN', 'ADMIN', 'DEVELOPER', 'OPERATOR', 'VIEWER'] as const).map((r) => (
            <button
              key={r}
              onClick={() => handleRoleChange(r)}
              className={`px-3 py-1.5 rounded transition-colors text-[11px] ${
                activeRole === r
                  ? 'bg-[#181C23] text-[#F0A43A] font-bold border border-[#F0A43A]/40'
                  : 'text-[#9DA7B5] hover:text-[#ECEFF4]'
              }`}
            >
              {r}
            </button>
          ))}
        </div>
      </div>

      {/* RBAC Table */}
      <div className="bg-[#14171D] border border-[#303640] rounded overflow-hidden">
        <table className="w-full text-left text-xs">
          <thead className="bg-[#181C23] text-[#9DA7B5] border-b border-[#303640]">
            <tr>
              <th className="py-2.5 px-3">Permission Key</th>
              <th className="py-2.5 px-3">Scope</th>
              <th className="py-2.5 px-3">Description</th>
              <th className="py-2.5 px-3 text-center">Super Admin</th>
              <th className="py-2.5 px-3 text-center">Admin</th>
              <th className="py-2.5 px-3 text-center">Developer</th>
              <th className="py-2.5 px-3 text-center">Operator</th>
              <th className="py-2.5 px-3 text-center">Viewer</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#303640]">
            {PERMISSIONS_MATRIX.map((row) => (
              <tr key={row.permission} className="hover:bg-[#181C23]/40">
                <td className="py-2.5 px-3 font-bold text-[#ECEFF4]">{row.permission}</td>
                <td className="py-2.5 px-3 text-[#48B9D0]">{row.category}</td>
                <td className="py-2.5 px-3 text-[#9DA7B5] font-sans">{row.description}</td>
                <td className="py-2.5 px-3 text-center">
                  {row.superAdmin ? <Check className="w-4 h-4 text-[#43B581] mx-auto" /> : <X className="w-4 h-4 text-[#E05252]/50 mx-auto" />}
                </td>
                <td className="py-2.5 px-3 text-center">
                  {row.admin ? <Check className="w-4 h-4 text-[#43B581] mx-auto" /> : <X className="w-4 h-4 text-[#E05252]/50 mx-auto" />}
                </td>
                <td className="py-2.5 px-3 text-center">
                  {row.developer ? <Check className="w-4 h-4 text-[#43B581] mx-auto" /> : <X className="w-4 h-4 text-[#E05252]/50 mx-auto" />}
                </td>
                <td className="py-2.5 px-3 text-center">
                  {row.operator ? <Check className="w-4 h-4 text-[#43B581] mx-auto" /> : <X className="w-4 h-4 text-[#E05252]/50 mx-auto" />}
                </td>
                <td className="py-2.5 px-3 text-center">
                  {row.viewer ? <Check className="w-4 h-4 text-[#43B581] mx-auto" /> : <X className="w-4 h-4 text-[#E05252]/50 mx-auto" />}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
