'use client';

import { useEffect, useState, useRef } from 'react';
import { voiceApi } from '@/lib/api/lectures';
import type { VoiceProfile } from '@/types/lecture';
import { toast } from 'sonner';
import { Mic, Plus, Trash2, Upload } from 'lucide-react';

export default function VoiceProfilesPage() {
  const [profiles, setProfiles] = useState<VoiceProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState('');
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [consent, setConsent] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');
  const audioRef = useRef<HTMLInputElement>(null);

  const loadProfiles = async () => {
    try {
      const list = await voiceApi.list();
      setProfiles(list);
    } catch (err) {
      toast.error('Failed to load voice profiles');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProfiles();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !audioFile || !consent) {
      setError('Please fill all fields and consent to voice cloning');
      return;
    }

    setCreating(true);
    setError('');

    const formData = new FormData();
    formData.append('name', name);
    formData.append('audio_file', audioFile);
    formData.append('consent', 'true');

    try {
      await voiceApi.create(formData);
      setShowCreate(false);
      setName('');
      setAudioFile(null);
      setConsent(false);
      loadProfiles();
    } catch (err: any) {
      setError(err?.response?.data?.error?.message || 'Failed to create profile');
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await voiceApi.delete(id);
      loadProfiles();
    } catch (err) {
      toast.error('Failed to delete voice profile');
    }
  };

  const statusBadge = (status: string) => {
    const colors: Record<string, string> = {
      pending: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-950 dark:text-yellow-400',
      cloning: 'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-400',
      ready: 'bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-400',
      failed: 'bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-400',
    };
    return colors[status] || 'bg-slate-100 text-slate-600';
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold">Voice Profiles</h1>
          <p className="text-slate-500 dark:text-slate-400 mt-1">
            Manage voice cloning profiles for narration
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors"
        >
          <Plus className="w-4 h-4" />
          New Profile
        </button>
      </div>

      <div className="bg-white dark:bg-slate-950 rounded-xl border border-slate-200 dark:border-slate-800">
        {loading ? (
          <div className="p-12 text-center text-slate-500">Loading...</div>
        ) : profiles.length === 0 ? (
          <div className="p-12 text-center text-slate-500">
            <Mic className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p className="text-lg font-medium mb-2">No voice profiles yet</p>
            <p className="mb-4">Upload a voice sample to create a custom narration voice</p>
            <button
              onClick={() => setShowCreate(true)}
              className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors"
            >
              Create Profile
            </button>
          </div>
        ) : (
          <div className="divide-y divide-slate-200 dark:divide-slate-800">
            {profiles.map((profile) => (
              <div key={profile.id} className="flex items-center justify-between p-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-primary/10 rounded-lg">
                    <Mic className="w-5 h-5 text-primary" />
                  </div>
                  <div>
                    <h3 className="font-medium">{profile.name}</h3>
                    <p className="text-sm text-slate-500">
                      Created {new Date(profile.created_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${statusBadge(profile.status)}`}>
                    {profile.status}
                  </span>
                  <button
                    onClick={() => handleDelete(profile.id)}
                    className="p-2 text-red-500 hover:bg-red-50 dark:hover:bg-red-950/50 rounded-lg transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create Dialog */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-slate-950 rounded-xl border border-slate-200 dark:border-slate-800 p-6 w-full max-w-md mx-4">
            <h2 className="text-lg font-semibold mb-4">Create Voice Profile</h2>
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Name *</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-900 focus:outline-none focus:ring-2 focus:ring-primary/50"
                  placeholder="My Teaching Voice"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">Audio Sample *</label>
                <div
                  className="border-2 border-dashed border-slate-300 dark:border-slate-700 rounded-lg p-4 text-center cursor-pointer hover:border-primary transition-colors"
                  onClick={() => audioRef.current?.click()}
                >
                  <input
                    ref={audioRef}
                    type="file"
                    accept=".mp3,.wav,.m4a,.aac"
                    className="hidden"
                    onChange={(e) => setAudioFile(e.target.files?.[0] || null)}
                  />
                  {audioFile ? (
                    <div className="flex items-center justify-center gap-2">
                      <Upload className="w-4 h-4 text-primary" />
                      <span className="text-sm">{audioFile.name}</span>
                    </div>
                  ) : (
                    <p className="text-sm text-slate-500">
                      Click to upload (MP3, WAV, M4A — min 30 seconds)
                    </p>
                  )}
                </div>
              </div>

              <label className="flex items-start gap-2">
                <input
                  type="checkbox"
                  checked={consent}
                  onChange={(e) => setConsent(e.target.checked)}
                  className="mt-1"
                />
                <span className="text-sm text-slate-600 dark:text-slate-400">
                  I consent to my voice being cloned for narration purposes
                </span>
              </label>

              {error && (
                <div className="text-red-500 text-sm bg-red-50 dark:bg-red-950/50 p-3 rounded-lg">
                  {error}
                </div>
              )}

              <div className="flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setShowCreate(false)}
                  className="px-4 py-2 border border-slate-300 dark:border-slate-700 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-900 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 disabled:opacity-50 transition-colors"
                >
                  {creating ? 'Creating...' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
