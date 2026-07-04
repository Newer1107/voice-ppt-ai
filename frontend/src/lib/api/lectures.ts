import { apiClient } from './client';
import type { LectureDetail, LectureStatus, VoiceProfile } from '@/types/lecture';

export const lecturesApi = {
  upload: async (
    formData: FormData,
    onProgress?: (pct: number) => void,
  ): Promise<{ id: string; title: string; input_type: string; status: string; job_id?: string; created_at: string }> => {
    const res = await apiClient.post('/api/v1/lectures/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (onProgress && e.total) {
          onProgress(Math.round((e.loaded / e.total) * 100));
        }
      },
    });
    return res.data;
  },

  get: async (id: string): Promise<LectureDetail> => {
    const res = await apiClient.get(`/api/v1/lectures/${id}`);
    return res.data;
  },

  getStatus: async (id: string): Promise<LectureStatus> => {
    const res = await apiClient.get(`/api/v1/lectures/${id}/status`);
    return res.data;
  },
};

export const voiceApi = {
  list: async (): Promise<VoiceProfile[]> => {
    const res = await apiClient.get('/api/v1/voice-profiles');
    return res.data;
  },

  create: async (formData: FormData): Promise<VoiceProfile> => {
    const res = await apiClient.post('/api/v1/voice-profiles', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },

  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/api/v1/voice-profiles/${id}`);
  },
};
