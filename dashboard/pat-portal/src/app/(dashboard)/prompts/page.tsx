'use client';

import { useQuery } from '@tanstack/react-query';
import { promptsApi } from '@/lib/api/prompts';
import { Plus, FileText, CheckCircle2 } from 'lucide-react';
import Link from 'next/link';

export default function PromptsPage() {
  const { data: prompts, isLoading } = useQuery({
    queryKey: ['prompts'],
    queryFn: promptsApi.getPrompts,
  });

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">System Prompts</h1>
          <p className="text-sm text-zinc-400 mt-1">Manage system prompt templates used by agent profiles.</p>
        </div>
        <button className="flex items-center gap-2 bg-zinc-100 hover:bg-white text-zinc-900 px-4 py-2 rounded-md text-sm font-medium transition-colors">
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
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800">
            {isLoading ? (
              <tr>
                <td colSpan={4} className="px-6 py-8 text-center text-zinc-500">Loading prompts...</td>
              </tr>
            ) : prompts?.map((prompt) => (
              <tr key={prompt.id} className="hover:bg-zinc-900/20 transition-colors cursor-pointer">
                <td className="px-6 py-4 font-medium text-zinc-200 flex items-center gap-3">
                  <div className="w-8 h-8 rounded bg-zinc-900 border border-zinc-800 flex items-center justify-center">
                    <FileText size={14} className="text-zinc-400" />
                  </div>
                  {prompt.name}
                </td>
                <td className="px-6 py-4 text-zinc-400 max-w-sm truncate">
                  {prompt.content}
                </td>
                <td className="px-6 py-4 text-zinc-400">
                  v{prompt.version}
                </td>
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
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
