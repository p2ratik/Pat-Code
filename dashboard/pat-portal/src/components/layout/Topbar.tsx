'use client';

import { useAuthStore } from '@/lib/store/useAuthStore';
import { LogOut } from 'lucide-react';

export function Topbar() {
  const { user, logout } = useAuthStore();

  return (
    <header className="h-14 border-b border-zinc-800 bg-[#0A0A0A] flex items-center justify-between px-6 sticky top-0 z-10">
      <div className="flex items-center gap-4">
        {/* Breadcrumbs or Context here */}
        <div className="text-sm font-medium flex items-center gap-2">
          <span className="text-zinc-400">PAT</span>
          <span className="text-zinc-600">/</span>
          <span className="text-zinc-200">Research Agent</span>
          <span className="text-zinc-600">/</span>
          <span className="text-zinc-400">GPT-4.1-mini</span>
        </div>
      </div>
      
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
          <span className="text-sm text-zinc-400">Online</span>
        </div>
        
        {user && (
          <div className="flex items-center gap-3 border-l border-zinc-800 pl-4">
            <span className="text-sm text-zinc-300">{user.display_name}</span>
            <button 
              onClick={() => {
                logout();
                window.location.href = '/login';
              }}
              className="text-zinc-400 hover:text-white p-1 rounded-md transition-colors"
            >
              <LogOut size={16} />
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
