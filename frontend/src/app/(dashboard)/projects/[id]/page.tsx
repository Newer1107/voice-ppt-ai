'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { projectsApi } from '@/lib/api/projects';
import { lecturesApi } from '@/lib/api/lectures';
import type { ProjectDetail } from '@/types/project';
import type { LectureSummary } from '@/types/lecture';
import { ArrowLeft, Plus, Trash2, FileText, Video, Music } from 'lucide-react';

export default function ProjectDetailPage() {
  const params = useParams();
  const router = useRouter();
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [lectures, setLectures] = useState<LectureSummary[]>([]);
  const [lecturesLoading, setLecturesLoading] = useState(true);
  const [loading, setLoading] = useState(true);
  const [showDelete, setShowDelete] = useState(false);

  const loadProject = async () => {
    try {
      const id = params.id as string;
      const p = await projectsApi.get(id);
      setProject(p);
      setLectures(p.lectures);
    } catch (err) {
      console.error('Failed to load project:', err);
    } finally {
      setLoading(false);
      setLecturesLoading(false);
    }
  };

  useEffect(() => {
    loadProject();
  }, [params.id]);

  const handleDelete = async () => {
    try {
      await projectsApi.delete(params.id as string);
      router.push('/dashboard');
    } catch (err) {
      console.error('Failed to delete project:', err);
    }
  };

  if (loading) {
    return <div className="text-center py-12 text-slate-500">Loading...</div>;
  }

  if (!project) {
    return (
      <div className="text-center py-12">
        <p className="text-slate-500">Project not found</p>
        <Link href="/dashboard" className="text-primary hover:underline mt-4 inline-block">
          Back to Dashboard
        </Link>
      </div>
    );
  }

  const inputTypeIcon = (type: string) => {
    switch (type) {
      case 'video': return <Video className="w-4 h-4" />;
      case 'audio': return <Music className="w-4 h-4" />;
      default: return <FileText className="w-4 h-4" />;
    }
  };

  const statusBadge = (status: string) => {
    const colors: Record<string, string> = {
      pending: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-950 dark:text-yellow-400',
      processing: 'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-400',
      completed: 'bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-400',
      failed: 'bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-400',
    };
    return colors[status] || 'bg-slate-100 text-slate-600';
  };

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <Link href="/dashboard" className="flex items-center gap-2 text-sm text-slate-500 hover:text-slate-700 mb-4">
          <ArrowLeft className="w-4 h-4" />
          Back to Dashboard
        </Link>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">{project.title}</h1>
            {project.description && (
              <p className="text-slate-500 mt-1">{project.description}</p>
            )}
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/lectures/upload"
              className="flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors"
            >
              <Plus className="w-4 h-4" />
              Upload Lecture
            </Link>
            <button
              onClick={() => setShowDelete(true)}
              className="p-2 text-red-500 hover:bg-red-50 dark:hover:bg-red-950/50 rounded-lg transition-colors"
            >
              <Trash2 className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>

      {/* Lectures List */}
      <div className="bg-white dark:bg-slate-950 rounded-xl border border-slate-200 dark:border-slate-800">
        <div className="p-6 border-b border-slate-200 dark:border-slate-800">
          <h2 className="text-lg font-semibold">Lectures</h2>
        </div>

        {lectures.length === 0 ? (
          <div className="p-12 text-center text-slate-500">
            <FileText className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p className="text-lg font-medium mb-2">No lectures yet</p>
            <p className="mb-4">Upload a lecture to get started</p>
            <Link
              href="/lectures/upload"
              className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors inline-block"
            >
              Upload Lecture
            </Link>
          </div>
        ) : (
          <div className="divide-y divide-slate-200 dark:divide-slate-800">
            {lectures.map((lecture) => (
              <div key={lecture.id} className="flex items-center justify-between p-4">
                <div className="flex items-center gap-3">
                  {inputTypeIcon(lecture.input_type)}
                  <div>
                    <h3 className="font-medium">{lecture.title}</h3>
                    <p className="text-sm text-slate-500">
                      {lecture.duration_seconds
                        ? `${Math.floor(lecture.duration_seconds / 60)} min`
                        : '—'}
                    </p>
                  </div>
                </div>
                <span className={`px-2 py-1 rounded-full text-xs font-medium ${statusBadge(lecture.status)}`}>
                  {lecture.status}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Delete Confirmation */}
      {showDelete && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-slate-950 rounded-xl border border-slate-200 dark:border-slate-800 p-6 w-full max-w-md mx-4">
            <h2 className="text-lg font-semibold mb-2">Delete Project</h2>
            <p className="text-slate-500 mb-4">
              Are you sure you want to delete &quot;{project.title}&quot;? This action cannot be undone.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowDelete(false)}
                className="px-4 py-2 border border-slate-300 dark:border-slate-700 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-900 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                className="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
