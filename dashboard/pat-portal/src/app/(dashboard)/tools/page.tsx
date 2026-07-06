"use client";

import { useState, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Wrench, Plug, CheckCircle2, XCircle, Loader2,
  RefreshCw, LogOut, AlertTriangle, ChevronRight
} from "lucide-react";
import { toolsApi } from "@/lib/api/tools";
import { integrationsApi, UserConnection, IntegrationProvider } from "@/lib/api/integrations";
import { API_BASE_URL } from "@/lib/api/client";
import { useAuthStore } from "@/lib/store/useAuthStore";

// ─── Static integration catalog ─────────────────────────────────────────────
const CATALOG: Record<string, {
  label: string;
  subtitle: string;
  logo: string;
  color: string;       // brand accent used for the status bar
  tools: string[];
}> = {
  google: {
    label: "Google Workspace",
    subtitle: "Google Sheets · Drive · Docs",
    logo: "https://www.gstatic.com/images/branding/product/2x/sheets_2020q4_48dp.png",
    color: "#34A853",
    tools: ["read_google_sheet", "append_google_sheet_rows"],
  },
};

type Tab = "integrations" | "registry";

// ─── OAuth popup hook ────────────────────────────────────────────────────────
function useOAuthPopup() {
  const queryClient = useQueryClient();

  const open = useCallback(async (providerName: string) => {
    const redirectUri = `${window.location.origin}/integrations/callback`;
    const tools = CATALOG[providerName]?.tools ?? [];

    let authUrl: string;
    try {
      const res = await integrationsApi.initiateOAuth(providerName, tools, redirectUri);
      authUrl = res.authorization_url;
    } catch {
      alert("Could not start the OAuth flow. Check the server.");
      return;
    }

    const popup = window.open(authUrl, "oauth_popup", "width=520,height=640,scrollbars=yes");
    if (!popup) {
      alert("Please allow popups for this site to connect integrations.");
      return;
    }

    const handler = (event: MessageEvent) => {
      if (event.origin !== window.location.origin) return;
      if (event.data?.type === "OAUTH_SUCCESS" || event.data?.type === "OAUTH_ERROR") {
        queryClient.invalidateQueries({ queryKey: ["connections"] });
        window.removeEventListener("message", handler);
      }
    };
    window.addEventListener("message", handler);
  }, [queryClient]);

  return { open };
}

