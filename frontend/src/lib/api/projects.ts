import { apiClient } from './client';
import type { Project, PaginatedResponse } from '@/types/project';

export interface CreateProjectData {
  title: string;
  description?: string;
}

export interface UpdateProjectData {
  title?: string;
  description?: string;
  status?: string;
}

export const projectsApi = {
  list: async (params?: {
    page?: number;
    page_size?: number;
    status?: string;
  }): Promise<PaginatedResponse<Project>> => {
    const res = await apiClient.get('/api/v1/projects', { params });
    return res.data;
  },

  create: async (data: CreateProjectData): Promise<Project> => {
    const res = await apiClient.post('/api/v1/projects', data);
    return res.data;
  },

  get: async (id: string): Promise<Project> => {
    const res = await apiClient.get(`/api/v1/projects/${id}`);
    return res.data;
  },

  update: async (id: string, data: UpdateProjectData): Promise<Project> => {
    const res = await apiClient.put(`/api/v1/projects/${id}`, data);
    return res.data;
  },

  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/api/v1/projects/${id}`);
  },
};
