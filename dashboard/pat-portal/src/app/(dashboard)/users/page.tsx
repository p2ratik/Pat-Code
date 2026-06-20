'use client';

// In a real app we'd fetch users, but the API guide doesn't list a GET /users endpoint.
// We'll mock it for the UI structure based on the design.

import { Users as UsersIcon, Shield, MoreHorizontal } from 'lucide-react';

const MOCK_USERS = [
  { id: '1', name: 'Pratik', email: 'pratik@example.com', role: 'Super Admin', status: 'Active', profile: 'Research Agent' },
  { id: '2', name: 'Alice', email: 'alice@example.com', role: 'User', status: 'Active', profile: 'Customer Support' },
];

export default function UsersPage() {
  return (
    <div className="p-8 max-w-6xl mx-auto space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Users</h1>
          <p className="text-sm text-zinc-400 mt-1">Manage team access and agent assignments.</p>
        </div>
        <button className="bg-zinc-100 hover:bg-white text-zinc-900 px-4 py-2 rounded-md text-sm font-medium transition-colors">
          Add User
        </button>
      </div>

      <div className="border border-zinc-800 rounded-xl overflow-hidden bg-[#0A0A0A]">
        <table className="w-full text-left text-sm">
          <thead className="bg-zinc-900/50 text-zinc-400 border-b border-zinc-800">
            <tr>
              <th className="px-6 py-4 font-medium">User</th>
              <th className="px-6 py-4 font-medium">Role</th>
              <th className="px-6 py-4 font-medium">Status</th>
              <th className="px-6 py-4 font-medium">Active Profile</th>
              <th className="px-6 py-4 font-medium text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800">
            {MOCK_USERS.map((user) => (
              <tr key={user.id} className="hover:bg-zinc-900/20 transition-colors">
                <td className="px-6 py-4">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-zinc-800 flex items-center justify-center text-xs font-medium text-zinc-300">
                      {user.name[0]}
                    </div>
                    <div>
                      <div className="font-medium text-zinc-200">{user.name}</div>
                      <div className="text-xs text-zinc-500">{user.email}</div>
                    </div>
                  </div>
                </td>
                <td className="px-6 py-4">
                  <span className="flex items-center gap-1.5 text-zinc-300">
                    {user.role === 'Super Admin' && <Shield size={14} className="text-blue-500" />}
                    {user.role}
                  </span>
                </td>
                <td className="px-6 py-4">
                  <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-medium bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">
                    {user.status}
                  </span>
                </td>
                <td className="px-6 py-4 text-zinc-400">
                  {user.profile}
                </td>
                <td className="px-6 py-4 text-right">
                  <button className="text-zinc-500 hover:text-zinc-300 p-1 rounded transition-colors">
                    <MoreHorizontal size={16} />
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
