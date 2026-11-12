import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../services/api';
import {
  AlertTriangle,
  ShieldAlert,
  Clock,
  Terminal,
  Activity,
  CheckCircle2
} from 'lucide-react';

export const AlertsIncidents: React.FC = () => {
  const { data: metrics, isLoading } = useQuery({
    queryKey: ['command-center-metrics'],
    queryFn: api.getMetrics,
  });

  return (
    <div className="space-y-6 font-mono">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#303640] pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-[#ECEFF4]">
              ALERTS & INCIDENT RADAR
            </h1>
            <span className="text-[11px] px-2 py-0.5 rounded bg-[#E05252]/15 text-[#E05252] border border-[#E05252]/30">
              OPERATIONAL RISKS & VIOLATIONS
            </span>
          </div>
          <p className="text-xs text-[#9DA7B5] mt-1 font-sans">
            Real-time feed of policy violations, unauthorized access attempts, and mechanical machinery telemetry alarms.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {(metrics?.security_events || []).map((evt) => (
          <div
            key={evt.id}
            className="p-4 bg-[#14171D] border border-[#303640] rounded space-y-2"
          >
            <div className="flex items-center justify-between">
              <span className={`text-[10px] px-2 py-0.5 rounded font-bold ${
                evt.severity === 'CRITICAL' || evt.severity === 'HIGH'
                  ? 'bg-[#E05252]/15 text-[#E05252] border border-[#E05252]/30'
                  : 'bg-[#EBB346]/15 text-[#EBB346] border border-[#EBB346]/30'
              }`}>
                {evt.severity} SEVERITY
              </span>
              <span className="text-[10px] text-[#626D7C]">{evt.timestamp}</span>
            </div>

            <div className="text-xs font-bold text-[#ECEFF4]">{evt.type}</div>
            <p className="text-xs text-[#9DA7B5] font-sans">{evt.description}</p>

            <div className="pt-2 border-t border-[#303640] flex items-center justify-between text-[10px] text-[#626D7C]">
              <span>Actor: {evt.actor}</span>
              <span>Target: {evt.resource}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
