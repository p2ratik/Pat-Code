"use client";

import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { Bell, CheckCircle2, Loader2, LogOut } from "lucide-react";
import { authApi } from "@/lib/api/auth";
import { useAuthStore } from "@/lib/store/useAuthStore";

export function Topbar() {
  const { user, logout } = useAuthStore();

  const { data: activeProfile } = useQuery({
    queryKey: ["userProfile", user?.id],
    queryFn: () => authApi.getUserProfile(user!.id),
    enabled: !!user?.id,
    staleTime: 60_000,
  });

  // Mock run status for UI demonstration
  const runStatus = "idle"; // idle, running, complete

  return (
    <header className="h-14 border-b border-zinc-800 bg-[#0A0A0A] flex items-center justify-between px-6 sticky top-0 z-10 shrink-0">
      <div className="flex items-center gap-2 text-sm">
        <span className="text-zinc-400 font-medium bg-zinc-800/50 px-2 py-1 rounded-md text-xs">
          Workspace
        </span>

        {activeProfile && (
          <>
            <span className="text-zinc-700">/</span>
            <span className="text-zinc-200 font-medium">
              {activeProfile.name}
            </span>
            <span className="text-zinc-700">/</span>
            <span className="text-zinc-500 font-mono text-xs bg-zinc-900 px-1.5 py-0.5 rounded border border-zinc-800">
              {activeProfile.model_name}
            </span>
          </>
        )}
      </div>

      <div className="flex items-center gap-4">
        {/* Run Status (Future feature visualization) */}
        <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-zinc-900 border border-zinc-800">
          {runStatus === "running" ? (
            <Loader2 size={12} className="text-emerald-500 animate-spin" />
          ) : runStatus === "complete" ? (
            <CheckCircle2 size={12} className="text-emerald-500" />
          ) : (
            <div className="w-2 h-2 rounded-full bg-zinc-600" />
          )}
          <span
            className={clsx(
              "text-xs font-medium",
              runStatus === "running" ? "text-emerald-400" : "text-zinc-400",
            )}
          >
            {runStatus === "running" ? "Agent Thinking..." : "Agent Idle"}
          </span>
        </div>

        <button className="text-zinc-400 hover:text-white relative p-1.5 rounded-md hover:bg-zinc-800 transition-colors">
          <Bell size={16} />
          <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full bg-emerald-500" />
        </button>

        {user && (
          <div className="flex items-center gap-3 border-l border-zinc-800 pl-4 ml-1">
            <button
              onClick={() => {
                logout();
                window.location.href = "/login";
              }}
              className="text-zinc-500 hover:text-red-400 p-1.5 rounded-md transition-colors flex items-center gap-2 text-sm font-medium"
              title="Sign out"
            >
              <LogOut size={15} />
              Logout
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
