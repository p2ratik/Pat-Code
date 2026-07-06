"use client";

import { useEffect } from "react";
import { apiClient } from "@/lib/api/client";
import { API_BASE_URL } from "@/lib/api/client";
import { useAuthStore } from "@/lib/store/useAuthStore";

/**
 * OAuth callback landing page.
 * Google redirects here with ?code=...&state=...
 * This page forwards those params to the backend callback endpoint,
 * then posts a message to the opener window and closes itself.
 */
export default function OAuthCallbackPage() {
  useEffect(() => {
    const run = async () => {
      const params = new URLSearchParams(window.location.search);
      const code = params.get("code");
      const state = params.get("state");

      if (!code || !state) {
        window.opener?.postMessage({ type: "OAUTH_ERROR", error: "Missing code or state" }, window.location.origin);
        window.close();
        return;
      }

      try {
        const token = useAuthStore.getState().token;
        const res = await fetch(`${API_BASE_URL}/integrations/oauth/callback`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            code,
            state,
            redirect_uri: window.location.origin + "/integrations/callback",
          }),
        });

        const data = await res.json();

        if (res.ok) {
          window.opener?.postMessage({ type: "OAUTH_SUCCESS", data }, window.location.origin);
        } else {
          window.opener?.postMessage({ type: "OAUTH_ERROR", error: data.detail || "OAuth failed" }, window.location.origin);
        }
      } catch (err) {
        window.opener?.postMessage({ type: "OAUTH_ERROR", error: String(err) }, window.location.origin);
      } finally {
        window.close();
      }
    };

    run();
  }, []);

  return (
    <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center">
      <div className="text-center space-y-3">
        <div className="w-8 h-8 border-2 border-zinc-600 border-t-white rounded-full animate-spin mx-auto" />
        <p className="text-zinc-400 text-sm">Completing authorization…</p>
      </div>
    </div>
  );
}
