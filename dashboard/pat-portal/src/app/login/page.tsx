"use client";

import { useState } from "react";
import { authApi } from "@/lib/api/auth";
import { useAuthStore } from "@/lib/store/useAuthStore";

export default function LoginPage() {
  const [userId, setUserId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const { setAuth } = useAuthStore();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!userId.trim()) return;

    setLoading(true);
    setError("");

    try {
      // Get token
      const tokenData = await authApi.generateToken(userId);

      // Temporarily set token so apiClient interceptor can use it
      useAuthStore.getState().setToken(tokenData.access_token);

      // Get user details
      const userData = await authApi.getUser(userId);

      // Store fully in Zustand
      useAuthStore.getState().setAuth(tokenData.access_token, userData);

      // Redirect to dashboard
      window.location.href = "/";
    } catch (err: any) {
      setError(
        err?.response?.data?.detail || "Failed to login. Check User ID.",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0A0A0A] flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <h2 className="mt-6 text-center text-3xl font-bold tracking-tight text-white">
          Sign in to PAT Portal
        </h2>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-[#0A0A0A] py-8 px-4 border border-zinc-800 shadow sm:rounded-xl sm:px-10">
          <form className="space-y-6" onSubmit={handleLogin}>
            <div>
              <label
                htmlFor="userId"
                className="block text-sm font-medium text-zinc-300"
              >
                User ID (UUID)
              </label>
              <div className="mt-1">
                <input
                  id="userId"
                  name="userId"
                  type="text"
                  required
                  value={userId}
                  onChange={(e) => setUserId(e.target.value)}
                  className="block w-full appearance-none rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-zinc-300 placeholder-zinc-500 focus:border-zinc-500 focus:outline-none focus:ring-zinc-500 sm:text-sm"
                  placeholder="e.g. 123e4567-e89b-12d3-a456-426614174000"
                />
              </div>
            </div>

            {error && <div className="text-sm text-red-500">{error}</div>}

            <div>
              <button
                type="submit"
                disabled={loading}
                className="flex w-full justify-center rounded-md border border-transparent bg-zinc-100 py-2 px-4 text-sm font-medium text-zinc-900 shadow-sm hover:bg-white focus:outline-none focus:ring-2 focus:ring-zinc-500 focus:ring-offset-2 disabled:opacity-50"
              >
                {loading ? "Signing in..." : "Sign in"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
