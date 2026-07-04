import { apiClient } from './client';
import type { LoginRequest, RegisterRequest, TokenResponse, User } from '@/types/auth';

export const authApi = {
  register: async (data: RegisterRequest): Promise<User> => {
    const res = await apiClient.post('/api/v1/auth/register', data);
    return res.data;
  },

  login: async (data: LoginRequest): Promise<TokenResponse> => {
    const res = await apiClient.post('/api/v1/auth/login', data);
    return res.data;
  },

  refresh: async (refreshToken: string): Promise<{ access_token: string; expires_in: number }> => {
    const res = await apiClient.post('/api/v1/auth/refresh', {
      refresh_token: refreshToken,
    });
    return res.data;
  },

  getMe: async (): Promise<User> => {
    const res = await apiClient.get('/api/v1/auth/me');
    return res.data;
  },
};