// ─── Integration card ────────────────────────────────────────────────────────
function IntegrationCard({
  provider,
  connection,
  onConnect,
  onReconnect,
  onDisconnect,
  isDisconnecting,
}: {
  provider: IntegrationProvider;
  connection?: UserConnection;
  onConnect: () => void;
  onReconnect: () => void;
  onDisconnect: () => void;
  isDisconnecting: boolean;
}) {
  const meta = CATALOG[provider.name];
  const isConnected = connection?.status === "connected";
  const [expanded, setExpanded] = useState(false);

  const connectedAt = connection?.connected_at
    ? new Date(connection.connected_at).toLocaleDateString("en-US", {
        month: "short", day: "numeric", year: "numeric",
      })
    : null;

  return (
    <div className="border border-zinc-800 rounded-2xl bg-[#0f0f0f] overflow-hidden transition-all hover:border-zinc-700">
      {/* Status banner */}
      {isConnected ? (
        <div className="flex items-center gap-2.5 px-5 py-2.5 text-sm font-medium"
          style={{ backgroundColor: `${meta?.color ?? "#22c55e"}18`, borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
          <CheckCircle2 size={14} style={{ color: meta?.color ?? "#22c55e" }} />
          <span style={{ color: meta?.color ?? "#22c55e" }}>Account connected</span>
          {connectedAt && <span className="ml-auto text-xs text-zinc-500 font-normal">Since {connectedAt}</span>}
        </div>
      ) : (
        <div className="flex items-center gap-2.5 px-5 py-2.5 text-sm font-medium bg-zinc-900/40 border-b border-zinc-800/50">
          <XCircle size={14} className="text-zinc-500" />
          <span className="text-zinc-500">Not connected</span>
        </div>
      )}

      {/* Body */}
      <div className="p-5 flex items-start gap-4">
        {meta?.logo ? (
          <img src={meta.logo} alt={meta.label} className="w-10 h-10 rounded-xl mt-0.5 flex-shrink-0" />
        ) : (
          <div className="w-10 h-10 rounded-xl bg-zinc-800 flex items-center justify-center flex-shrink-0">
            <Plug size={18} className="text-zinc-400" />
          </div>
        )}

        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-zinc-100">{meta?.label ?? provider.display_name}</p>
          <p className="text-xs text-zinc-500 mt-0.5">{meta?.subtitle ?? provider.display_name}</p>

          {/* Enabled tool chips */}
          {meta?.tools && (
            <div className="flex flex-wrap gap-1.5 mt-3">
              {meta.tools.map((t) => (
                <span key={t} className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-zinc-800 text-zinc-400 border border-zinc-700/50">
                  {t.replace(/_/g, " ")}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Action buttons */}
        <div className="flex flex-col items-end gap-2 flex-shrink-0">
          {isConnected ? (
            <>
              {/* Reconnect — triggers OAuth again, swaps credentials */}
              <button
                onClick={onReconnect}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-zinc-700 text-zinc-300 hover:border-zinc-500 hover:text-white transition-colors"
              >
                <RefreshCw size={11} />
                Reconnect
              </button>
              <button
                onClick={onDisconnect}
                disabled={isDisconnecting}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-transparent text-zinc-500 hover:text-red-400 hover:border-red-900 transition-colors disabled:opacity-40"
              >
                {isDisconnecting ? <Loader2 size={11} className="animate-spin" /> : <LogOut size={11} />}
                Disconnect
              </button>
            </>
          ) : (
            <button
              onClick={onConnect}
              className="flex items-center gap-2 px-4 py-2 text-sm rounded-xl font-medium bg-white text-zinc-900 hover:bg-zinc-100 transition-colors shadow-sm"
            >
              <img src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg" alt="" className="w-4 h-4" />
              Sign in with Google
            </button>
          )}
        </div>
      </div>

      {/* Expandable tools detail */}
      {isConnected && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="w-full flex items-center justify-between px-5 py-3 text-xs text-zinc-500 hover:text-zinc-300 border-t border-zinc-800/60 transition-colors"
        >
          <span>Permissions & tools</span>
          <ChevronRight size={13} className={`transition-transform ${expanded ? "rotate-90" : ""}`} />
        </button>
      )}

      {expanded && isConnected && (
        <div className="px-5 pb-4 space-y-2 border-t border-zinc-800/40">
          <p className="text-xs text-zinc-500 pt-3 font-medium uppercase tracking-wider">Enabled tools</p>
          {meta?.tools.map((t) => (
            <div key={t} className="flex items-center gap-2 text-xs text-zinc-400">
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
              {t.replace(/_/g, " ")}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Page ────────────────────────────────────────────────────────────────────
export default function ToolsPage() {
  const [tab, setTab] = useState<Tab>("integrations");
  const queryClient = useQueryClient();
  const { open: openOAuth } = useOAuthPopup();

  const { data: tools, isLoading: toolsLoading } = useQuery({
    queryKey: ["tools"],
    queryFn: toolsApi.getTools,
    enabled: tab === "registry",
  });

  const { data: providers, isLoading: providersLoading } = useQuery({
    queryKey: ["providers"],
    queryFn: integrationsApi.getProviders,
    enabled: tab === "integrations",
  });

  const { data: connections, isLoading: connectionsLoading } = useQuery({
    queryKey: ["connections"],
    queryFn: integrationsApi.getConnections,
    enabled: tab === "integrations",
    refetchInterval: false,
  });

  const disconnectMutation = useMutation({
    mutationFn: integrationsApi.disconnect,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["connections"] }),
  });

  const connectionMap: Record<string, UserConnection> = {};
  connections?.forEach((c) => { connectionMap[c.provider] = c; });

  const isLoading = providersLoading || connectionsLoading;

  return (
    <div className="p-8 max-w-3xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold text-white">Tools & Integrations</h1>
        <p className="text-sm text-zinc-400 mt-1">
          Connect external services to expand what your agent can do.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 bg-zinc-900 rounded-lg w-fit border border-zinc-800">
        {(["integrations", "registry"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-1.5 text-sm rounded-md transition-colors font-medium capitalize ${
              tab === t ? "bg-zinc-700 text-white" : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            {t === "integrations" ? "Integrations" : "Tool Registry"}
          </button>
        ))}
      </div>

      {/* ── Integrations tab ── */}
      {tab === "integrations" && (
        <div className="space-y-4">
          {isLoading ? (
            <div className="flex items-center justify-center gap-2 text-zinc-500 py-16 text-sm">
              <Loader2 size={16} className="animate-spin" />
              Loading integrations…
            </div>
          ) : !providers?.length ? (
            <div className="text-center py-16">
              <AlertTriangle size={28} className="text-zinc-600 mx-auto mb-3" />
              <p className="text-zinc-500 text-sm">No integration providers configured.</p>
            </div>
          ) : (
            providers.map((provider) => (
              <IntegrationCard
                key={provider.name}
                provider={provider}
                connection={connectionMap[provider.name]}
                onConnect={() => openOAuth(provider.name)}
                onReconnect={() => openOAuth(provider.name)}
                onDisconnect={() => disconnectMutation.mutate(provider.name)}
                isDisconnecting={
                  disconnectMutation.isPending &&
                  disconnectMutation.variables === provider.name
                }
              />
            ))
          )}
        </div>
      )}

      {/* ── Tool Registry tab ── */}
      {tab === "registry" && (
        <div className="border border-zinc-800 rounded-xl overflow-hidden bg-[#0A0A0A]">
          <table className="w-full text-left text-sm">
            <thead className="bg-zinc-900/50 text-zinc-400 border-b border-zinc-800">
              <tr>
                <th className="px-6 py-4 font-medium">Tool Name</th>
                <th className="px-6 py-4 font-medium">Description</th>
                <th className="px-6 py-4 font-medium">Kind</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800">
              {toolsLoading ? (
                <tr>
                  <td colSpan={3} className="px-6 py-8 text-center text-zinc-500">
                    Loading tools…
                  </td>
                </tr>
              ) : (
                tools?.map((tool) => (
                  <tr key={tool.id} className="hover:bg-zinc-900/20 transition-colors">
                    <td className="px-6 py-4 font-medium text-zinc-200">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded bg-zinc-900 border border-zinc-800 flex items-center justify-center">
                          <Wrench size={14} className="text-zinc-400" />
                        </div>
                        {tool.name}
                      </div>
                    </td>
                    <td className="px-6 py-4 text-zinc-400 max-w-md truncate">
                      {tool.description ?? "No description."}
                    </td>
                    <td className="px-6 py-4">
                      <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-medium bg-zinc-800 text-zinc-300">
                        Built-in
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
