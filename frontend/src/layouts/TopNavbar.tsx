import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search,
  Bell,
  ChevronDown,
  Shield,
  Activity,
  CheckCircle2,
  Building,
  Radio,
  SlidersHorizontal,
  X
} from 'lucide-react';
import { getActiveRole, setActiveRole } from '../services/api';
import type { Role } from '../types';

interface TopNavbarProps {
  onSearch?: (query: string) => void;
}

export const TopNavbar: React.FC<TopNavbarProps> = ({ onSearch }) => {
  const navigate = useNavigate();
  const [currentRole, setCurrentRole] = useState<Role>(getActiveRole());
  const [environment, setEnvironment] = useState<'Development' | 'Staging' | 'Production'>('Production');
  const [showRoleDropdown, setShowRoleDropdown] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);
  const [searchVal, setSearchVal] = useState('');
  const [showSearchResults, setShowSearchResults] = useState(false);
  const searchContainerRef = useRef<HTMLDivElement>(null);

  const SEARCH_INDEX = [
    { title: 'Command Center', path: '/', category: 'OVERVIEW', desc: 'Real-time telemetry, server health, top metrics' },
    { title: 'Infrastructure Map', path: '/topology', category: 'OVERVIEW', desc: 'React Flow topology graph of servers & agents' },
    { title: 'MCP Servers', path: '/servers', category: 'MANAGEMENT', desc: 'Register, inspect STDIO/HTTP MCP servers' },
    { title: 'Tool Registry & Playground', path: '/tools', category: 'MANAGEMENT', desc: 'Central tool discovery, policies & playground test' },
    { title: 'AI Agent Orchestration', path: '/agents', category: 'MANAGEMENT', desc: 'Cross-server multi-step AI orchestration' },
    { title: 'Enterprise Integrations', path: '/integrations', category: 'MANAGEMENT', desc: 'ERP, SAP S/4HANA, Primavera, IoT SCADA' },
    { title: 'Access Control (RBAC)', path: '/governance/access-control', category: 'GOVERNANCE', desc: 'Role permissions matrix & active users' },
    { title: 'Security Policies', path: '/governance/policies', category: 'GOVERNANCE', desc: 'Policy guardrails, rate limits, sandbox constraints' },
    { title: 'Approval Queue', path: '/governance/approvals', category: 'GOVERNANCE', desc: 'Dual-control human-in-the-loop approvals' },
    { title: 'Audit Logs', path: '/governance/audit-logs', category: 'GOVERNANCE', desc: 'Immutable compliance trail of all operations' },
    { title: 'Execution Traces', path: '/observability/traces', category: 'OBSERVABILITY', desc: 'End-to-end distributed trace spans' },
    { title: 'System Metrics', path: '/observability/metrics', category: 'OBSERVABILITY', desc: 'Live CPU, memory, latency & throughput telemetry' },
    { title: 'Alerts & Incidents', path: '/observability/alerts', category: 'OBSERVABILITY', desc: 'Critical alarms & incident triage' },
    { title: 'Organization Settings', path: '/settings/organization', category: 'SETTINGS', desc: 'L&T enterprise entity profile' },
    { title: 'API Configuration', path: '/settings/api', category: 'SETTINGS', desc: 'MCP gateway endpoints & keys' },
    { title: 'User Management', path: '/settings/users', category: 'SETTINGS', desc: 'Enterprise IAM accounts' },
  ];

  const filteredSearchResults = searchVal.trim()
    ? SEARCH_INDEX.filter(
        (item) =>
          item.title.toLowerCase().includes(searchVal.toLowerCase()) ||
          item.desc.toLowerCase().includes(searchVal.toLowerCase()) ||
          item.category.toLowerCase().includes(searchVal.toLowerCase())
      )
    : [];

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (searchContainerRef.current && !searchContainerRef.current.contains(e.target as Node)) {
        setShowSearchResults(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    const handleRoleChanged = () => {
      setCurrentRole(getActiveRole());
    };
    window.addEventListener('role_changed', handleRoleChanged);
    return () => window.removeEventListener('role_changed', handleRoleChanged);
  }, []);

  const handleRoleSelect = (role: Role) => {
    setActiveRole(role);
    setCurrentRole(role);
    setShowRoleDropdown(false);
  };

  const rolesList: { role: Role; label: string; desc: string }[] = [
    { role: 'SUPER_ADMIN', label: 'Super Admin', desc: 'Unrestricted control plane & master policies' },
    { role: 'ADMIN', label: 'Admin', desc: 'Servers, agents & approval authorizations' },
    { role: 'DEVELOPER', label: 'Developer', desc: 'Register servers, test permitted tools' },
    { role: 'OPERATOR', label: 'Operator', desc: 'Execute authorized workflows & orchestrations' },
    { role: 'VIEWER', label: 'Viewer', desc: 'Read-only access to monitoring & traces' },
  ];

  return (
    <header className="h-16 bg-[#14171D] border-b border-[#303640] px-6 flex items-center justify-between sticky top-0 z-30 ml-64">
      {/* Left items: Org & Environment */}
      <div className="flex items-center space-x-4">
        {/* Organization Badge */}
        <div className="flex items-center space-x-2 px-3 py-1.5 bg-[#181C23] border border-[#303640] rounded text-xs text-[#ECEFF4]">
          <Building className="w-3.5 h-3.5 text-[#F0A43A]" />
          <span className="font-semibold tracking-wide">L&T Heavy Civil IC</span>
          <span className="text-[10px] text-[#626D7C] font-mono">| EPC Division</span>
        </div>

        {/* Environment Selector */}
        <div className="flex items-center space-x-1 bg-[#101216] p-0.5 border border-[#303640] rounded text-xs">
          {(['Development', 'Staging', 'Production'] as const).map((env) => (
            <button
              key={env}
              onClick={() => setEnvironment(env)}
              className={`px-2.5 py-1 rounded text-[11px] font-mono transition-colors ${
                environment === env
                  ? 'bg-[#181C23] text-[#F0A43A] font-semibold border border-[#F0A43A]/30'
                  : 'text-[#9DA7B5] hover:text-[#ECEFF4]'
              }`}
            >
              {env}
            </button>
          ))}
        </div>
      </div>

      {/* Center: Global Search */}
      <div className="flex-1 max-w-md mx-6" ref={searchContainerRef}>
        <div className="relative">
          <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-[#626D7C]" />
          <input
            type="text"
            placeholder="Global search servers, tools, agents, traces (Ctrl+K)..."
            value={searchVal}
            onFocus={() => setShowSearchResults(true)}
            onChange={(e) => {
              setSearchVal(e.target.value);
              setShowSearchResults(true);
              onSearch?.(e.target.value);
            }}
            className="w-full bg-[#101216] border border-[#303640] rounded pl-8 pr-12 py-1.5 text-xs text-[#ECEFF4] placeholder-[#626D7C] focus:outline-none focus:border-[#F0A43A]/60 font-mono"
          />
          <span className="absolute right-2.5 top-2 text-[10px] bg-[#181C23] px-1.5 py-0.5 rounded text-[#626D7C] border border-[#303640] font-mono">
            ⌘K
          </span>

          {/* Quick Navigation Results Dropdown */}
          {showSearchResults && searchVal.trim().length > 0 && (
            <div className="absolute left-0 right-0 mt-2 bg-[#14171D] border border-[#303640] rounded shadow-2xl p-2 z-50 max-h-72 overflow-y-auto font-mono text-xs">
              <div className="px-2 py-1 text-[10px] text-[#626D7C] uppercase tracking-wider border-b border-[#303640] flex justify-between">
                <span>Matching Control Plane Views</span>
                <span>{filteredSearchResults.length} Results</span>
              </div>
              {filteredSearchResults.length === 0 ? (
                <div className="p-3 text-center text-[#626D7C] text-xs">
                  No views or tools matching "{searchVal}"
                </div>
              ) : (
                <div className="py-1 space-y-1">
                  {filteredSearchResults.map((res) => (
                    <button
                      key={res.path}
                      onClick={() => {
                        navigate(res.path);
                        setShowSearchResults(false);
                        setSearchVal('');
                      }}
                      className="w-full text-left p-2 rounded hover:bg-[#181C23] group transition-colors flex items-start justify-between"
                    >
                      <div>
                        <div className="font-semibold text-[#ECEFF4] group-hover:text-[#F0A43A] flex items-center gap-2">
                          <span>{res.title}</span>
                          <span className="text-[9px] px-1 bg-[#101216] text-[#48B9D0] border border-[#303640] rounded">
                            {res.category}
                          </span>
                        </div>
                        <div className="text-[10px] text-[#9DA7B5] mt-0.5 line-clamp-1">
                          {res.desc}
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Right controls: Health status, Notifications, Profile / Role Switcher */}
      <div className="flex items-center space-x-4">
        {/* System Health Indicator */}
        <div className="flex items-center space-x-2 px-2.5 py-1 bg-[#101216] border border-[#303640] rounded text-[11px] font-mono">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#43B581] opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-[#43B581]"></span>
          </span>
          <span className="text-[#43B581] font-semibold tracking-wide">OPERATIONAL</span>
          <span className="text-[#626D7C] text-[10px]">99.98%</span>
        </div>

        {/* Notifications Button */}
        <div className="relative">
          <button
            onClick={() => setShowNotifications(!showNotifications)}
            className="p-1.5 text-[#9DA7B5] hover:text-[#ECEFF4] hover:bg-[#181C23] rounded border border-[#303640] relative"
            title="System Notifications"
          >
            <Bell className="w-4 h-4" />
            <span className="absolute -top-1 -right-1 w-2 h-2 bg-[#F0A43A] rounded-full" />
          </button>

          {/* Notifications Flyout */}
          {showNotifications && (
            <div className="absolute right-0 mt-2 w-80 bg-[#14171D] border border-[#303640] rounded shadow-2xl p-3 z-50">
              <div className="flex items-center justify-between pb-2 border-b border-[#303640] text-xs font-semibold text-[#ECEFF4]">
                <span>Operational Alerts</span>
                <button onClick={() => setShowNotifications(false)}>
                  <X className="w-3.5 h-3.5 text-[#626D7C]" />
                </button>
              </div>
              <div className="py-2 space-y-2 text-xs">
                <div className="p-2 bg-[#181C23] border border-[#EBB346]/30 rounded">
                  <div className="text-[#EBB346] font-mono font-bold text-[11px]">MAINTENANCE OVERDUE</div>
                  <div className="text-[#9DA7B5] text-[11px] mt-0.5">Crane CC-8800 at Hazira Jetty 3 has exceeded scheduled hoist inspection by 42 days.</div>
                </div>
                <div className="p-2 bg-[#181C23] border border-[#E05252]/30 rounded">
                  <div className="text-[#E05252] font-mono font-bold text-[11px]">INVENTORY SHORTAGE</div>
                  <div className="text-[#9DA7B5] text-[11px] mt-0.5">Cryogenic Flanges SS-316L reached zero inventory at Hazira central yard.</div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* User Role Switcher Dropdown (Live RBAC Switcher) */}
        <div className="relative">
          <button
            onClick={() => setShowRoleDropdown(!showRoleDropdown)}
            className="flex items-center space-x-2.5 px-3 py-1.5 bg-[#181C23] border border-[#303640] hover:border-[#F0A43A]/50 rounded text-xs transition-colors"
          >
            <div className="w-6 h-6 rounded bg-[#F0A43A]/20 border border-[#F0A43A]/40 flex items-center justify-center text-[10px] font-mono text-[#F0A43A] font-bold">
              VS
            </div>
            <div className="text-left">
              <div className="text-[#ECEFF4] font-medium leading-none">V. Sharma</div>
              <div className="text-[10px] font-mono text-[#F0A43A] leading-tight mt-0.5 flex items-center gap-1">
                <Shield className="w-2.5 h-2.5" />
                {currentRole}
              </div>
            </div>
            <ChevronDown className="w-3.5 h-3.5 text-[#626D7C]" />
          </button>

          {/* Role selection dropdown */}
          {showRoleDropdown && (
            <div className="absolute right-0 mt-2 w-64 bg-[#14171D] border border-[#303640] rounded shadow-2xl p-2 z-50">
              <div className="px-2 py-1 text-[10px] font-mono uppercase text-[#626D7C] tracking-wider border-b border-[#303640]">
                Active RBAC Role Switcher
              </div>
              <div className="py-1 space-y-1">
                {rolesList.map((r) => (
                  <button
                    key={r.role}
                    onClick={() => handleRoleSelect(r.role)}
                    className={`w-full text-left px-2.5 py-1.5 rounded text-xs transition-colors ${
                      currentRole === r.role
                        ? 'bg-[#181C23] text-[#F0A43A] font-semibold border-l-2 border-[#F0A43A]'
                        : 'text-[#9DA7B5] hover:bg-[#181C23] hover:text-[#ECEFF4]'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono">{r.label}</span>
                      {currentRole === r.role && <CheckCircle2 className="w-3 h-3 text-[#F0A43A]" />}
                    </div>
                    <div className="text-[10px] text-[#626D7C] mt-0.5">{r.desc}</div>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
