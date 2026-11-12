import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Network,
  Server,
  Wrench,
  Bot,
  Layers,
  ShieldCheck,
  FileCheck2,
  Clock,
  History,
  Activity,
  BarChart3,
  AlertTriangle,
  Building2,
  Key,
  Users,
  ChevronRight
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../services/api';

interface NavItem {
  name: string;
  path: string;
  icon: React.ElementType;
  badge?: number;
}

interface NavSection {
  title: string;
  items: NavItem[];
}

export const Sidebar: React.FC = () => {
  const { data: metrics } = useQuery({
    queryKey: ['command-center-metrics'],
    queryFn: api.getMetrics,
    refetchInterval: 15000,
  });

  const pendingApprovalsCount = metrics?.top_metrics?.pending_approvals ?? 0;

  const sections: NavSection[] = [
    {
      title: 'OVERVIEW',
      items: [
        { name: 'Command Center', path: '/', icon: LayoutDashboard },
        { name: 'Infrastructure Map', path: '/topology', icon: Network },
      ],
    },
    {
      title: 'MANAGEMENT',
      items: [
        { name: 'MCP Servers', path: '/servers', icon: Server, badge: metrics?.top_metrics?.registered_servers },
        { name: 'Tool Registry', path: '/tools', icon: Wrench },
        { name: 'AI Agents', path: '/agents', icon: Bot, badge: metrics?.top_metrics?.connected_agents },
        { name: 'Integrations', path: '/integrations', icon: Layers },
      ],
    },
    {
      title: 'GOVERNANCE',
      items: [
        { name: 'Access Control', path: '/governance/access-control', icon: ShieldCheck },
        { name: 'Security Policies', path: '/governance/policies', icon: FileCheck2 },
        { name: 'Approval Queue', path: '/governance/approvals', icon: Clock, badge: pendingApprovalsCount },
        { name: 'Audit Logs', path: '/governance/audit-logs', icon: History },
      ],
    },
    {
      title: 'OBSERVABILITY',
      items: [
        { name: 'Execution Traces', path: '/observability/traces', icon: Activity },
        { name: 'System Metrics', path: '/observability/metrics', icon: BarChart3 },
        { name: 'Alerts & Incidents', path: '/observability/alerts', icon: AlertTriangle },
      ],
    },
    {
      title: 'SETTINGS',
      items: [
        { name: 'Organization', path: '/settings/organization', icon: Building2 },
        { name: 'API Configuration', path: '/settings/api', icon: Key },
        { name: 'User Management', path: '/settings/users', icon: Users },
      ],
    },
  ];

  return (
    <aside className="w-64 bg-[#101216] border-r border-[#303640] flex flex-col h-screen fixed left-0 top-0 z-40 select-none">
      {/* Brand Header */}
      <div className="h-16 border-b border-[#303640] px-5 flex items-center justify-between bg-[#14171D]">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded bg-[#181C23] border border-[#F0A43A]/40 flex items-center justify-center shadow-sm">
            <div className="w-3.5 h-3.5 bg-[#F0A43A] rotate-45 transform" />
          </div>
          <div>
            <div className="text-sm font-bold tracking-wider text-[#ECEFF4] font-mono flex items-center gap-1.5">
              MCP NEXUS
              <span className="text-[10px] px-1 py-0.2 bg-[#F0A43A]/20 text-[#F0A43A] font-sans font-semibold rounded">
                v1.0
              </span>
            </div>
            <div className="text-[9px] tracking-widest text-[#9DA7B5] font-mono uppercase">
              CONNECT • ORCHESTRATE • GOVERN
            </div>
          </div>
        </div>
      </div>

      {/* Navigation Sections */}
      <div className="flex-1 overflow-y-auto py-3 px-3 space-y-5">
        {sections.map((section) => (
          <div key={section.title} className="space-y-1">
            <div className="px-2 text-[10px] font-semibold text-[#626D7C] tracking-wider uppercase font-mono">
              {section.title}
            </div>
            <div className="space-y-0.5">
              {section.items.map((item) => {
                const Icon = item.icon;
                return (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    end={item.path === '/'}
                    className={({ isActive }) =>
                      `flex items-center justify-between px-2.5 py-1.5 rounded text-xs transition-colors group ${
                        isActive
                          ? 'bg-[#181C23] text-[#F0A43A] border-l-2 border-[#F0A43A] font-medium'
                          : 'text-[#9DA7B5] hover:bg-[#181C23]/60 hover:text-[#ECEFF4]'
                      }`
                    }
                  >
                    <div className="flex items-center space-x-2.5">
                      <Icon className="w-4 h-4 opacity-80 group-hover:opacity-100" />
                      <span>{item.name}</span>
                    </div>
                    {item.badge !== undefined && item.badge > 0 && (
                      <span className={`text-[10px] px-1.5 py-0.2 rounded font-mono font-bold ${
                        item.name === 'Approval Queue' 
                          ? 'bg-[#E05252]/20 text-[#E05252] border border-[#E05252]/30 animate-pulse'
                          : 'bg-[#181C23] text-[#9DA7B5] border border-[#303640]'
                      }`}>
                        {item.badge}
                      </span>
                    )}
                  </NavLink>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {/* Footer Info: Target Review */}
      <div className="p-3 border-t border-[#303640] bg-[#14171D]/60 text-[10px] text-[#626D7C] font-mono flex items-center justify-between">
        <span className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-[#43B581]" />
          L&T Technical Architecture
        </span>
        <span className="text-[#9DA7B5]">PROD-SEC</span>
      </div>
    </aside>
  );
};
