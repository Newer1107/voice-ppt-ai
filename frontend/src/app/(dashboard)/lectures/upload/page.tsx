'use client';

import { useEffect, useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { projectsApi } from '@/lib/api/projects';
import { lecturesApi, voiceApi } from '@/lib/api/lectures';
import type { Project } from '@/types/project';
import type { VoiceProfile } from '@/types/lecture';
import { Upload, File, X, Check } from 'lucide-react';

export default function UploadLecturePage() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [voiceProfiles, setVoiceProfiles] = useState<VoiceProfile[]>([]);
  const [selectedProject, setSelectedProject] = useState('');
  const [title, setTitle] = useState('');
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [pptxFile, setPptxFile] = useState<File | null>(null);
  const [selectedVoice, setSelectedVoice] = useState('');
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState<{ id: string; title: string; project_id: string } | null>(null);
  const [error, setError] = useState('');
  const videoRef = useRef<HTMLInputElement>(null);
  const audioRef = useRef<HTMLInputElement>(null);
  const pptxRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const [p, v] = await Promise.all([
          projectsApi.list({ page_size: 100 }),
          voiceApi.list(),
        ]);
        setProjects(p.items);
        setVoiceProfiles(v);
      } catch (err) {
        console.error('Failed to load data:', err);
      }
    };
    load();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedProject || !title) {
      setError('Please fill in all required fields');
      return;
    }
    if (!videoFile && !audioFile) {
      setError('Please select at least one video or audio file');
      return;
    }

    setError('');
    setUploading(true);
    setProgress(0);

    const formData = new FormData();
    formData.append('project_id', selectedProject);
    formData.append('title', title);
    if (videoFile) formData.append('video_file', videoFile);
    if (audioFile) formData.append('audio_file', audioFile);
    if (pptxFile) formData.append('pptx_file', pptxFile);
    if (selectedVoice) formData.append('voice_profile_id', selectedVoice);

    try {
      const res = await lecturesApi.upload(formData, setProgress);
      setResult({ id: res.id, title: res.title, project_id: selectedProject });
    } catch (err: any) {
      const msg = err?.response?.data?.error?.message || 'Upload failed';
      setError(msg);
    } finally {
      setUploading(false);
    }
  };

  if (result) {
    return (
      <div className="max-w-2xl mx-auto">
        <div className="bg-white dark:bg-slate-950 rounded-xl border border-slate-200 dark:border-slate-800 p-8 text-center">
          <div className="w-16 h-16 bg-green-100 dark:bg-green-950 rounded-full flex items-center justify-center mx-auto mb-4">
            <Check className="w-8 h-8 text-green-600" />
          </div>
          <h2 className="text-xl font-bold mb-2">Upload Successful!</h2>
          <p className="text-slate-500 mb-2">{result.title}</p>
          <p className="text-sm text-slate-400 mb-6">
            Your lecture is being processed. You can check its status from the project page.
          </p>
          <div className="flex justify-center gap-3">
            <button
              onClick={() => router.push(`/projects/${result.project_id}`)}
              className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors"
            >
              View Project
            </button>
            <button
              onClick={() => {
                setResult(null);
                setVideoFile(null);
                setAudioFile(null);
                setPptxFile(null);
                setTitle('');
                setProgress(0);
              }}
              className="px-4 py-2 border border-slate-300 dark:border-slate-700 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-900 transition-colors"
            >
              Upload Another
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold">Upload Lecture</h1>
        <p className="text-slate-500 dark:text-slate-400 mt-1">
          Upload a video or audio lecture with optional slides
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="bg-white dark:bg-slate-950 rounded-xl border border-slate-200 dark:border-slate-800 p-6 space-y-4">
          <h2 className="font-semibold">Project & Title</h2>

          <div>
            <label className="block text-sm font-medium mb-1">Project *</label>
            <select
              value={selectedProject}
              onChange={(e) => setSelectedProject(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-900 focus:outline-none focus:ring-2 focus:ring-primary/50"
              required
            >
              <option value="">Select a project</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>{p.title}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Title *</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-900 focus:outline-none focus:ring-2 focus:ring-primary/50"
              placeholder="Physics 101 - Lecture 1"
              required
            />
          </div>
        </div>

        <div className="bg-white dark:bg-slate-950 rounded-xl border border-slate-200 dark:border-slate-800 p-6 space-y-4">
          <h2 className="font-semibold">Media Files</h2>
          <p className="text-sm text-slate-500">Select at least one video or audio file</p>

          {/* Video */}
          <div
            className="border-2 border-dashed border-slate-300 dark:border-slate-700 rounded-lg p-6 text-center cursor-pointer hover:border-primary transition-colors"
            onClick={() => videoRef.current?.click()}
          >
            <input
              ref={videoRef}
              type="file"
              accept=".mp4,.mov,.mkv,.webm"
              className="hidden"
              onChange={(e) => setVideoFile(e.target.files?.[0] || null)}
            />
            {videoFile ? (
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <File className="w-5 h-5 text-primary" />
                  <span className="text-sm">{videoFile.name}</span>
                </div>
                <button onClick={(e) => { e.stopPropagation(); setVideoFile(null); }} className="text-red-500">
                  <X className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <div>
                <Upload className="w-8 h-8 mx-auto mb-2 text-slate-400" />
                <p className="text-sm text-slate-500">Click to upload video (MP4, MOV, MKV)</p>
              </div>
            )}
          </div>

          {/* Audio */}
          <div
            className="border-2 border-dashed border-slate-300 dark:border-slate-700 rounded-lg p-6 text-center cursor-pointer hover:border-primary transition-colors"
            onClick={() => audioRef.current?.click()}
          >
            <input
              ref={audioRef}
              type="file"
              accept=".mp3,.wav,.m4a,.aac,.ogg"
              className="hidden"
              onChange={(e) => setAudioFile(e.target.files?.[0] || null)}
            />
            {audioFile ? (
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <File className="w-5 h-5 text-primary" />
                  <span className="text-sm">{audioFile.name}</span>
                </div>
                <button onClick={(e) => { e.stopPropagation(); setAudioFile(null); }} className="text-red-500">
                  <X className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <div>
                <Upload className="w-8 h-8 mx-auto mb-2 text-slate-400" />
                <p className="text-sm text-slate-500">Click to upload audio (MP3, WAV, M4A)</p>
              </div>
            )}
          </div>

          {/* PPTX */}
          <div
            className="border-2 border-dashed border-slate-300 dark:border-slate-700 rounded-lg p-6 text-center cursor-pointer hover:border-primary transition-colors"
            onClick={() => pptxRef.current?.click()}
          >
            <input
              ref={pptxRef}
              type="file"
              accept=".pptx"
              className="hidden"
              onChange={(e) => setPptxFile(e.target.files?.[0] || null)}
            />
            {pptxFile ? (
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <File className="w-5 h-5 text-primary" />
                  <span className="text-sm">{pptxFile.name}</span>
                </div>
                <button onClick={(e) => { e.stopPropagation(); setPptxFile(null); }} className="text-red-500">
                  <X className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <div>
                <Upload className="w-8 h-8 mx-auto mb-2 text-slate-400" />
                <p className="text-sm text-slate-500">Click to upload slides (PPTX, optional)</p>
              </div>
            )}
          </div>
        </div>

        <div className="bg-white dark:bg-slate-950 rounded-xl border border-slate-200 dark:border-slate-800 p-6">
          <h2 className="font-semibold mb-4">Voice Profile (Optional)</h2>
          <select
            value={selectedVoice}
            onChange={(e) => setSelectedVoice(e.target.value)}
            className="w-full px-3 py-2 border border-slate-300 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-900 focus:outline-none focus:ring-2 focus:ring-primary/50"
          >
            <option value="">Default voice</option>
            {voiceProfiles.filter(v => v.status === 'ready').map((vp) => (
              <option key={vp.id} value={vp.id}>{vp.name}</option>
            ))}
          </select>
        </div>

        {error && (
          <div className="text-red-500 text-sm bg-red-50 dark:bg-red-950/50 p-3 rounded-lg">
            {error}
          </div>
        )}

        {uploading && (
          <div className="bg-white dark:bg-slate-950 rounded-xl border border-slate-200 dark:border-slate-800 p-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium">Uploading...</span>
              <span className="text-sm text-slate-500">{progress}%</span>
            </div>
            <div className="w-full bg-slate-200 dark:bg-slate-800 rounded-full h-2">
              <div
                className="bg-primary rounded-full h-2 transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}

        <button
          type="submit"
          disabled={uploading}
          className="w-full py-3 px-6 bg-primary text-white rounded-lg font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
        >
          {uploading ? 'Uploading...' : 'Upload Lecture'}
        </button>
      </form>
    </div>
  );
}
