'use client';

import { useQuery } from '@tanstack/react-query';
import { profilesApi } from '@/lib/api/profiles';
import { Plus, Bot, Settings2 } from 'lucide-react';
import Link from 'next/link';

export default function ProfilesPage() {
  const { data: profiles, isLoading } = useQuery({
    queryKey: ['profiles'],
    queryFn: profilesApi.getProfiles,
  });

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Agent Profiles</h1>
          <p className="text-sm text-zinc-400 mt-1">Manage agent behaviors, models, and tool access.</p>
        </div>
        <button className="flex items-center gap-2 bg-zinc-100 hover:bg-white text-zinc-900 px-4 py-2 rounded-md text-sm font-medium transition-colors">
          <Plus size={16} />
          Create Profile
        </button>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1,2,3].map(i => (
             <div key={i} className="h-40 rounded-xl border border-zinc-800 bg-zinc-900/30 animate-pulse" />
          ))}
        </div>
      ) : (
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
                
                <h3 className="text-base font-medium text-zinc-100 group-hover:text-white transition-colors">{profile.name}</h3>
                <p className="text-sm text-zinc-500 mt-1 line-clamp-2 flex-1">
                  {profile.description || "No description provided."}
                </p>
                
                <div className="flex items-center gap-4 mt-6 pt-4 border-t border-zinc-800/50">
                  <div className="flex items-center gap-1.5 text-xs font-medium text-zinc-400">
                     <span className="w-2 h-2 rounded-full bg-blue-500"></span>
                     {profile.model_name}
                  </div>
                  <div className="flex items-center gap-1.5 text-xs text-zinc-500">
                    <Settings2 size={14} />
                    v{profile.version}
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
