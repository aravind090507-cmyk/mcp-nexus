import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../services/api';
import { Users, Plus, Shield, Check, X, User } from 'lucide-react';

export const UserManagement: React.FC = () => {
  const queryClient = useQueryClient();
  const [showAddModal, setShowAddModal] = useState(false);
  const [formData, setFormData] = useState({
    email: '',
    full_name: '',
    password: '',
    role: 'OPERATOR',
    department: 'Operations',
  });

  const { data: users, isLoading } = useQuery({
    queryKey: ['enterprise-users'],
    queryFn: () => api.getUsers(),
  });

  const createMutation = useMutation({
    mutationFn: (payload: any) => api.createUser(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['enterprise-users'] });
      setShowAddModal(false);
      setFormData({
        email: '',
        full_name: '',
        password: '',
        role: 'OPERATOR',
        department: 'Operations',
      });
    },
    onError: (err: any) => alert(`Error creating user: ${err.message}`),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    createMutation.mutate(formData);
  };

  return (
    <div className="space-y-6 font-mono">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#303640] pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-[#ECEFF4]">
              USER & IDENTITY MANAGEMENT
            </h1>
            <span className="text-[11px] px-2 py-0.5 rounded bg-[#48B9D0]/15 text-[#48B9D0] border border-[#48B9D0]/30">
              ENTERPRISE ROSTER
            </span>
          </div>
          <p className="text-xs text-[#9DA7B5] mt-1 font-sans">
            Provision and assign least-privilege enterprise roles to engineers, administrators, and site operators.
          </p>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="flex items-center gap-2 px-3.5 py-1.5 bg-[#F0A43A] hover:bg-[#F0A43A]/90 text-[#101216] font-semibold rounded text-xs transition-colors"
        >
          <Plus className="w-4 h-4" />
          Provision Enterprise User
        </button>
      </div>

      {/* Users Table */}
      <div className="bg-[#14171D] border border-[#303640] rounded overflow-hidden">
        <table className="w-full text-left text-xs">
          <thead className="bg-[#181C23] text-[#9DA7B5] border-b border-[#303640]">
            <tr>
              <th className="py-2.5 px-3">Name</th>
              <th className="py-2.5 px-3">Corporate Email</th>
              <th className="py-2.5 px-3">Department</th>
              <th className="py-2.5 px-3">RBAC Role</th>
              <th className="py-2.5 px-3">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#303640]">
            {isLoading ? (
              <tr>
                <td colSpan={5} className="py-8 text-center text-[#9DA7B5]">
                  Reading enterprise user directory...
                </td>
              </tr>
            ) : (
              (users || []).map((u) => (
                <tr key={u.id} className="hover:bg-[#181C23]/40">
                  <td className="py-2.5 px-3 font-bold text-[#ECEFF4]">{u.full_name}</td>
                  <td className="py-2.5 px-3 text-[#48B9D0]">{u.email}</td>
                  <td className="py-2.5 px-3 text-[#9DA7B5]">{u.department || 'Operations'}</td>
                  <td className="py-2.5 px-3">
                    <span className="px-2 py-0.5 bg-[#181C23] border border-[#303640] rounded text-[10px] text-[#F0A43A] font-bold">
                      {u.role}
                    </span>
                  </td>
                  <td className="py-2.5 px-3">
                    <span className="text-[#43B581] font-bold">● Active</span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Provision User Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#14171D] border border-[#303640] rounded-lg max-w-md w-full p-6 space-y-4 font-mono shadow-2xl">
            <div className="flex items-center justify-between border-b border-[#303640] pb-2 text-xs">
              <span className="font-bold text-[#ECEFF4]">Provision Enterprise User</span>
              <button onClick={() => setShowAddModal(false)}>
                <X className="w-4 h-4 text-[#626D7C]" />
              </button>
            </div>
            <form onSubmit={handleSubmit} className="space-y-3 text-xs">
              <div>
                <label className="text-[10px] text-[#626D7C] uppercase">Full Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. S. Ramanathan"
                  value={formData.full_name}
                  onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                  className="w-full mt-1 bg-[#181C23] border border-[#303640] rounded p-2 text-[#ECEFF4]"
                />
              </div>
              <div>
                <label className="text-[10px] text-[#626D7C] uppercase">Email</label>
                <input
                  type="email"
                  required
                  placeholder="s.ramanathan@lt.corp"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  className="w-full mt-1 bg-[#181C23] border border-[#303640] rounded p-2 text-[#ECEFF4]"
                />
              </div>
              <div>
                <label className="text-[10px] text-[#626D7C] uppercase">Password</label>
                <input
                  type="password"
                  required
                  placeholder="Password"
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  className="w-full mt-1 bg-[#181C23] border border-[#303640] rounded p-2 text-[#ECEFF4]"
                />
              </div>
              <div>
                <label className="text-[10px] text-[#626D7C] uppercase">Role</label>
                <select
                  value={formData.role}
                  onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                  className="w-full mt-1 bg-[#181C23] border border-[#303640] rounded p-2 text-[#ECEFF4]"
                >
                  <option value="SUPER_ADMIN">SUPER_ADMIN</option>
                  <option value="ADMIN">ADMIN</option>
                  <option value="DEVELOPER">DEVELOPER</option>
                  <option value="OPERATOR">OPERATOR</option>
                  <option value="VIEWER">VIEWER</option>
                </select>
              </div>
              <div className="flex justify-end gap-2 pt-2 border-t border-[#303640]">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-3 py-1.5 bg-[#181C23] border border-[#303640] rounded text-[#ECEFF4]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending}
                  className="px-3 py-1.5 bg-[#F0A43A] text-[#101216] font-bold rounded"
                >
                  Save User
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
