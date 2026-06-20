'use client';

import { useQuery } from '@tanstack/react-query';
import { profilesApi } from '@/lib/api/profiles';
import { toolsApi } from '@/lib/api/tools';
import { MessageSquare, Bot, Wrench, Activity } from 'lucide-react';
import Link from 'next/link';
import { useAuthStore } from '@/lib/store/useAuthStore';

export default function DashboardPage() {
  const { user } = useAuthStore();
  
  const { data: profiles } = useQuery({
    queryKey: ['profiles'],
    queryFn: profilesApi.getProfiles,
  });

  const { data: tools } = useQuery({
    queryKey: ['tools'],
    queryFn: toolsApi.getTools,
  });

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight text-white">
          Good Evening{user?.display_name ? `, ${user.display_name}` : ''}
        </h1>
        <p className="text-zinc-400 mt-2">
          <span className="text-emerald-500 font-medium">Research Agent</span> is currently active.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="p-6 rounded-xl border border-zinc-800 bg-zinc-900/50 flex flex-col gap-2">
          <div className="text-zinc-400 text-sm font-medium flex items-center gap-2">
            <MessageSquare size={16} />
            Conversations
          </div>
          <div className="text-3xl font-semibold text-white">154</div>
          <div className="text-xs text-zinc-500">Today</div>
        </div>

        <div className="p-6 rounded-xl border border-zinc-800 bg-zinc-900/50 flex flex-col gap-2">
          <div className="text-zinc-400 text-sm font-medium flex items-center gap-2">
            <Activity size={16} />
            Messages
          </div>
          <div className="text-3xl font-semibold text-white">21</div>
          <div className="text-xs text-zinc-500">Today</div>
        </div>

        <div className="p-6 rounded-xl border border-zinc-800 bg-zinc-900/50 flex flex-col gap-2">
          <div className="text-zinc-400 text-sm font-medium flex items-center gap-2">
            <Wrench size={16} />
            Tools Enabled
          </div>
          <div className="text-3xl font-semibold text-white">{tools?.length || 0}</div>
          <div className="text-xs text-zinc-500">In registry</div>
        </div>

        <div className="p-6 rounded-xl border border-zinc-800 bg-zinc-900/50 flex flex-col gap-2">
          <div className="text-zinc-400 text-sm font-medium flex items-center gap-2">
            <Bot size={16} />
            Current Model
          </div>
          <div className="text-xl font-semibold text-white mt-1">GPT-4.1-mini</div>
          <div className="text-xs text-zinc-500">Active Profile</div>
        </div>
      </div>

      <div className="pt-6">
        <h2 className="text-xl font-semibold text-white mb-4">Quick Actions</h2>
        <div className="flex flex-wrap gap-4">
          <Link href="/chat" className="px-4 py-2 bg-zinc-100 text-zinc-900 font-medium rounded-md hover:bg-white transition-colors">
            + New Chat
          </Link>
          <Link href="/profiles" className="px-4 py-2 border border-zinc-800 text-zinc-300 font-medium rounded-md hover:bg-zinc-800 transition-colors">
            Manage Profiles
          </Link>
          <Link href="/tools" className="px-4 py-2 border border-zinc-800 text-zinc-300 font-medium rounded-md hover:bg-zinc-800 transition-colors">
            Configure Tools
          </Link>
        </div>
      </div>
    </div>
  );
}
