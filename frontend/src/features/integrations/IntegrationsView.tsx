import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../services/api';
import {
  Layers,
  CheckCircle,
  ExternalLink,
  RefreshCw,
  Server,
  Activity,
  Building
} from 'lucide-react';

export const IntegrationsView: React.FC = () => {
  const { data: integrations, isLoading } = useQuery({
    queryKey: ['enterprise-integrations'],
    queryFn: () => api.getIntegrations(),
  });

  return (
    <div className="space-y-6 font-mono">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#303640] pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-[#ECEFF4]">
              ENTERPRISE INTEGRATIONS
            </h1>
            <span className="text-[11px] px-2 py-0.5 rounded bg-[#43B581]/15 text-[#43B581] border border-[#43B581]/30">
              ERP • INVENTORY • EQUIPMENT • HR • PROCUREMENT
            </span>
          </div>
          <p className="text-xs text-[#9DA7B5] mt-1 font-sans">
            Modular connectors bridging corporate systems of record with Model Context Protocol servers.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {isLoading ? (
          <div className="col-span-3 text-center text-xs text-[#9DA7B5] py-8">
            Querying enterprise integration connectors...
          </div>
        ) : (
          (integrations || []).map((item) => (
            <div
              key={item.id}
              className="p-5 bg-[#14171D] border border-[#303640] rounded space-y-3 flex flex-col justify-between"
            >
              <div>
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="text-xs font-bold text-[#ECEFF4]">{item.name}</h3>
                    <div className="text-[10px] text-[#48B9D0] mt-0.5">{item.vendor} • {item.system_type}</div>
                  </div>
                  <span className="text-[9px] px-2 py-0.5 rounded font-bold bg-[#43B581]/15 text-[#43B581] border border-[#43B581]/30">
                    {item.status}
                  </span>
                </div>

                <div className="mt-3 p-2.5 bg-[#101216] border border-[#303640] rounded text-[11px] text-[#9DA7B5] space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-[#626D7C]">Linked Server:</span>
                    <span className="text-[#F0A43A] font-semibold">{item.linked_mcp_server || 'Direct Connector'}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[#626D7C]">Sync Cadence:</span>
                    <span className="text-[#ECEFF4]">{item.sync_interval_mins} mins</span>
                  </div>
                </div>

                {item.stats && Object.keys(item.stats).length > 0 && (
                  <div className="mt-2 text-[10px] text-[#626D7C]">
                    Telemetry: {JSON.stringify(item.stats)}
                  </div>
                )}
              </div>

              <div className="pt-2 border-t border-[#303640] flex items-center justify-between text-[10px] text-[#626D7C]">
                <span>Last Sync: {new Date(item.last_sync).toLocaleTimeString()}</span>
                <span className="text-[#43B581]">Active Webhook</span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
