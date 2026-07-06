"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, Loader2, Plus, Settings2, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { type ProfileCreate, profilesApi } from "@/lib/api/profiles";
import { promptsApi } from "@/lib/api/prompts";

function CreateProfileModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState<ProfileCreate>({
    name: "",
    model_name: "gpt-4.1-mini",
    temperature: 0.7,
    max_turns: 100,
    description: "",
    prompt_id: null,
  });

  const { data: prompts } = useQuery({
    queryKey: ["prompts"],
    queryFn: promptsApi.getPrompts,
  });

  const mutation = useMutation({
    mutationFn: () =>
      profilesApi.createProfile({
        ...form,
        description: form.description || null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["profiles"] });
      onClose();
    },
  });

  const set = (k: keyof ProfileCreate, v: any) =>
    setForm((f) => ({ ...f, [k]: v }));

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl w-full max-w-lg p-6 shadow-2xl">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-base font-semibold text-white">
            Create Agent Profile
          </h2>
          <button
            onClick={onClose}
            className="text-zinc-500 hover:text-zinc-200"
          >
            <X size={18} />
          </button>
        </div>
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">
              Name *
            </label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => set("name", e.target.value)}
              placeholder="Research Agent"
              className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-zinc-500 placeholder-zinc-600"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">
              Description
            </label>
            <textarea
              value={form.description ?? ""}
              onChange={(e) => set("description", e.target.value)}
              rows={2}
              placeholder="Optional description"
              className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-zinc-500 placeholder-zinc-600 resize-none"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1.5">
                Model
              </label>
              <select
                value={form.model_name}
                onChange={(e) => set("model_name", e.target.value)}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-zinc-500"
              >
                {["gpt-4.1-mini", "gpt-4.1", "gpt-4o", "gpt-4o-mini"].map(
                  (m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ),
                )}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1.5">
                Temperature
              </label>
              <input
                type="number"
                step="0.1"
                min="0"
                max="2"
                value={form.temperature}
                onChange={(e) => set("temperature", parseFloat(e.target.value))}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-zinc-500"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1.5">
                Max Turns
              </label>
              <input
                type="number"
                min="1"
                value={form.max_turns}
                onChange={(e) => set("max_turns", parseInt(e.target.value))}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-zinc-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1.5">
                System Prompt
              </label>
              <select
                value={form.prompt_id ?? ""}
                onChange={(e) => set("prompt_id", e.target.value || null)}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-zinc-500"
              >
                <option value="">None</option>
                {prompts?.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
        {mutation.isError && (
          <p className="mt-4 text-xs text-red-400">
            {(mutation.error as any)?.response?.data?.detail ||
              "Something went wrong."}
          </p>
        )}
        <div className="flex justify-end gap-3 mt-6">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-zinc-400 hover:text-zinc-200"
          >
            Cancel
          </button>
          <button
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending || !form.name.trim()}
            className="flex items-center gap-2 px-4 py-2 bg-zinc-100 text-zinc-900 text-sm font-medium rounded-md hover:bg-white disabled:opacity-50"
          >
            {mutation.isPending && (
              <Loader2 size={14} className="animate-spin" />
            )}
            Create Profile
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ProfilesPage() {
  const [showModal, setShowModal] = useState(false);
  const {
    data: profiles,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["profiles"],
    queryFn: profilesApi.getProfiles,
  });

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-8">
      {showModal && <CreateProfileModal onClose={() => setShowModal(false)} />}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Agent Profiles</h1>
          <p className="text-sm text-zinc-400 mt-1">
            {isLoading
              ? "Loading..."
              : `${profiles?.length ?? 0} profiles configured.`}
          </p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-2 bg-zinc-100 hover:bg-white text-zinc-900 px-4 py-2 rounded-md text-sm font-medium transition-colors"
        >
          <Plus size={16} /> Create Profile
        </button>
      </div>

      {isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-44 rounded-xl border border-zinc-800 bg-zinc-900/30 animate-pulse"
            />
          ))}
        </div>
      )}
      {isError && (
        <p className="text-sm text-red-400">Failed to load profiles.</p>
      )}
      {!isLoading && !isError && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {profiles?.map((profile) => (
            <Link
              key={profile.id}
              href={`/profiles/${profile.id}`}
              className="block group"
            >
              <div className="p-6 rounded-xl border border-zinc-800 bg-[#0A0A0A] hover:border-zinc-600 transition-colors h-full flex flex-col">
                <div className="flex items-start justify-between mb-4">
                  <div className="w-10 h-10 rounded-lg bg-zinc-900 flex items-center justify-center border border-zinc-800">
                    <Bot size={20} className="text-zinc-300" />
                  </div>
                  {profile.is_active && (
                    <span className="px-2 py-1 bg-emerald-500/10 text-emerald-500 text-xs font-medium rounded-full border border-emerald-500/20">
                      Active
                    </span>
                  )}
                </div>
                <h3 className="text-base font-medium text-zinc-100 group-hover:text-white transition-colors">
                  {profile.name}
                </h3>
                <p className="text-sm text-zinc-500 mt-1 line-clamp-2 flex-1">
                  {profile.description || "No description."}
                </p>
                <div className="flex items-center gap-4 mt-6 pt-4 border-t border-zinc-800/50">
                  <div className="flex items-center gap-1.5 text-xs font-medium text-zinc-400">
                    <span className="w-2 h-2 rounded-full bg-blue-500" />
                    {profile.model_name}
                  </div>
                  <div className="flex items-center gap-1.5 text-xs text-zinc-500">
                    <Settings2 size={14} />v{profile.version}
                  </div>
                  <div className="ml-auto text-xs text-zinc-600">
                    {profile.temperature} temp
                  </div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
