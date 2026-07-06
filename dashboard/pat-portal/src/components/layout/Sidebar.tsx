"use client";

import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import {
  Activity,
  Bot,
  Box,
  ChevronDown,
  Plus,
  Search,
  Settings,
  Terminal,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { authApi } from "@/lib/api/auth";
import { profilesApi } from "@/lib/api/profiles";
import { useAuthStore } from "@/lib/store/useAuthStore";

export function Sidebar() {
  const pathname = usePathname();
  const { user } = useAuthStore();

  const { data: activeProfile } = useQuery({
    queryKey: ["userProfile", user?.id],
    queryFn: () => authApi.getUserProfile(user!.id),
    enabled: !!user?.id,
    staleTime: 60_000,
  });

  const { data: profiles } = useQuery({
    queryKey: ["profiles"],
    queryFn: profilesApi.getProfiles,
  });

  return (
    <aside className="w-[260px] h-screen fixed top-0 left-0 border-r border-zinc-800 bg-[#0A0A0A] flex flex-col z-20">
      <div className="h-14 flex items-center px-5 font-semibold text-base border-b border-zinc-800 tracking-tight gap-2 text-zinc-100">
        <Box size={18} className="text-emerald-500" />
        PAT Platform
      </div>

      <nav className="flex-1 overflow-y-auto p-4 space-y-6">
        {/* Main Navigation */}
        <div className="space-y-1">
          <Link
            href="/"
            className={clsx(
              "flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors",
              pathname === "/"
                ? "bg-zinc-800 text-white font-medium"
                : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50",
            )}
          >
            <Bot size={16} />
            Agents
          </Link>
          <button
            onClick={() => {
              // Trigger command palette later
              const event = new KeyboardEvent("keydown", {
                key: "k",
                ctrlKey: true,
              });
              document.dispatchEvent(event);
            }}
            className="w-full flex items-center justify-between px-3 py-2 rounded-md text-sm text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50 transition-colors"
          >
            <div className="flex items-center gap-3">
              <Search size={16} />
              Search
            </div>
            <div className="flex items-center gap-1 text-[10px] bg-zinc-800 px-1.5 py-0.5 rounded text-zinc-500 font-medium">
              <span>⌘</span>K
            </div>
          </button>
          <button
            onClick={() => {
              import('@/lib/store/useUIStore').then(m => m.useUIStore.getState().setCreateAgentOpen(true));
            }}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-md text-sm text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50 transition-colors"
          >
            <Plus size={16} />
            Create Agent
          </button>
        </div>

        {/* Recent Agents */}
        <div>
          <div className="px-3 text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-2 flex items-center justify-between">
            Recent Agents
            <ChevronDown size={14} />
          </div>
          <div className="space-y-0.5">
            {profiles?.slice(0, 5).map((profile) => (
              <Link
                key={profile.id}
                href={`/?agent=${profile.id}`}
                className={clsx(
                  "flex items-center gap-3 px-3 py-2 rounded-md text-sm text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50 transition-colors",
                  activeProfile?.id === profile.id &&
                    pathname === "/" &&
                    "text-zinc-200",
                )}
              >
                <div className="w-2 h-2 rounded-full bg-emerald-500/50" />
                <span className="truncate">{profile.name}</span>
              </Link>
            ))}
            {!profiles?.length && (
              <div className="px-3 py-2 text-sm text-zinc-600 italic">
                No agents found
              </div>
            )}
          </div>
        </div>

        {/* System */}
        <div>
          <div className="px-3 text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-2">
            System
          </div>
          <div className="space-y-0.5">
            <Link
              href="/chat"
              className="flex items-center gap-3 px-3 py-2 rounded-md text-sm text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50 transition-colors"
            >
              <Terminal size={16} /> Terminal
            </Link>
            <Link
              href="/analytics"
              className="flex items-center gap-3 px-3 py-2 rounded-md text-sm text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50 transition-colors"
            >
              <Activity size={16} /> Monitoring
            </Link>
            <Link
              href="/settings"
              className="flex items-center gap-3 px-3 py-2 rounded-md text-sm text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50 transition-colors"
            >
              <Settings size={16} /> Settings
            </Link>
          </div>
        </div>
      </nav>

      <div className="p-4 border-t border-zinc-800">
        {user ? (
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-zinc-800 flex items-center justify-center text-zinc-400 font-medium text-xs border border-zinc-700">
              {user.display_name?.charAt(0) || "U"}
            </div>
            <div className="flex flex-col flex-1 min-w-0">
              <span className="text-zinc-200 text-sm font-medium truncate">
                {user.display_name}
              </span>
              <span className="text-zinc-500 text-xs truncate">
                {user.email}
              </span>
            </div>
          </div>
        ) : null}
      </div>
    </aside>
  );
}
