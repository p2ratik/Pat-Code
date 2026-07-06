"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, FileText, Loader2, Pencil, Plus, X } from "lucide-react";
import { useState } from "react";
import { PromptCreate, promptsApi } from "@/lib/api/prompts";

// ---------------------------------------------------------------------------
// Create / Edit Prompt Modal
// ---------------------------------------------------------------------------
function PromptModal({
  onClose,
  existing,
}: {
  onClose: () => void;
  existing?: {
    id: string;
    name: string;
    content: string;
    version: number;
    is_active: boolean;
  } | null;
}) {
  const qc = useQueryClient();
  const isEdit = !!existing;

  const [form, setForm] = useState({
    name: existing?.name ?? "",
    content: existing?.content ?? "",
    version: existing?.version ?? 1,
  });
  const [isActive, setIsActive] = useState(existing?.is_active ?? true);

  const set = (k: keyof typeof form, v: any) =>
    setForm((f) => ({ ...f, [k]: v }));

  const createMutation = useMutation({
    mutationFn: () =>
      promptsApi.createPrompt({
        name: form.name,
        content: form.content,
        version: form.version,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["prompts"] });
      onClose();
    },
  });

  const updateMutation = useMutation({
    mutationFn: () =>
      promptsApi.updatePrompt(existing!.id, {
        name: form.name,
        content: form.content,
        is_active: isActive,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["prompts"] });
      onClose();
    },
  });

  const mutation = isEdit ? updateMutation : createMutation;

  const handleSubmit = () => {
    if (!form.name.trim() || !form.content.trim()) return;
    mutation.mutate();
  };

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl w-full max-w-2xl shadow-2xl flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-zinc-800 shrink-0">
          <h2 className="text-base font-semibold text-white">
            {isEdit ? "Edit Prompt" : "Create System Prompt"}
          </h2>
          <button
            onClick={onClose}
            className="text-zinc-500 hover:text-zinc-200 transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-4 overflow-y-auto flex-1">
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">
              Name *
            </label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => set("name", e.target.value)}
              placeholder="e.g. Research Assistant Prompt"
              className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-zinc-500 placeholder-zinc-600"
            />
          </div>

          {!isEdit && (
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1.5">
                Version
              </label>
              <input
                type="number"
                min={1}
                value={form.version}
                onChange={(e) => set("version", parseInt(e.target.value) || 1)}
                className="w-24 bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-zinc-500"
              />
            </div>
          )}

          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">
              Content *
            </label>
            <textarea
              value={form.content}
              onChange={(e) => set("content", e.target.value)}
              rows={12}
              placeholder="You are a helpful research assistant. Your goal is to..."
              className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-zinc-500 placeholder-zinc-600 resize-y font-mono"
            />
          </div>

          {isEdit && (
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => setIsActive((v) => !v)}
                className={`relative inline-flex h-5 w-9 shrink-0 rounded-full border-2 border-transparent transition-colors focus:outline-none ${isActive ? "bg-emerald-500" : "bg-zinc-600"}`}
              >
                <span
                  className={`pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow transform transition-transform ${isActive ? "translate-x-4" : "translate-x-0"}`}
                />
              </button>
              <span className="text-sm text-zinc-300">
                {isActive ? "Active" : "Inactive"}
              </span>
            </div>
          )}
        </div>

        {/* Error */}
        {mutation.isError && (
          <p className="px-6 pb-2 text-xs text-red-400">
            {(mutation.error as any)?.response?.data?.detail ||
              "Something went wrong."}
          </p>
        )}

        {/* Footer */}
        <div className="flex justify-end gap-3 p-6 border-t border-zinc-800 shrink-0">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-zinc-400 hover:text-zinc-200 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={
              mutation.isPending || !form.name.trim() || !form.content.trim()
            }
            className="flex items-center gap-2 px-4 py-2 bg-zinc-100 text-zinc-900 text-sm font-medium rounded-md hover:bg-white disabled:opacity-50 transition-colors"
          >
            {mutation.isPending && (
              <Loader2 size={14} className="animate-spin" />
            )}
            {isEdit ? "Save Changes" : "Create Prompt"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function PromptsPage() {
  const [showModal, setShowModal] = useState(false);
  const [editTarget, setEditTarget] = useState<null | {
    id: string;
    name: string;
    content: string;
    version: number;
    is_active: boolean;
  }>(null);

  const {
    data: prompts,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["prompts"],
    queryFn: promptsApi.getPrompts,
  });

  const openCreate = () => {
    setEditTarget(null);
    setShowModal(true);
  };
  const openEdit = (p: typeof editTarget) => {
    setEditTarget(p);
    setShowModal(true);
  };
  const closeModal = () => setShowModal(false);

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-8">
      {showModal && <PromptModal onClose={closeModal} existing={editTarget} />}

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">System Prompts</h1>
          <p className="text-sm text-zinc-400 mt-1">
            Manage system prompt templates used by agent profiles.
          </p>
        </div>
        <button
          onClick={openCreate}
          className="flex items-center gap-2 bg-zinc-100 hover:bg-white text-zinc-900 px-4 py-2 rounded-md text-sm font-medium transition-colors"
        >
          <Plus size={16} />
          Create Prompt
        </button>
      </div>

      <div className="border border-zinc-800 rounded-xl overflow-hidden bg-[#0A0A0A]">
        <table className="w-full text-left text-sm">
          <thead className="bg-zinc-900/50 text-zinc-400 border-b border-zinc-800">
            <tr>
              <th className="px-6 py-4 font-medium">Name</th>
              <th className="px-6 py-4 font-medium">Content Preview</th>
              <th className="px-6 py-4 font-medium">Version</th>
              <th className="px-6 py-4 font-medium">Status</th>
              <th className="px-6 py-4 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800">
            {isLoading ? (
              <tr>
                <td colSpan={5} className="px-6 py-8 text-center text-zinc-500">
                  Loading prompts...
                </td>
              </tr>
            ) : isError ? (
              <tr>
                <td colSpan={5} className="px-6 py-8 text-center text-red-400">
                  Failed to load prompts.
                </td>
              </tr>
            ) : prompts?.length === 0 ? (
              <tr>
                <td
                  colSpan={5}
                  className="px-6 py-12 text-center text-zinc-500"
                >
                  <div className="flex flex-col items-center gap-2">
                    <FileText size={32} className="opacity-20" />
                    <p>No prompts yet. Click "Create Prompt" to add one.</p>
                  </div>
                </td>
              </tr>
            ) : (
              prompts?.map((prompt) => (
                <tr
                  key={prompt.id}
                  className="hover:bg-zinc-900/20 transition-colors"
                >
                  <td className="px-6 py-4 font-medium text-zinc-200">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded bg-zinc-900 border border-zinc-800 flex items-center justify-center shrink-0">
                        <FileText size={14} className="text-zinc-400" />
                      </div>
                      {prompt.name}
                    </div>
                  </td>
                  <td className="px-6 py-4 text-zinc-400 max-w-sm truncate">
                    {prompt.content}
                  </td>
                  <td className="px-6 py-4 text-zinc-400">v{prompt.version}</td>
                  <td className="px-6 py-4">
                    {prompt.is_active ? (
                      <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-medium bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">
                        <CheckCircle2 size={12} /> Active
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-medium bg-zinc-800 text-zinc-400 border border-zinc-700">
                        Inactive
                      </span>
                    )}
                  </td>
                  <td className="px-6 py-4">
                    <button
                      onClick={() =>
                        openEdit({
                          id: prompt.id,
                          name: prompt.name,
                          content: prompt.content,
                          version: prompt.version,
                          is_active: prompt.is_active,
                        })
                      }
                      className="text-zinc-500 hover:text-zinc-200 transition-colors p-1 rounded hover:bg-zinc-800"
                      title="Edit prompt"
                    >
                      <Pencil size={14} />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
