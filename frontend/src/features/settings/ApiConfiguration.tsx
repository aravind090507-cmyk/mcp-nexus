import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../services/api';
import { Key, ShieldAlert, Cpu, CheckCircle } from 'lucide-react';

export const ApiConfiguration: React.FC = () => {
  const { data: config, isLoading } = useQuery({
    queryKey: ['api-config'],
    queryFn: () => api.getApiConfig(),
  });

  return (
    <div className="space-y-6 font-mono max-w-3xl">
      <div className="flex items-center justify-between border-b border-[#303640] pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-[#ECEFF4]">
              API & LLM GATEWAY CONFIGURATION
            </h1>
            <span className="text-[11px] px-2 py-0.5 rounded bg-[#48B9D0]/15 text-[#48B9D0] border border-[#48B9D0]/30">
              BACKEND ABSTRACTION
            </span>
          </div>
          <p className="text-xs text-[#9DA7B5] mt-1 font-sans">
            Provider credentials, MCP protocol version, and server timeouts. (API keys are never exposed on client surfaces).
          </p>
        </div>
      </div>

      <div className="bg-[#14171D] border border-[#303640] rounded p-6 space-y-4">
        <div className="grid grid-cols-2 gap-4 text-xs">
          <div>
            <label className="text-[10px] text-[#626D7C] uppercase">LLM Provider Active</label>
            <div className="mt-1 p-2 bg-[#181C23] border border-[#303640] rounded text-[#ECEFF4] font-bold">
              {config?.llm_provider || 'DEMO_DETERMINISTIC'}
            </div>
          </div>
          <div>
            <label className="text-[10px] text-[#626D7C] uppercase">Default Model</label>
            <div className="mt-1 p-2 bg-[#181C23] border border-[#303640] rounded text-[#48B9D0]">
              {config?.llm_model || 'gemini-1.5-pro'}
            </div>
          </div>
          <div>
            <label className="text-[10px] text-[#626D7C] uppercase">MCP Protocol Specification</label>
            <div className="mt-1 p-2 bg-[#181C23] border border-[#303640] rounded text-[#43B581] font-bold">
              {config?.mcp_protocol_version || '2024-11-05 (JSON-RPC 2.0)'}
            </div>
          </div>
          <div>
            <label className="text-[10px] text-[#626D7C] uppercase">Default Connection Timeout</label>
            <div className="mt-1 p-2 bg-[#181C23] border border-[#303640] rounded text-[#ECEFF4]">
              {config?.default_timeout_seconds || 15} Seconds
            </div>
          </div>
        </div>

        <div>
          <label className="text-[10px] text-[#626D7C] uppercase">Vault Masked Key</label>
          <div className="mt-1 p-2 bg-[#101216] border border-[#303640] rounded text-xs text-[#9DA7B5]">
            {config?.api_key_masked}
          </div>
        </div>

        <div className="p-3 bg-[#181C23] border border-[#303640] rounded text-xs text-[#9DA7B5] font-sans">
          Supported MCP Transports: <span className="font-mono text-[#F0A43A]">STDIO (Subprocesses)</span>, <span className="font-mono text-[#48B9D0]">Streamable HTTP / SSE</span>.
        </div>
      </div>
    </div>
  );
};
