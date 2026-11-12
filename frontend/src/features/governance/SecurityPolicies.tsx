import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../services/api';
import {
  FileCheck2,
  ShieldCheck,
  AlertTriangle,
  Lock,
  Layers,
  ArrowRight
} from 'lucide-react';

export const SecurityPolicies: React.FC = () => {
  const { data: policies, isLoading } = useQuery({
    queryKey: ['security-policies'],
    queryFn: () => api.getPolicies(),
  });

  return (
    <div className="space-y-6 font-mono">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#303640] pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-[#ECEFF4]">
              SECURITY POLICIES & CONSTRAINTS
            </h1>
            <span className="text-[11px] px-2 py-0.5 rounded bg-[#43B581]/15 text-[#43B581] border border-[#43B581]/30">
              ACTIVE ENFORCEMENT ENGINE
            </span>
          </div>
          <p className="text-xs text-[#9DA7B5] mt-1 font-sans">
            Declarative governance rules evaluated synchronously before any MCP tool invocation.
          </p>
        </div>
      </div>

      {/* Policies Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {isLoading ? (
          <div className="col-span-2 text-center text-xs text-[#9DA7B5] py-8">
            Loading governance policies...
          </div>
        ) : (
          (policies || []).map((pol) => (
            <div
              key={pol.id}
              className="p-5 bg-[#14171D] border border-[#303640] rounded space-y-3"
            >
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-[#F0A43A] font-bold">{pol.id}</span>
                    <span className="text-xs font-bold text-[#ECEFF4]">{pol.name}</span>
                  </div>
                  <div className="text-[10px] text-[#48B9D0] mt-0.5">
                    Scope: {pol.scope} • Trigger: {pol.risk_trigger}
                  </div>
                </div>
                <span className="text-[10px] px-2 py-0.5 rounded font-bold bg-[#43B581]/15 text-[#43B581] border border-[#43B581]/30">
                  {pol.enforcement}
                </span>
              </div>

              <p className="text-xs text-[#9DA7B5] font-sans leading-relaxed">
                {pol.description}
              </p>

              <div className="pt-2 border-t border-[#303640] flex items-center justify-between text-[11px] text-[#626D7C]">
                <span>Status: Enforcing</span>
                <span className="text-[#43B581] font-semibold">Zero Bypass</span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
