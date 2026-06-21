'use client';

import { useAuthStore } from '@/lib/store/useAuthStore';
import { useQuery } from '@tanstack/react-query';
import { authApi } from '@/lib/api/auth';
import { LogOut } from 'lucide-react';

export function Topbar() {
  const { user, logout } = useAuthStore();

  const { data: activeProfile } = useQuery({
    queryKey: ['userProfile', user?.id],
    queryFn: () => authApi.getUserProfile(user!.id),
    enabled: !!user?.id,
    staleTime: 60_000,
  });

  return (
    <header className="h-14 border-b border-zinc-800 bg-[#0A0A0A] flex items-center justify-between px-6 sticky top-0 z-10">
      <div className="flex items-center gap-2 text-sm">
        <span className="text-zinc-500">PAT</span>
        {activeProfile && (
          <>
            <span className="text-zinc-700">/</span>
            <span className="text-zinc-300 font-medium">{activeProfile.name}</span>
            <span className="text-zinc-700">/</span>
            <span className="text-zinc-500">{activeProfile.model_name}</span>
          </>
        )}
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-500" />
          <span className="text-sm text-zinc-400">Online</span>
        </div>

        {user && (
          <div className="flex items-center gap-3 border-l border-zinc-800 pl-4">
            <div className="text-right">
              <div className="text-sm text-zinc-300 font-medium">{user.display_name}</div>
              <div className="text-xs text-zinc-600">{user.email}</div>
            </div>
            <button
              onClick={() => { logout(); window.location.href = '/login'; }}
              className="text-zinc-500 hover:text-white p-1.5 rounded-md transition-colors"
              title="Sign out"
            >
              <LogOut size={15} />
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
