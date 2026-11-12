import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../services/api';
import { Building2, ShieldCheck, Server, Globe } from 'lucide-react';

export const OrganizationSettings: React.FC = () => {
  const { data: org, isLoading } = useQuery({
    queryKey: ['org-settings'],
    queryFn: () => api.getOrganization(),
  });

  return (
    <div className="space-y-6 font-mono max-w-3xl">
      <div className="flex items-center justify-between border-b border-[#303640] pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-[#ECEFF4]">
              ORGANIZATION SETTINGS
            </h1>
            <span className="text-[11px] px-2 py-0.5 rounded bg-[#F0A43A]/15 text-[#F0A43A] border border-[#F0A43A]/30">
              TENANT PROFILE
            </span>
          </div>
          <p className="text-xs text-[#9DA7B5] mt-1 font-sans">
            Enterprise identity, compliance boundary, and environment configurations.
          </p>
        </div>
      </div>

      <div className="bg-[#14171D] border border-[#303640] rounded p-6 space-y-4">
        <div className="grid grid-cols-2 gap-4 text-xs">
          <div>
            <label className="text-[10px] text-[#626D7C] uppercase">Organization Name</label>
            <div className="mt-1 p-2 bg-[#181C23] border border-[#303640] rounded text-[#ECEFF4] font-bold">
              {org?.name || 'Larsen & Toubro Heavy Civil & Digital IC'}
            </div>
          </div>
          <div>
            <label className="text-[10px] text-[#626D7C] uppercase">Tenant Slug</label>
            <div className="mt-1 p-2 bg-[#181C23] border border-[#303640] rounded text-[#48B9D0]">
              {org?.slug || 'lt-heavy-civil'}
            </div>
          </div>
          <div>
            <label className="text-[10px] text-[#626D7C] uppercase">License Tier</label>
            <div className="mt-1 p-2 bg-[#181C23] border border-[#303640] rounded text-[#43B581] font-bold">
              {org?.tier || 'ENTERPRISE MISSION-CRITICAL'}
            </div>
          </div>
          <div>
            <label className="text-[10px] text-[#626D7C] uppercase">Environment Active</label>
            <div className="mt-1 p-2 bg-[#181C23] border border-[#303640] rounded text-[#ECEFF4]">
              {org?.environment || 'Production'}
            </div>
          </div>
        </div>

        <div className="pt-4 border-t border-[#303640] text-xs text-[#9DA7B5] font-sans">
          Tagline: <span className="font-mono text-[#F0A43A] font-bold">CONNECT. ORCHESTRATE. GOVERN.</span>
        </div>
      </div>
    </div>
  );
};
