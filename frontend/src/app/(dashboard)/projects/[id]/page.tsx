'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { projectsApi } from '@/lib/api/projects';
import { apiClient } from '@/lib/api/client';
import { lecturesApi } from '@/lib/api/lectures';
import type { ProjectDetail } from '@/types/project';
import type { LectureSummary } from '@/types/lecture';
import { toast } from 'sonner';
import { ArrowLeft, Plus, Trash2, FileText, Video, Music } from 'lucide-react';

export default function ProjectDetailPage() {
  const params = useParams();
  const router = useRouter();
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [lectures, setLectures] = useState<LectureSummary[]>([]);
  const [lecturesLoading, setLecturesLoading] = useState(true);
  const [loading, setLoading] = useState(true);
  const [showDelete, setShowDelete] = useState(false);
  const [lectureUrls, setLectureUrls] = useState<Record<string, string>>({});

  const loadProject = async () => {
    try {
      const id = params.id as string;
      const p = await projectsApi.get(id);
      setProject(p);
      setLectures(p.lectures);
    } catch (err) {
      toast.error('Failed to load project');
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
      toast.error('Failed to delete project');
    }
  };

  const downloadFile = async (url: string, filename: string) => {
    try {
      const res = await apiClient.get(url, { responseType: 'blob' });
      const blobUrl = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = filename.endsWith('.pptx') ? filename : `${filename}.pptx`;
      a.click();
      URL.revokeObjectURL(blobUrl);
    } catch {
      toast.error('Failed to download file');
    }
  };

  useEffect(() => {
    const hasProcessing = lectures.some(
      (l) => l.status === 'processing' || l.status === 'pending',
    );
    if (!hasProcessing) return;

    const interval = setInterval(async () => {
      try {
        const p = await projectsApi.get(params.id as string);
        setProject(p);
        setLectures(p.lectures);
      } catch {
        // retry on next tick
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [lectures, params.id]);

  useEffect(() => {
    lectures.forEach((lecture) => {
      if (
        lecture.status === 'completed' &&
        !lectureUrls[lecture.id] &&
        !lecture.narrated_pptx_url
      ) {
        lecturesApi.get(lecture.id).then((detail) => {
          if (detail.narrated_pptx_url) {
            setLectureUrls((prev) => ({
              ...prev,
              [lecture.id]: detail.narrated_pptx_url!,
            }));
          }
        }).catch(() => {});
      }
    });
  }, [lectures, lectureUrls]);

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
                <div className="flex items-center gap-2">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${statusBadge(lecture.status)}`}>
                    {lecture.status}
                  </span>
                  {lecture.status === 'completed' && (lecture.narrated_pptx_url || lectureUrls[lecture.id]) && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        downloadFile(
                          lecture.narrated_pptx_url || lectureUrls[lecture.id]!,
                          `${lecture.title}.pptx`,
                        );
                      }}
                      className="px-3 py-1 bg-green-600 text-white text-xs rounded hover:bg-green-700 whitespace-nowrap"
                    >
                      Download PPTX
                    </button>
                  )}
                </div>
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
