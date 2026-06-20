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
  Search
} from 'lucide-react';
import { usePathname } from 'next/navigation';
import clsx from 'clsx';

export function Sidebar() {
  const pathname = usePathname();

  const links = [
    { name: 'Dashboard', href: '/', icon: LayoutDashboard },
    { name: 'Chat', href: '/chat', icon: MessageSquare },
    { name: 'Profiles', href: '/profiles', icon: Bot },
    { name: 'Tools', href: '/tools', icon: Wrench },
    { name: 'Users', href: '/users', icon: Users },
    { name: 'Analytics', href: '/analytics', icon: BarChart3 },
    { name: 'Settings', href: '/settings', icon: Settings },
  ];

  return (
    <aside className="w-[260px] h-screen fixed top-0 left-0 border-r border-zinc-800 bg-[#0A0A0A] flex flex-col">
      <div className="h-14 flex items-center px-4 font-semibold text-lg border-b border-zinc-800">
        PAT Portal
      </div>
      
      <div className="p-3">
        <div className="flex items-center gap-2 px-3 py-1.5 text-zinc-400 bg-zinc-900 rounded-md border border-zinc-800 text-sm">
          <Search size={16} />
          <span>Search (Ctrl+K)</span>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto p-3 space-y-1">
        {links.map((link) => {
          const Icon = link.icon;
          const isActive = pathname === link.href || (pathname.startsWith(link.href) && link.href !== '/');
          
          return (
            <Link 
              key={link.name} 
              href={link.href}
              className={clsx(
                "flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors",
                isActive ? "bg-zinc-800 text-white font-medium" : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50"
              )}
            >
              <Icon size={18} />
              {link.name}
            </Link>
          );
        })}
      </nav>
      
      <div className="p-4 border-t border-zinc-800">
        <div className="flex flex-col gap-1 text-sm">
          <span className="text-zinc-400">Current Profile</span>
          <span className="text-zinc-200 font-medium">Research Agent</span>
          <span className="text-zinc-500 text-xs mt-1">GPT-4.1-mini</span>
        </div>
      </div>
    </aside>
  );
}
