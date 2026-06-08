import apiClient from './client';
import type { AuthTokens, User } from '@/types';

export const authApi = {
  login: async (email: string, password: string) => {
    const res = await apiClient.post<AuthTokens & { user_id: string; role: string; full_name: string }>(
      '/auth/login', { email, password }
    );
    return res.data;
  },

  register: async (data: { email: string; password: string; first_name: string; last_name: string; role?: string }) => {
    const res = await apiClient.post<AuthTokens>('/auth/register', data);
    return res.data;
  },

  getMe: async () => {
    const res = await apiClient.get<User>('/auth/me');
    return res.data;
  },

  refresh: async (refreshToken: string) => {
    const res = await apiClient.post<AuthTokens>('/auth/refresh', { refresh_token: refreshToken });
    return res.data;
  },
};

export const exerciseApi = {
  list: async () => {
    const res = await apiClient.get('/exercises/');
    return res.data;
  },
  get: async (id: string) => {
    const res = await apiClient.get(`/exercises/${id}`);
    return res.data;
  },
  seed: async () => {
    const res = await apiClient.post('/exercises/seed');
    return res.data;
  },
};

export const sessionApi = {
  create: async (exerciseId: string, mode: string = 'live') => {
    const res = await apiClient.post('/sessions/', { exercise_id: exerciseId, mode });
    return res.data;
  },
  list: async (limit = 20, skip = 0) => {
    const res = await apiClient.get(`/sessions/?limit=${limit}&skip=${skip}`);
    return res.data;
  },
  get: async (id: string) => {
    const res = await apiClient.get(`/sessions/${id}`);
    return res.data;
  },
  complete: async (id: string, notes?: string) => {
    const res = await apiClient.put(`/sessions/${id}/complete`, null, { params: { notes } });
    return res.data;
  },
  uploadVideo: async (sessionId: string, file: File) => {
    const form = new FormData();
    form.append('video', file);
    const res = await apiClient.post(`/sessions/${sessionId}/upload-video`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },
  getAngleData: async (sessionId: string) => {
    const res = await apiClient.get(`/sessions/${sessionId}/angle-data`);
    return res.data;
  },
  getPS2Results: async (sessionId: string) => {
    const res = await apiClient.get(`/sessions/${sessionId}/ps2-results`);
    return res.data;
  },
};

export const analyticsApi = {
  summary: async (patientId: string) => {
    const res = await apiClient.get(`/analytics/patient/${patientId}/summary`);
    return res.data;
  },
  weekly: async (patientId: string, weeks = 8) => {
    const res = await apiClient.get(`/analytics/patient/${patientId}/weekly?weeks=${weeks}`);
    return res.data;
  },
  romTrends: async (patientId: string, days = 30) => {
    const res = await apiClient.get(`/analytics/patient/${patientId}/rom-trends?days=${days}`);
    return res.data;
  },
  exerciseBreakdown: async (patientId: string) => {
    const res = await apiClient.get(`/analytics/patient/${patientId}/exercise-breakdown`);
    return res.data;
  },
};

export const sensorApi = {
  status: async () => {
    const res = await apiClient.get('/sensor/status');
    return res.data;
  },
  data: async () => {
    const res = await apiClient.get('/sensor/data');
    return res.data;
  },
};

export const notificationApi = {
  list: async () => {
    const res = await apiClient.get('/notifications/');
    return res.data;
  },
  unreadCount: async () => {
    const res = await apiClient.get('/notifications/unread-count');
    return res.data;
  },
  markRead: async (id: string) => {
    await apiClient.put(`/notifications/${id}/read`);
  },
  markAllRead: async () => {
    await apiClient.put('/notifications/mark-all-read');
  },
};

export const reportApi = {
  generate: async (patientId: string, reportType = 'session') => {
    const res = await apiClient.post(`/reports/generate?patient_id=${patientId}&report_type=${reportType}`);
    return res.data;
  },
  list: async (patientId: string) => {
    const res = await apiClient.get(`/reports/patient/${patientId}`);
    return res.data;
  },
};

export const patientApi = {
  list: async () => {
    const res = await apiClient.get('/patients/');
    return res.data;
  },
  get: async (id: string) => {
    const res = await apiClient.get(`/patients/${id}`);
    return res.data;
  },
  getSessions: async (id: string) => {
    const res = await apiClient.get(`/patients/${id}/sessions`);
    return res.data;
  },
  getAnalytics: async (id: string) => {
    const res = await apiClient.get(`/patients/${id}/analytics`);
    return res.data;
  },
  getPlan: async (id: string) => {
    const res = await apiClient.get(`/patients/${id}/plan`);
    return res.data;
  },
};
