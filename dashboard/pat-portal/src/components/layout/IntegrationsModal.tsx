"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  X,
  Plug,
  CheckCircle2,
  Circle,
  Loader2,
  RefreshCcw,
  Link2Off,
  ExternalLink,
} from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { integrationsApi, UserConnection } from "@/lib/api/integrations";
import { useUIStore } from "@/lib/store/useUIStore";
import clsx from "clsx";

const GOOGLE_TOOLS_LABEL = "Google Sheets, Drive, Gmail, Calendar";

export function IntegrationsModal() {
  const { isIntegrationsOpen, setIntegrationsOpen } = useUIStore();
  const qc = useQueryClient();
  const [isOAuthLoading, setIsOAuthLoading] = useState(false);
  const [isDisconnecting, setIsDisconnecting] = useState(false);

  // Fetch providers and connections fresh every time the modal opens.
  const { data: providers = [] } = useQuery({
    queryKey: ["providers"],
    queryFn: integrationsApi.getProviders,
    enabled: isIntegrationsOpen,
  });

  const { data: connections = [], isLoading: connectionsLoading } = useQuery({
    queryKey: ["connections"],
    queryFn: integrationsApi.getConnections,
    enabled: isIntegrationsOpen,
    // Refresh every time the modal is opened so status is always fresh.
    staleTime: 0,
  });

  // Listen for OAuth popup result.
  useEffect(() => {
    const handler = (e: MessageEvent) => {
      if (e.origin !== window.location.origin) return;
      if (e.data?.type === "OAUTH_SUCCESS") {
        setIsOAuthLoading(false);
        qc.invalidateQueries({ queryKey: ["connections"] });
        qc.invalidateQueries({ queryKey: ["profileTools"] });
      }
      if (e.data?.type === "OAUTH_ERROR") {
        setIsOAuthLoading(false);
        qc.invalidateQueries({ queryKey: ["connections"] });
      }
    };
    window.addEventListener("message", handler);
    return () => window.removeEventListener("message", handler);
  }, [qc]);

  // Close on Escape.
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setIntegrationsOpen(false);
    };
    if (isIntegrationsOpen) window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isIntegrationsOpen, setIntegrationsOpen]);

  const getConnection = (providerName: string): UserConnection | undefined =>
    connections.find((c) => c.provider === providerName);

  const handleConnect = async (providerName: string, toolNames: string[]) => {
    setIsOAuthLoading(true);
    try {
      const redirectUri = `${window.location.origin}/integrations/callback`;
      const { authorization_url } = await integrationsApi.initiateOAuth(
        providerName,
        toolNames,
        redirectUri,
      );
      // Open Google's consent screen in a popup.
      window.open(
        authorization_url,
        "oauth_popup",
        "width=520,height=660,left=200,top=80",
      );
    } catch {
      setIsOAuthLoading(false);
    }
  };

  const handleDisconnect = async (providerName: string) => {
    setIsDisconnecting(true);
    try {
      await integrationsApi.disconnect(providerName);
      qc.invalidateQueries({ queryKey: ["connections"] });
    } finally {
      setIsDisconnecting(false);
    }
  };

  return (
    <AnimatePresence>
      {isIntegrationsOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50"
            onClick={() => setIntegrationsOpen(false)}
          />

          {/* Panel */}
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 16 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 16 }}
              transition={{ duration: 0.2, ease: "easeOut" }}
              className="w-full max-w-lg bg-zinc-900 border border-zinc-800 rounded-2xl shadow-2xl overflow-hidden pointer-events-auto"
            >
              {/* Header */}
              <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-zinc-800 flex items-center justify-center">
                    <Plug size={16} className="text-zinc-400" />
                  </div>
                  <div>
                    <h2 className="font-semibold text-white text-sm">
                      Integrations
                    </h2>
                    <p className="text-xs text-zinc-500">
                      Connect your accounts to use external tools
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setIntegrationsOpen(false)}
                  className="text-zinc-500 hover:text-white transition-colors p-1 rounded-md hover:bg-zinc-800"
                >
                  <X size={18} />
                </button>
              </div>

              {/* Body */}
              <div className="p-4 space-y-3 max-h-[70vh] overflow-y-auto">
                {connectionsLoading ? (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 size={20} className="animate-spin text-zinc-500" />
                  </div>
                ) : providers.length === 0 ? (
                  <div className="text-center py-12 text-sm text-zinc-500">
                    No integration providers configured yet.
                    <br />
                    <span className="text-xs text-zinc-600">
                      Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in your .env
                    </span>
                  </div>
                ) : (
                  providers.map((provider) => {
                    const conn = getConnection(provider.name);
                    const isConnected = conn?.status === "connected";

                    return (
                      <div
                        key={provider.name}
                        className={clsx(
                          "rounded-xl border p-4 transition-colors",
                          isConnected
                            ? "border-emerald-900/50 bg-emerald-950/20"
                            : "border-zinc-800 bg-zinc-950",
                        )}
                      >
                        <div className="flex items-start gap-4">
                          {/* Provider icon */}
                          <div className="w-10 h-10 rounded-xl bg-white flex items-center justify-center shrink-0">
                            {provider.name === "google" ? (
                              <img
                                src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg"
                                className="w-5 h-5"
                                alt="Google"
                              />
                            ) : (
                              <Plug size={18} className="text-zinc-700" />
                            )}
                          </div>

                          {/* Info */}
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-0.5">
                              <span className="font-medium text-white text-sm">
                                {provider.display_name}
                              </span>
                              {isConnected ? (
                                <span className="flex items-center gap-1 text-emerald-400 text-xs font-medium">
                                  <CheckCircle2 size={12} />
                                  Connected
                                </span>
                              ) : (
                                <span className="flex items-center gap-1 text-amber-500 text-xs font-medium">
                                  <Circle size={12} />
                                  Not connected
                                </span>
                              )}
                            </div>

                            {/* Connected-as badge */}
                            {isConnected && conn?.email && (
                              <p className="text-xs text-zinc-400 mt-1">
                                Signed in as{" "}
                                <span className="font-medium text-zinc-200">
                                  {conn.email}
                                </span>
                              </p>
                            )}

                            {/* Scope hint */}
                            {!isConnected && (
                              <p className="text-xs text-zinc-500 mt-1">
                                Enables:{" "}
                                {provider.name === "google"
                                  ? GOOGLE_TOOLS_LABEL
                                  : "external tools"}
                              </p>
                            )}
                          </div>

                          {/* Action button */}
                          <div className="shrink-0">
                            {!isConnected ? (
                              <button
                                onClick={() =>
                                  handleConnect(provider.name, [])
                                }
                                disabled={isOAuthLoading || !provider.enabled}
                                className="flex items-center gap-2 px-3 py-1.5 bg-white hover:bg-zinc-100 disabled:opacity-50 text-zinc-900 text-xs font-semibold rounded-lg transition-colors"
                              >
                                {isOAuthLoading ? (
                                  <Loader2 size={12} className="animate-spin" />
                                ) : (
                                  <ExternalLink size={12} />
                                )}
                                Connect
                              </button>
                            ) : (
                              <div className="flex flex-col gap-1.5">
                                <button
                                  onClick={() =>
                                    handleConnect(provider.name, [])
                                  }
                                  disabled={isOAuthLoading}
                                  className="flex items-center gap-1.5 px-3 py-1.5 border border-zinc-700 hover:bg-zinc-800 disabled:opacity-50 text-zinc-300 text-xs font-medium rounded-lg transition-colors"
                                  title="Reconnect / switch account"
                                >
                                  {isOAuthLoading ? (
                                    <Loader2
                                      size={12}
                                      className="animate-spin"
                                    />
                                  ) : (
                                    <RefreshCcw size={12} />
                                  )}
                                  Reconnect
                                </button>
                                <button
                                  onClick={() =>
                                    handleDisconnect(provider.name)
                                  }
                                  disabled={isDisconnecting}
                                  className="flex items-center gap-1.5 px-3 py-1.5 border border-red-900/40 hover:bg-red-500/10 disabled:opacity-50 text-red-400 text-xs font-medium rounded-lg transition-colors"
                                >
                                  {isDisconnecting ? (
                                    <Loader2
                                      size={12}
                                      className="animate-spin"
                                    />
                                  ) : (
                                    <Link2Off size={12} />
                                  )}
                                  Disconnect
                                </button>
                              </div>
                            )}
                          </div>
                        </div>

                        {/* "Not enabled" warning */}
                        {!provider.enabled && (
                          <div className="mt-3 px-3 py-2 bg-amber-500/10 border border-amber-900/40 rounded-lg text-xs text-amber-400">
                            This provider is disabled by the administrator.
                          </div>
                        )}
                      </div>
                    );
                  })
                )}
              </div>

              {/* Footer hint */}
              <div className="px-6 py-3 border-t border-zinc-800 text-xs text-zinc-600">
                Each user connects their own account — credentials are stored
                encrypted and are never shared.
              </div>
            </motion.div>
          </div>
        </>
      )}
    </AnimatePresence>
  );
}
