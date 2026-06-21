'use client';

import Link from 'next/link';
import {
  MessageSquare,
  LayoutDashboard,
  Users,
  Settings,
  Bot,
  Wrench,
  BarChart3,
  FileText,
  Cable,
} from 'lucide-react';
import { usePathname } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { useAuthStore } from '@/lib/store/useAuthStore';
import { authApi } from '@/lib/api/auth';
import clsx from 'clsx';

const NAV_LINKS = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Chat', href: '/chat', icon: MessageSquare },
  { name: 'Profiles', href: '/profiles', icon: Bot },
  { name: 'Prompts', href: '/prompts', icon: FileText },
  { name: 'MCP', href: '/mcp', icon: Cable },
  { name: 'Tools', href: '/tools', icon: Wrench },
  { name: 'Users', href: '/users', icon: Users },
  { name: 'Analytics', href: '/analytics', icon: BarChart3 },
  { name: 'Settings', href: '/settings', icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user } = useAuthStore();

  // Fetch the user's active profile for the sidebar footer
  const { data: activeProfile } = useQuery({
    queryKey: ['userProfile', user?.id],
    queryFn: () => authApi.getUserProfile(user!.id),
    enabled: !!user?.id,
    staleTime: 60_000,
  });

  return (
    <aside className="w-[260px] h-screen fixed top-0 left-0 border-r border-zinc-800 bg-[#0A0A0A] flex flex-col">
      <div className="h-14 flex items-center px-5 font-semibold text-base border-b border-zinc-800 tracking-tight">
        PAT Portal
      </div>

      <nav className="flex-1 overflow-y-auto p-3 space-y-0.5">
        {NAV_LINKS.map((link) => {
          const Icon = link.icon;
          const isActive = link.href === '/'
            ? pathname === '/'
            : pathname.startsWith(link.href);

          return (
            <Link
              key={link.name}
              href={link.href}
              className={clsx(
                'flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors',
                isActive
                  ? 'bg-zinc-800 text-white font-medium'
                  : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50'
              )}
            >
              <Icon size={17} />
              {link.name}
            </Link>
          );
        })}
      </nav>

      <div className="p-4 border-t border-zinc-800">
        {activeProfile ? (
          <div className="flex flex-col gap-0.5 text-sm">
            <span className="text-zinc-500 text-xs">Active Profile</span>
            <span className="text-zinc-200 font-medium truncate">{activeProfile.name}</span>
            <span className="text-zinc-500 text-xs">{activeProfile.model_name}</span>
          </div>
        ) : (
          <div className="text-xs text-zinc-600">No profile assigned</div>
        )}
      </div>
    </aside>
  );
}
