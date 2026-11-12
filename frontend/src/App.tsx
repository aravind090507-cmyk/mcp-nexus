import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { DashboardLayout } from './layouts/DashboardLayout';
import { CommandCenter } from './features/dashboard/CommandCenter';
import { InfrastructureMap } from './features/topology/InfrastructureMap';
import { ServerManagement } from './features/servers/ServerManagement';
import { ToolRegistry } from './features/tools/ToolRegistry';
import { AgentOrchestration } from './features/agents/AgentOrchestration';
import { IntegrationsView } from './features/integrations/IntegrationsView';
import { EnterpriseWorkflows } from './features/workflows/EnterpriseWorkflows';
import { AccessControl } from './features/governance/AccessControl';
import { SecurityPolicies } from './features/governance/SecurityPolicies';
import { ApprovalQueue } from './features/governance/ApprovalQueue';
import { AuditLogsView } from './features/governance/AuditLogsView';
import { ExecutionTraces } from './features/observability/ExecutionTraces';
import { SystemMetrics } from './features/observability/SystemMetrics';
import { AlertsIncidents } from './features/observability/AlertsIncidents';
import { OrganizationSettings } from './features/settings/OrganizationSettings';
import { ApiConfiguration } from './features/settings/ApiConfiguration';
import { UserManagement } from './features/settings/UserManagement';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      staleTime: 5000,
      retry: 1,
    },
  },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<DashboardLayout />}>
            {/* OVERVIEW */}
            <Route index element={<CommandCenter />} />
            <Route path="topology" element={<InfrastructureMap />} />

            {/* MANAGEMENT */}
            <Route path="servers" element={<ServerManagement />} />
            <Route path="tools" element={<ToolRegistry />} />
            <Route path="agents" element={<AgentOrchestration />} />
            <Route path="workflows" element={<EnterpriseWorkflows />} />
            <Route path="integrations" element={<IntegrationsView />} />

            {/* GOVERNANCE */}
            <Route path="governance/access-control" element={<AccessControl />} />
            <Route path="governance/policies" element={<SecurityPolicies />} />
            <Route path="governance/approvals" element={<ApprovalQueue />} />
            <Route path="governance/audit-logs" element={<AuditLogsView />} />

            {/* OBSERVABILITY */}
            <Route path="observability/traces" element={<ExecutionTraces />} />
            <Route path="observability/metrics" element={<SystemMetrics />} />
            <Route path="observability/alerts" element={<AlertsIncidents />} />

            {/* SETTINGS */}
            <Route path="settings/organization" element={<OrganizationSettings />} />
            <Route path="settings/api" element={<ApiConfiguration />} />
            <Route path="settings/users" element={<UserManagement />} />

            {/* CATCH-ALL */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
