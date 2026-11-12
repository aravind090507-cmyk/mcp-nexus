import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../services/api';
import {
  History,
  Search,
  Filter,
  User,
  Terminal,
  Calendar,
  Layers
} from 'lucide-react';

export const AuditLogsView: React.FC = () => {
  const [searchFilter, setSearchFilter] = useState('');

  const { data: logs, isLoading } = useQuery({
    queryKey: ['audit-logs'],
    queryFn: () => api.getAuditLogs(),
    refetchInterval: 10000,
  });

  const filteredLogs = (logs || []).filter((log) => {
    return (
      log.action.toLowerCase().includes(searchFilter.toLowerCase()) ||
      log.user_name.toLowerCase().includes(searchFilter.toLowerCase()) ||
      (log.details || '').toLowerCase().includes(searchFilter.toLowerCase())
    );
  });

  return (
    <div className="space-y-6 font-mono">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#303640] pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-[#ECEFF4]">
              PLATFORM AUDIT LOGS
            </h1>
            <span className="text-[11px] px-2 py-0.5 rounded bg-[#48B9D0]/15 text-[#48B9D0] border border-[#48B9D0]/30">
              IMMUTABLE COMPLIANCE TRAIL
            </span>
          </div>
          <p className="text-xs text-[#9DA7B5] mt-1 font-sans">
            Forensic tracking of configuration changes, approval authorizations, and protocol invocations.
          </p>
        </div>
      </div>

      {/* Search Input */}
      <div className="bg-[#14171D] p-3 border border-[#303640] rounded flex items-center gap-2 max-w-md">
        <Search className="w-3.5 h-3.5 text-[#626D7C]" />
        <input
          type="text"
          placeholder="Filter audit records by action or user..."
          value={searchFilter}
          onChange={(e) => setSearchFilter(e.target.value)}
          className="w-full bg-transparent text-xs text-[#ECEFF4] focus:outline-none placeholder-[#626D7C]"
        />
      </div>

      {/* Audit Log Table */}
      <div className="bg-[#14171D] border border-[#303640] rounded overflow-hidden">
        <table className="w-full text-left text-xs">
          <thead className="bg-[#181C23] text-[#9DA7B5] border-b border-[#303640]">
            <tr>
              <th className="py-2.5 px-3">Timestamp</th>
              <th className="py-2.5 px-3">Action</th>
              <th className="py-2.5 px-3">Entity Type</th>
              <th className="py-2.5 px-3">Actor / Role</th>
              <th className="py-2.5 px-3">Details</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#303640]">
            {isLoading ? (
              <tr>
                <td colSpan={5} className="py-8 text-center text-[#9DA7B5]">
                  Reading audit log vault...
                </td>
              </tr>
            ) : filteredLogs.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-8 text-center text-[#626D7C]">
                  No audit records match the query.
                </td>
              </tr>
            ) : (
              filteredLogs.map((item) => (
                <tr key={item.id} className="hover:bg-[#181C23]/40">
                  <td className="py-2.5 px-3 text-[#626D7C] whitespace-nowrap">
                    {new Date(item.timestamp).toLocaleString()}
                  </td>
                  <td className="py-2.5 px-3 font-bold text-[#F0A43A] whitespace-nowrap">
                    {item.action}
                  </td>
                  <td className="py-2.5 px-3 text-[#48B9D0] whitespace-nowrap">
                    {item.entity_type}
                  </td>
                  <td className="py-2.5 px-3 whitespace-nowrap">
                    <span className="text-[#ECEFF4] font-medium">{item.user_name}</span>
                    <span className="text-[10px] text-[#626D7C] ml-1.5">({item.role})</span>
                  </td>
                  <td className="py-2.5 px-3 text-[#9DA7B5] font-sans">
                    {item.details}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
