"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bot,
  CheckCircle2,
  ChevronRight,
  Loader2,
  Save,
  X,
} from "lucide-react";
import Link from "next/link";
import { use, useState } from "react";
import { type ProfileUpdate, profilesApi } from "@/lib/api/profiles";
import { promptsApi } from "@/lib/api/prompts";
import { toolsApi } from "@/lib/api/tools";

// ---------------------------------------------------------------------------
// Overview tab – editable profile fields
// ---------------------------------------------------------------------------
function OverviewTab({
  profile,
}: {
  profile: ReturnType<typeof useProfile>["profile"];
}) {
  const qc = useQueryClient();

  const { data: prompts } = useQuery({
    queryKey: ["prompts"],
    queryFn: promptsApi.getPrompts,
  });

  const [form, setForm] = useState<ProfileUpdate>({
    name: profile!.name,
    description: profile!.description ?? "",
    model_name: profile!.model_name,
    temperature: profile!.temperature,
    max_turns: profile!.max_turns,
    prompt_id: profile!.prompt_id ?? "",
  });
  const [dirty, setDirty] = useState(false);

  const set = (k: keyof ProfileUpdate, v: any) => {
    setForm((f) => ({ ...f, [k]: v }));
    setDirty(true);
  };

  const mutation = useMutation({
    mutationFn: () =>
      profilesApi.updateProfile(profile!.id, {
        ...form,
        description: form.description || null,
        prompt_id: form.prompt_id || null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["profiles"] });
      setDirty(false);
    },
  });

  const handleReset = () => {
    setForm({
      name: profile!.name,
      description: profile!.description ?? "",
      model_name: profile!.model_name,
      temperature: profile!.temperature,
      max_turns: profile!.max_turns,
      prompt_id: profile!.prompt_id ?? "",
    });
    setDirty(false);
  };

  const inputClass =
    "w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-zinc-500 transition-colors";
  const labelClass = "block text-xs font-medium text-zinc-500 mb-1.5";

  return (
    <div className="space-y-6 pt-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Left column */}
        <div className="space-y-4">
          <div>
            <label className={labelClass}>Profile Name *</label>
            <input
              type="text"
              value={form.name ?? ""}
              onChange={(e) => set("name", e.target.value)}
              className={inputClass}
            />
          </div>

          <div>
            <label className={labelClass}>Description</label>
            <textarea
              value={form.description ?? ""}
              onChange={(e) => set("description", e.target.value)}
              rows={3}
              className={`${inputClass} resize-none`}
              placeholder="Optional description"
            />
          </div>

          <div>
            <label className={labelClass}>System Prompt</label>
            <select
              value={form.prompt_id ?? ""}
              onChange={(e) => set("prompt_id", e.target.value || null)}
              className={inputClass}
            >
              <option value="">— None —</option>
              {prompts?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} {!p.is_active ? "(inactive)" : ""}
                </option>
              ))}
            </select>
            {form.prompt_id && prompts && (
              <p className="mt-1 text-xs text-zinc-500">
                {prompts
                  .find((p) => p.id === form.prompt_id)
                  ?.content.slice(0, 120)}
                …
              </p>
            )}
          </div>
        </div>

        {/* Right column */}
        <div className="space-y-4">
          <div>
            <label className={labelClass}>Model</label>
            <select
              value={form.model_name ?? ""}
              onChange={(e) => set("model_name", e.target.value)}
              className={inputClass}
            >
              {["gpt-4.1-mini", "gpt-4.1", "gpt-4o", "gpt-4o-mini"].map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className={labelClass}>Temperature</label>
            <div className="flex items-center gap-3">
              <input
                type="range"
                min={0}
                max={2}
                step={0.05}
                value={form.temperature ?? 0.7}
                onChange={(e) => set("temperature", parseFloat(e.target.value))}
                className="flex-1 accent-white"
              />
              <span className="text-sm text-zinc-200 w-10 text-right font-mono">
                {(form.temperature ?? 0.7).toFixed(2)}
              </span>
            </div>
          </div>

          <div>
            <label className={labelClass}>Max Turns</label>
            <input
              type="number"
              min={1}
              max={500}
              value={form.max_turns ?? 100}
              onChange={(e) => set("max_turns", parseInt(e.target.value))}
              className={inputClass}
            />
          </div>

          <div>
            <label className={labelClass}>Profile Version</label>
            <div className="text-sm text-zinc-400 bg-zinc-900/50 border border-zinc-800 rounded-md px-3 py-2">
              v{profile!.version}
            </div>
          </div>
        </div>
      </div>

      {/* Save bar */}
      {dirty && (
        <div className="flex items-center gap-3 pt-2 border-t border-zinc-800">
          <button
            onClick={handleReset}
            className="flex items-center gap-2 px-4 py-2 text-sm text-zinc-400 hover:text-zinc-200 border border-zinc-700 rounded-md hover:border-zinc-500 transition-colors"
          >
            <X size={14} /> Discard
          </button>
          <button
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending || !form.name?.trim()}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium bg-zinc-100 text-zinc-900 rounded-md hover:bg-white disabled:opacity-50 transition-colors"
          >
            {mutation.isPending ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Save size={14} />
            )}
            Save Changes
          </button>
          {mutation.isSuccess && (
            <span className="flex items-center gap-1 text-xs text-emerald-500">
              <CheckCircle2 size={12} /> Saved
            </span>
          )}
          {mutation.isError && (
            <span className="text-xs text-red-400">
              {(mutation.error as any)?.response?.data?.detail ||
                "Save failed."}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tools tab
// ---------------------------------------------------------------------------
function ToolsTab({
  profileId,
  profileName,
}: {
  profileId: string;
  profileName: string;
}) {
  const qc = useQueryClient();

  const { data: allTools } = useQuery({
    queryKey: ["tools"],
    queryFn: toolsApi.getTools,
  });

  const { data: profileTools, isLoading } = useQuery({
    queryKey: ["profileTools", profileId],
    queryFn: () => toolsApi.getProfileTools(profileId),
  });

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [initialized, setInitialized] = useState(false);

  // Sync selected set when profile tools load
  if (profileTools && !initialized) {
    setSelected(new Set(profileTools.map((t) => t.name)));
    setInitialized(true);
  }

  const dirty = profileTools
    ? JSON.stringify([...selected].sort()) !==
      JSON.stringify(profileTools.map((t) => t.name).sort())
    : false;

  const mutation = useMutation({
    mutationFn: () => toolsApi.assignToolsToProfile(profileId, [...selected]),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["profileTools", profileId] });
      setInitialized(false);
    },
  });

  const toggle = (name: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  if (isLoading)
    return <div className="pt-8 text-center text-zinc-500">Loading tools…</div>;

  return (
    <div className="pt-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-zinc-200">
          Tool Permissions for <span className="text-white">{profileName}</span>
        </h3>
        <div className="flex items-center gap-3">
          {dirty && (
            <button
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending}
              className="flex items-center gap-2 text-xs bg-zinc-100 text-zinc-900 px-3 py-1.5 rounded hover:bg-white font-medium transition-colors"
            >
              {mutation.isPending ? (
                <Loader2 size={12} className="animate-spin" />
              ) : (
                <Save size={12} />
              )}
              Save Changes
            </button>
          )}
          {mutation.isSuccess && !dirty && (
            <span className="flex items-center gap-1 text-xs text-emerald-500">
              <CheckCircle2 size={12} /> Saved
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {allTools?.map((tool) => {
          const enabled = selected.has(tool.name);
          return (
            <button
              key={tool.id}
              onClick={() => toggle(tool.name)}
              className={`p-4 rounded-lg border flex items-start gap-3 text-left transition-all ${
                enabled
                  ? "border-zinc-500 bg-zinc-800/50 shadow-inner"
                  : "border-zinc-800 bg-[#0A0A0A] hover:border-zinc-700"
              }`}
            >
              <div
                className={`mt-0.5 w-4 h-4 rounded border flex items-center justify-center shrink-0 transition-colors ${enabled ? "bg-white border-white" : "border-zinc-600 bg-transparent"}`}
              >
                {enabled && <div className="w-2 h-2 rounded-sm bg-zinc-900" />}
              </div>
              <div>
                <div className="text-sm font-medium text-zinc-200">
                  {tool.name}
                </div>
                {tool.description && (
                  <div className="text-xs text-zinc-500 mt-1 line-clamp-2">
                    {tool.description}
                  </div>
                )}
              </div>
            </button>
          );
        })}
      </div>

      {mutation.isError && (
        <p className="text-xs text-red-400">
          {(mutation.error as any)?.response?.data?.detail || "Save failed."}
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Hook to get the profile object
// ---------------------------------------------------------------------------
function useProfile(id: string) {
  const { data: profiles, isLoading } = useQuery({
    queryKey: ["profiles"],
    queryFn: profilesApi.getProfiles,
  });
  const profile = profiles?.find((p) => p.id === id) ?? null;
  return { profile, isLoading };
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function ProfileDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [activeTab, setActiveTab] = useState<
    "overview" | "tools" | "assignments"
  >("overview");

  const { profile, isLoading } = useProfile(id);

  if (isLoading) {
    return (
      <div className="p-8 flex items-center gap-2 text-zinc-500">
        <Loader2 size={16} className="animate-spin" /> Loading profile…
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="p-8 text-zinc-400">
        Profile not found.{" "}
        <Link href="/profiles" className="underline hover:text-zinc-200">
          Back to profiles
        </Link>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-zinc-500">
        <Link
          href="/profiles"
          className="hover:text-zinc-300 transition-colors"
        >
          Profiles
        </Link>
        <ChevronRight size={14} />
        <span className="text-zinc-200">{profile.name}</span>
      </div>

      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 rounded-xl bg-zinc-900 flex items-center justify-center border border-zinc-800">
            <Bot size={32} className="text-zinc-300" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold text-white flex items-center gap-3">
              {profile.name}
              {profile.is_active && (
                <span className="px-2 py-0.5 bg-emerald-500/10 text-emerald-500 text-xs font-medium rounded-full border border-emerald-500/20">
                  Active
                </span>
              )}
            </h1>
            <p className="text-sm text-zinc-400 mt-1">
              {profile.description || "No description"}
            </p>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-zinc-800">
        <nav className="flex gap-6">
          {(["overview", "tools", "assignments"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`py-3 text-sm font-medium border-b-2 transition-colors capitalize ${
                activeTab === tab
                  ? "border-white text-white"
                  : "border-transparent text-zinc-500 hover:text-zinc-300 hover:border-zinc-700"
              }`}
            >
              {tab}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab content */}
      {activeTab === "overview" && <OverviewTab profile={profile} />}
      {activeTab === "tools" && (
        <ToolsTab profileId={profile.id} profileName={profile.name} />
      )}
      {activeTab === "assignments" && (
        <div className="pt-4 text-sm text-zinc-400">
          Assignments view coming soon.
        </div>
      )}
    </div>
  );
}
