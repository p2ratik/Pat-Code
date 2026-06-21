'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { authApi, User } from '@/lib/api/auth';
import { profilesApi } from '@/lib/api/profiles';
import { Shield, MoreHorizontal, Plus, X, Loader2 } from 'lucide-react';
import { format } from 'date-fns';

function AddUserModal({ onClose }: { onClose: () => void }) {
  const [email, setEmail] = useState('');
  const [displayName, setDisplayName] = useState('');
  const qc = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => authApi.createUser(email, displayName),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] });
      onClose();
    },
  });

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl w-full max-w-md p-6 shadow-2xl">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-base font-semibold text-white">Add User</h2>
          <button onClick={onClose} className="text-zinc-500 hover:text-zinc-200 transition-colors">
            <X size={18} />
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">Display Name</label>
            <input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Pratik"
              className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-zinc-500 placeholder-zinc-600"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="user@example.com"
              className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-zinc-500 placeholder-zinc-600"
            />
          </div>
        </div>

        {mutation.isError && (
          <p className="mt-4 text-xs text-red-400">
            {(mutation.error as any)?.response?.data?.detail || 'Something went wrong.'}
          </p>
        )}

        <div className="flex justify-end gap-3 mt-6">
          <button onClick={onClose} className="px-4 py-2 text-sm text-zinc-400 hover:text-zinc-200 transition-colors">
            Cancel
          </button>
          <button
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending || !email || !displayName}
            className="flex items-center gap-2 px-4 py-2 bg-zinc-100 text-zinc-900 text-sm font-medium rounded-md hover:bg-white transition-colors disabled:opacity-50"
          >
            {mutation.isPending && <Loader2 size={14} className="animate-spin" />}
            Create User
          </button>
        </div>
      </div>
    </div>
  );
}

function AssignProfileModal({ user, onClose }: { user: User; onClose: () => void }) {
  const [profileId, setProfileId] = useState('');
  const qc = useQueryClient();

  const { data: profiles } = useQuery({
    queryKey: ['profiles'],
    queryFn: profilesApi.getProfiles,
  });

  const mutation = useMutation({
    mutationFn: () => authApi.assignProfile(user.id, profileId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] });
      onClose();
    },
  });

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl w-full max-w-md p-6 shadow-2xl">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-base font-semibold text-white">Assign Profile</h2>
            <p className="text-xs text-zinc-500 mt-0.5">{user.display_name}</p>
          </div>
          <button onClick={onClose} className="text-zinc-500 hover:text-zinc-200 transition-colors">
            <X size={18} />
          </button>
        </div>

        <div>
          <label className="block text-xs font-medium text-zinc-400 mb-1.5">Select Profile</label>
          <select
            value={profileId}
            onChange={(e) => setProfileId(e.target.value)}
            className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-zinc-500"
          >
            <option value="">-- Select a profile --</option>
            {profiles?.map(p => (
              <option key={p.id} value={p.id}>{p.name} ({p.model_name})</option>
            ))}
          </select>
        </div>

        {mutation.isError && (
          <p className="mt-4 text-xs text-red-400">
            {(mutation.error as any)?.response?.data?.detail || 'Failed to assign profile.'}
          </p>
        )}

        <div className="flex justify-end gap-3 mt-6">
          <button onClick={onClose} className="px-4 py-2 text-sm text-zinc-400 hover:text-zinc-200 transition-colors">
            Cancel
          </button>
          <button
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending || !profileId}
            className="flex items-center gap-2 px-4 py-2 bg-zinc-100 text-zinc-900 text-sm font-medium rounded-md hover:bg-white transition-colors disabled:opacity-50"
          >
            {mutation.isPending && <Loader2 size={14} className="animate-spin" />}
            Assign
          </button>
        </div>
      </div>
    </div>
  );
}

export default function UsersPage() {
  const [showAddModal, setShowAddModal] = useState(false);
  const [assignTarget, setAssignTarget] = useState<User | null>(null);

  const { data: users, isLoading, isError } = useQuery({
    queryKey: ['users'],
    queryFn: authApi.listUsers,
  });

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-8">
      {showAddModal && <AddUserModal onClose={() => setShowAddModal(false)} />}
      {assignTarget && <AssignProfileModal user={assignTarget} onClose={() => setAssignTarget(null)} />}

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Users</h1>
          <p className="text-sm text-zinc-400 mt-1">
            {isLoading ? 'Loading...' : `${users?.length ?? 0} users in the system.`}
          </p>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="flex items-center gap-2 bg-zinc-100 hover:bg-white text-zinc-900 px-4 py-2 rounded-md text-sm font-medium transition-colors"
        >
          <Plus size={16} />
          Add User
        </button>
      </div>

      <div className="border border-zinc-800 rounded-xl overflow-hidden bg-[#0A0A0A]">
        <table className="w-full text-left text-sm">
          <thead className="bg-zinc-900/50 text-zinc-400 border-b border-zinc-800">
            <tr>
              <th className="px-6 py-4 font-medium">User</th>
              <th className="px-6 py-4 font-medium">Roles</th>
              <th className="px-6 py-4 font-medium">Status</th>
              <th className="px-6 py-4 font-medium">Joined</th>
              <th className="px-6 py-4 font-medium text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800">
            {isLoading && (
              <tr>
                <td colSpan={5} className="px-6 py-10 text-center text-zinc-500">
                  <Loader2 size={20} className="animate-spin mx-auto" />
                </td>
              </tr>
            )}
            {isError && (
              <tr>
                <td colSpan={5} className="px-6 py-10 text-center text-red-400 text-xs">
                  Failed to load users.
                </td>
              </tr>
            )}
            {users?.map((user) => (
              <tr key={user.id} className="hover:bg-zinc-900/20 transition-colors">
                <td className="px-6 py-4">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-zinc-800 flex items-center justify-center text-xs font-medium text-zinc-300 shrink-0">
                      {user.display_name[0]?.toUpperCase()}
                    </div>
                    <div>
                      <div className="font-medium text-zinc-200">{user.display_name}</div>
                      <div className="text-xs text-zinc-500">{user.email}</div>
                    </div>
                  </div>
                </td>
                <td className="px-6 py-4">
                  {user.roles.length > 0 ? (
                    <div className="flex flex-wrap gap-1">
                      {user.roles.map(r => (
                        <span key={r} className="flex items-center gap-1 text-xs px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 border border-zinc-700">
                          {r.includes('admin') && <Shield size={11} className="text-blue-400" />}
                          {r}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <span className="text-xs text-zinc-600">No roles</span>
                  )}
                </td>
                <td className="px-6 py-4">
                  {user.is_active ? (
                    <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-medium bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">
                      Active
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-medium bg-zinc-800 text-zinc-400 border border-zinc-700">
                      Disabled
                    </span>
                  )}
                </td>
                <td className="px-6 py-4 text-zinc-400 text-xs">
                  {format(new Date(user.created_at), 'MMM d, yyyy')}
                </td>
                <td className="px-6 py-4 text-right">
                  <button
                    onClick={() => setAssignTarget(user)}
                    className="text-xs text-zinc-400 hover:text-white border border-zinc-800 hover:border-zinc-600 px-2.5 py-1 rounded transition-colors"
                  >
                    Assign Profile
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
