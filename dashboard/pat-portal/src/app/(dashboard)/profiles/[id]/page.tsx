'use client';

import { useQuery } from '@tanstack/react-query';
import { profilesApi } from '@/lib/api/profiles';
import { toolsApi } from '@/lib/api/tools';
import { Bot, Wrench, ChevronRight } from 'lucide-react';
import Link from 'next/link';
import { use, useState } from 'react';

export default function ProfileDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = use(params);
  const [activeTab, setActiveTab] = useState<'overview' | 'tools' | 'assignments'>('overview');

  const { data: profiles } = useQuery({
    queryKey: ['profiles'],
    queryFn: profilesApi.getProfiles,
  });

  const profile = profiles?.find(p => p.id === resolvedParams.id);

  const { data: allTools } = useQuery({
    queryKey: ['tools'],
    queryFn: toolsApi.getTools,
  });

  const { data: profileTools } = useQuery({
    queryKey: ['profileTools', resolvedParams.id],
    queryFn: () => toolsApi.getProfileTools(resolvedParams.id),
  });

  const isToolEnabled = (toolId: string) => {
    return profileTools?.some(pt => pt.id === toolId);
  };

  if (!profile) return <div className="p-8 text-zinc-400">Loading...</div>;

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-6">
      <div className="flex items-center gap-2 text-sm text-zinc-500 mb-6">
        <Link href="/profiles" className="hover:text-zinc-300">Profiles</Link>
        <ChevronRight size={14} />
        <span className="text-zinc-200">{profile.name}</span>
      </div>

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
            <p className="text-sm text-zinc-400 mt-1">{profile.description || 'No description'}</p>
          </div>
        </div>
      </div>

      <div className="border-b border-zinc-800">
        <nav className="flex gap-6">
          {['overview', 'tools', 'assignments'].map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab as any)}
              className={`py-3 text-sm font-medium border-b-2 transition-colors capitalize ${
                activeTab === tab 
                  ? 'border-white text-white' 
                  : 'border-transparent text-zinc-500 hover:text-zinc-300 hover:border-zinc-700'
              }`}
            >
              {tab}
            </button>
          ))}
        </nav>
      </div>

      {activeTab === 'overview' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4">
          <div className="space-y-6">
            <div>
              <label className="block text-xs font-medium text-zinc-500 mb-1">Model</label>
              <div className="text-sm text-zinc-200 bg-zinc-900/50 border border-zinc-800 rounded-md px-3 py-2">
                {profile.model_name}
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-500 mb-1">Temperature</label>
              <div className="text-sm text-zinc-200 bg-zinc-900/50 border border-zinc-800 rounded-md px-3 py-2">
                {profile.temperature}
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-500 mb-1">Max Turns</label>
              <div className="text-sm text-zinc-200 bg-zinc-900/50 border border-zinc-800 rounded-md px-3 py-2">
                {profile.max_turns}
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'tools' && (
        <div className="pt-4 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-zinc-200">Enabled Tools</h3>
            <button className="text-xs bg-zinc-100 text-zinc-900 px-3 py-1.5 rounded hover:bg-white font-medium">
              Save Changes
            </button>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {allTools?.map(tool => (
              <div 
                key={tool.id} 
                className={`p-4 rounded-lg border flex items-start gap-3 cursor-pointer transition-colors ${
                  isToolEnabled(tool.id) 
                    ? 'border-zinc-500 bg-zinc-800/50' 
                    : 'border-zinc-800 bg-[#0A0A0A] hover:border-zinc-700'
                }`}
              >
                <div className="mt-0.5">
                  <input 
                    type="checkbox" 
                    checked={isToolEnabled(tool.id)} 
                    readOnly
                    className="rounded border-zinc-700 bg-zinc-900 text-white focus:ring-zinc-500"
                  />
                </div>
                <div>
                  <div className="text-sm font-medium text-zinc-200">{tool.name}</div>
                  <div className="text-xs text-zinc-500 mt-1 line-clamp-2">{tool.description}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'assignments' && (
        <div className="pt-4 text-sm text-zinc-400">
          Assignments view coming soon.
        </div>
      )}
    </div>
  );
}
