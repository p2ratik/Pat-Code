'use client';

import { useQuery } from '@tanstack/react-query';
import { toolsApi } from '@/lib/api/tools';
import { Wrench } from 'lucide-react';

export default function ToolsPage() {
  const { data: tools, isLoading } = useQuery({
    queryKey: ['tools'],
    queryFn: toolsApi.getTools,
  });

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-white">Tool Registry</h1>
        <p className="text-sm text-zinc-400 mt-1">Global catalog of all tools available to agent profiles.</p>
      </div>

      <div className="border border-zinc-800 rounded-xl overflow-hidden bg-[#0A0A0A]">
        <table className="w-full text-left text-sm">
          <thead className="bg-zinc-900/50 text-zinc-400 border-b border-zinc-800">
            <tr>
              <th className="px-6 py-4 font-medium">Tool Name</th>
              <th className="px-6 py-4 font-medium">Description</th>
              <th className="px-6 py-4 font-medium">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800">
            {isLoading ? (
              <tr>
                <td colSpan={3} className="px-6 py-8 text-center text-zinc-500">Loading tools...</td>
              </tr>
            ) : tools?.map((tool) => (
              <tr key={tool.id} className="hover:bg-zinc-900/20 transition-colors">
                <td className="px-6 py-4 font-medium text-zinc-200 flex items-center gap-3">
                  <div className="w-8 h-8 rounded bg-zinc-900 border border-zinc-800 flex items-center justify-center">
                    <Wrench size={14} className="text-zinc-400" />
                  </div>
                  {tool.name}
                </td>
                <td className="px-6 py-4 text-zinc-400 max-w-md truncate">
                  {tool.description || "No description."}
                </td>
                <td className="px-6 py-4">
                   <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-medium bg-zinc-800 text-zinc-300">
                     Global
                   </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
