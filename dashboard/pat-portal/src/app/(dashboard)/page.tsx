'use client';

import { useQuery } from '@tanstack/react-query';
import { profilesApi } from '@/lib/api/profiles';
import { toolsApi } from '@/lib/api/tools';
import { authApi } from '@/lib/api/auth';
import { MessageSquare, Bot, Wrench, Users } from 'lucide-react';
import Link from 'next/link';
import { useAuthStore } from '@/lib/store/useAuthStore';

function StatCard({ label, value, sub, icon: Icon }: {
  label: string; value: string | number; sub: string; icon: React.ElementType;
}) {
  return (
    <div className="p-6 rounded-xl border border-zinc-800 bg-zinc-900/50 flex flex-col gap-2">
      <div className="text-zinc-400 text-sm font-medium flex items-center gap-2">
        <Icon size={16} />{label}
      </div>
      <div className="text-3xl font-semibold text-white">{value}</div>
      <div className="text-xs text-zinc-500">{sub}</div>
    </div>
  );
}

export default function DashboardPage() {
  const { user } = useAuthStore();

  const { data: profiles } = useQuery({ queryKey: ['profiles'], queryFn: profilesApi.getProfiles });
  const { data: tools } = useQuery({ queryKey: ['tools'], queryFn: toolsApi.getTools });
  const { data: users } = useQuery({ queryKey: ['users'], queryFn: authApi.listUsers });

  // Derive active profile from the user list (approximate for dashboard)
  const activeProfile = profiles?.[0];

  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good Morning' : hour < 18 ? 'Good Afternoon' : 'Good Evening';

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight text-white">
          {greeting}{user?.display_name ? `, ${user.display_name}` : ''}
        </h1>
        <p className="text-zinc-400 mt-2">
          {activeProfile ? (
            <><span className="text-emerald-500 font-medium">{activeProfile.name}</span> is the active profile.</>
          ) : 'No active profile assigned.'}
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard label="Profiles" value={profiles?.length ?? '—'} sub="Configured" icon={Bot} />
        <StatCard label="Tools" value={tools?.length ?? '—'} sub="In registry" icon={Wrench} />
        <StatCard label="Users" value={users?.length ?? '—'} sub="Total" icon={Users} />
        <StatCard
          label="Current Model"
          value={activeProfile?.model_name ?? '—'}
          sub={activeProfile ? `temp ${activeProfile.temperature}` : 'No profile'}
          icon={MessageSquare}
        />
      </div>

      <div className="pt-2">
        <h2 className="text-base font-medium text-zinc-200 mb-4">Quick Actions</h2>
        <div className="flex flex-wrap gap-3">
          <Link href="/chat" className="px-4 py-2 bg-zinc-100 text-zinc-900 font-medium rounded-md hover:bg-white transition-colors text-sm">
            + New Chat
          </Link>
          <Link href="/profiles" className="px-4 py-2 border border-zinc-800 text-zinc-300 font-medium rounded-md hover:bg-zinc-800 transition-colors text-sm">
            Manage Profiles
          </Link>
          <Link href="/tools" className="px-4 py-2 border border-zinc-800 text-zinc-300 font-medium rounded-md hover:bg-zinc-800 transition-colors text-sm">
            Configure Tools
          </Link>
          <Link href="/users" className="px-4 py-2 border border-zinc-800 text-zinc-300 font-medium rounded-md hover:bg-zinc-800 transition-colors text-sm">
            Manage Users
          </Link>
        </div>
      </div>
    </div>
  );
}
