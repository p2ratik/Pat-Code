"use client";

import { useState } from "react";
import { authApi } from "@/lib/api/auth";
import { useAuthStore } from "@/lib/store/useAuthStore";

type Step = "email" | "name";

export default function LoginPage() {
  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const { setAuth } = useAuthStore();

  /** First step: submit email. If account exists, logs in immediately.
   *  If not, moves to the name step so the user can set a display name. */
  const handleEmailSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = email.trim().toLowerCase();
    if (!trimmed) return;

    setLoading(true);
    setError("");

    try {
      const data = await authApi.loginOrRegister(trimmed);
      // Existing user — log in right away.
      useAuthStore.getState().setAuth(data.access_token, data.user);
      window.location.href = "/";
    } catch (err: any) {
      const detail = err?.response?.data?.detail ?? "";
      // If the error says "disabled", surface it immediately.
      if (detail.toLowerCase().includes("disabled")) {
        setError(detail);
        setLoading(false);
        return;
      }
      // Any other error — try continuing to the name step.
      setStep("name");
      setLoading(false);
    }
  };

  /** Second step (new users only): enter display name, then create + login. */
  const handleNameSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedEmail = email.trim().toLowerCase();
    const trimmedName = displayName.trim() || trimmedEmail.split("@")[0];

    setLoading(true);
    setError("");

    try {
      const data = await authApi.loginOrRegister(trimmedEmail, trimmedName);
      useAuthStore.getState().setAuth(data.access_token, data.user);
      window.location.href = "/";
    } catch (err: any) {
      setError(
        err?.response?.data?.detail || "Sign-up failed. Please try again.",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0A0A0A] flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      {/* Logo / wordmark */}
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center mb-8">
        <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-zinc-900 border border-zinc-800 mb-5">
          <span className="text-white font-bold text-xl">P</span>
        </div>
        <h1 className="text-3xl font-bold tracking-tight text-white">
          PAT Portal
        </h1>
        <p className="mt-2 text-sm text-zinc-500">
          {step === "email"
            ? "Sign in or create an account to continue"
            : "Just one more thing — what should we call you?"}
        </p>
      </div>

      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-[#111111] py-8 px-6 border border-zinc-800 shadow-2xl sm:rounded-xl">
          {step === "email" ? (
            <form className="space-y-5" onSubmit={handleEmailSubmit}>
              <div>
                <label
                  htmlFor="email"
                  className="block text-sm font-medium text-zinc-300 mb-1.5"
                >
                  Email address
                </label>
                <input
                  id="email"
                  name="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="block w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3.5 py-2.5 text-white placeholder-zinc-500 focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500 sm:text-sm transition-colors"
                  placeholder="you@example.com"
                />
              </div>

              {error && (
                <div className="text-sm text-red-400 bg-red-500/10 border border-red-900/40 rounded-lg px-3 py-2">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="flex w-full justify-center items-center gap-2 rounded-lg bg-white py-2.5 px-4 text-sm font-semibold text-zinc-900 shadow-sm hover:bg-zinc-100 focus:outline-none focus:ring-2 focus:ring-zinc-500 focus:ring-offset-2 focus:ring-offset-zinc-900 disabled:opacity-50 transition-colors"
              >
                {loading ? (
                  <>
                    <span className="w-4 h-4 border-2 border-zinc-400 border-t-zinc-800 rounded-full animate-spin" />
                    Checking…
                  </>
                ) : (
                  "Continue with email"
                )}
              </button>
            </form>
          ) : (
            <form className="space-y-5" onSubmit={handleNameSubmit}>
              {/* Show the email locked in */}
              <div className="flex items-center gap-2 p-3 bg-zinc-900 rounded-lg border border-zinc-800">
                <svg className="w-4 h-4 text-zinc-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 12a4 4 0 10-8 0 4 4 0 008 0zm0 0v1.5a2.5 2.5 0 005 0V12a9 9 0 10-9 9m4.5-1.206a8.959 8.959 0 01-4.5 1.207" />
                </svg>
                <span className="text-sm text-zinc-300 truncate">{email}</span>
                <button
                  type="button"
                  onClick={() => { setStep("email"); setError(""); }}
                  className="ml-auto text-xs text-zinc-500 hover:text-zinc-300 transition-colors shrink-0"
                >
                  Change
                </button>
              </div>

              <div>
                <label
                  htmlFor="displayName"
                  className="block text-sm font-medium text-zinc-300 mb-1.5"
                >
                  Your name
                </label>
                <input
                  id="displayName"
                  name="displayName"
                  type="text"
                  autoComplete="name"
                  autoFocus
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  className="block w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3.5 py-2.5 text-white placeholder-zinc-500 focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500 sm:text-sm transition-colors"
                  placeholder={email.split("@")[0]}
                />
                <p className="mt-1.5 text-xs text-zinc-500">
                  Leave blank to use your email prefix.
                </p>
              </div>

              {error && (
                <div className="text-sm text-red-400 bg-red-500/10 border border-red-900/40 rounded-lg px-3 py-2">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="flex w-full justify-center items-center gap-2 rounded-lg bg-white py-2.5 px-4 text-sm font-semibold text-zinc-900 shadow-sm hover:bg-zinc-100 focus:outline-none focus:ring-2 focus:ring-zinc-500 focus:ring-offset-2 focus:ring-offset-zinc-900 disabled:opacity-50 transition-colors"
              >
                {loading ? (
                  <>
                    <span className="w-4 h-4 border-2 border-zinc-400 border-t-zinc-800 rounded-full animate-spin" />
                    Creating account…
                  </>
                ) : (
                  "Create account & sign in"
                )}
              </button>
            </form>
          )}
        </div>

        <p className="mt-4 text-center text-xs text-zinc-600">
          By continuing you agree to use this tool responsibly.
        </p>
      </div>
    </div>
  );
}
