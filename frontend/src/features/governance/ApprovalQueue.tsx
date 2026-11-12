import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../services/api';
import type { ApprovalRequest } from '../../types';
import {
  Clock,
  CheckCircle,
  XCircle,
  AlertTriangle,
  ShieldAlert,
  Search,
  Filter,
  Check,
  X,
  Terminal,
  User,
  Bot,
  Server
} from 'lucide-react';

export const ApprovalQueue: React.FC = () => {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<string>('PENDING');
  const [selectedReq, setSelectedReq] = useState<ApprovalRequest | null>(null);
  const [reviewReason, setReviewReason] = useState<string>('');

  const { data: approvals, isLoading } = useQuery({
    queryKey: ['approval-requests', statusFilter],
    queryFn: () => api.getApprovals(statusFilter === 'ALL' ? undefined : statusFilter),
    refetchInterval: 8000,
  });

  const reviewMutation = useMutation({
    mutationFn: ({ id, action, reason }: { id: string; action: 'APPROVE' | 'REJECT'; reason?: string }) =>
      api.reviewApproval(id, action, reason),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['approval-requests'] });
      queryClient.invalidateQueries({ queryKey: ['command-center-metrics'] });
      alert(`Approval ${variables.action}: ${data.message}`);
      setSelectedReq(null);
      setReviewReason('');
    },
    onError: (err: any) => alert(`Action Failed: ${err.message}`),
  });

  const handleAction = (id: string, action: 'APPROVE' | 'REJECT') => {
    reviewMutation.mutate({ id, action, reason: reviewReason || 'Operational sign-off granted by administrator.' });
  };

  return (
    <div className="space-y-6 font-mono">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#303640] pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-[#ECEFF4]">
              ADMINISTRATIVE APPROVAL QUEUE
            </h1>
            <span className="text-[11px] px-2 py-0.5 rounded bg-[#E05252]/15 text-[#E05252] border border-[#E05252]/30">
              SENSITIVE & DESTRUCTIVE OPERATION GATE
            </span>
          </div>
          <p className="text-xs text-[#9DA7B5] mt-1 font-sans">
            Operations classified as High or Critical risk (e.g. reporting severe plant breakdown, altering machinery states) require explicit administrative sign-off before dispatch.
          </p>
        </div>

        {/* Filter Pills */}
        <div className="flex items-center space-x-1 bg-[#14171D] p-1 border border-[#303640] rounded text-xs">
          {(['PENDING', 'PARTIALLY_APPROVED', 'APPROVED', 'REJECTED', 'EXECUTED', 'ALL'] as const).map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`px-3 py-1 rounded transition-colors ${
                statusFilter === st
                  ? 'bg-[#181C23] text-[#F0A43A] font-bold border border-[#F0A43A]/30'
                  : 'text-[#9DA7B5] hover:text-[#ECEFF4]'
              }`}
            >
              {st === 'PARTIALLY_APPROVED' ? 'DUAL-PENDING' : st}
            </button>
          ))}
        </div>
      </div>

      {/* Queue List */}
      <div className="bg-[#14171D] border border-[#303640] rounded overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-xs text-[#9DA7B5] animate-pulse">
            Loading approval queue items...
          </div>
        ) : (approvals || []).length === 0 ? (
          <div className="p-12 text-center text-xs text-[#626D7C]">
            <Clock className="w-8 h-8 opacity-40 mx-auto mb-2" />
            No {statusFilter.toLowerCase()} approval requests in the queue.
          </div>
        ) : (
          <div className="divide-y divide-[#303640]">
            {(approvals || []).map((req) => (
              <div
                key={req.id}
                className="p-4 hover:bg-[#181C23]/50 transition-colors flex flex-col md:flex-row md:items-center justify-between gap-4"
              >
                <div className="space-y-1.5 flex-1">
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-bold text-[#ECEFF4]">{req.tool_name}</span>
                    <span className="text-[10px] px-1.5 py-0.2 rounded font-bold bg-[#E05252]/15 text-[#E05252] border border-[#E05252]/30">
                      {req.risk_level} RISK
                    </span>
                    {req.requires_dual_approval && (
                      <span className="text-[10px] px-1.5 py-0.2 rounded font-bold bg-[#F0A43A]/15 text-[#F0A43A] border border-[#F0A43A]/30 flex items-center gap-1">
                        <ShieldAlert className="w-3 h-3" />
                        DUAL-CONTROL REQUIRED
                      </span>
                    )}
                    <span className={`text-[10px] px-1.5 py-0.2 rounded font-bold ${
                      req.status === 'PENDING'
                        ? 'bg-[#EBB346]/15 text-[#EBB346]'
                        : req.status === 'PARTIALLY_APPROVED'
                        ? 'bg-[#48B9D0]/15 text-[#48B9D0] border border-[#48B9D0]/30'
                        : req.status === 'APPROVED' || req.status === 'EXECUTED'
                        ? 'bg-[#43B581]/15 text-[#43B581]'
                        : 'bg-[#E05252]/15 text-[#E05252]'
                    }`}>
                      {req.status}
                    </span>
                  </div>

                  <p className="text-xs text-[#9DA7B5] font-sans">
                    {req.operation_description}
                  </p>

                  {/* Dual approval review details */}
                  {req.first_approver_name && (
                    <div className="text-[11px] text-[#48B9D0] bg-[#101216] p-2 border border-[#303640] rounded flex items-center gap-2">
                      <CheckCircle className="w-3.5 h-3.5 text-[#43B581]" />
                      <span>Stage 1 Sign-off: <strong>{req.first_approver_name}</strong> {req.first_approved_at && `(${new Date(req.first_approved_at).toLocaleTimeString()})`}</span>
                      {req.status === 'PARTIALLY_APPROVED' && (
                        <span className="text-[#F0A43A] ml-2">-- Awaiting second distinct administrator sign-off</span>
                      )}
                    </div>
                  )}

                  <div className="flex flex-wrap items-center gap-4 text-[11px] text-[#626D7C] pt-1">
                    <span className="flex items-center gap-1">
                      <User className="w-3 h-3 text-[#F0A43A]" /> Requester: {req.requesting_user}
                    </span>
                    <span className="flex items-center gap-1">
                      <Server className="w-3 h-3 text-[#48B9D0]" /> Server: {req.server_name}
                    </span>
                    {req.agent_name && (
                      <span className="flex items-center gap-1">
                        <Bot className="w-3 h-3 text-[#43B581]" /> Agent: {req.agent_name}
                      </span>
                    )}
                    <span className="text-[#626D7C]">
                      Created: {new Date(req.created_at).toLocaleString()}
                    </span>
                    {req.expires_at && (
                      <span className="text-[#EBB346]">
                        Expires: {new Date(req.expires_at).toLocaleTimeString()}
                      </span>
                    )}
                  </div>

                  {req.parameters && Object.keys(req.parameters).length > 0 && (
                    <div className="mt-2 p-2 bg-[#101216] border border-[#303640] rounded text-[11px] text-[#ECEFF4] max-w-xl">
                      <span className="text-[#626D7C]">Arguments: </span>
                      {JSON.stringify(req.parameters)}
                    </div>
                  )}
                </div>

                {/* Actions */}
                {(req.status === 'PENDING' || req.status === 'PARTIALLY_APPROVED') && (
                  <div className="flex items-center gap-2 self-start md:self-center">
                    <button
                      onClick={() => handleAction(req.id, 'APPROVE')}
                      disabled={reviewMutation.isPending}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-[#43B581] hover:bg-[#43B581]/90 text-[#101216] font-bold rounded text-xs transition-colors"
                    >
                      <Check className="w-3.5 h-3.5" />
                      {req.status === 'PARTIALLY_APPROVED' ? 'Final Sign-off & Execute' : (req.requires_dual_approval ? 'Provide 1st Approval' : 'Approve & Execute')}
                    </button>
                    <button
                      onClick={() => handleAction(req.id, 'REJECT')}
                      disabled={reviewMutation.isPending}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-[#181C23] hover:bg-[#E05252]/20 border border-[#303640] hover:border-[#E05252] text-[#E05252] font-semibold rounded text-xs transition-colors"
                    >
                      <X className="w-3.5 h-3.5" />
                      Reject
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
