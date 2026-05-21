import client from './client';

// 链接管理
export const getLinks = (params?: { category?: string; active?: boolean }) =>
  client.get('/links', { params });

export const createLink = (data: { name: string; url: string; file_size?: number; category?: string }) =>
  client.post('/links', data);

export const updateLink = (id: number, data: Record<string, unknown>) =>
  client.put(`/links/${id}`, data);

export const deleteLink = (id: number) =>
  client.delete(`/links/${id}`);

export const verifyLink = (id: number) =>
  client.post(`/links/${id}/verify`);

// 任务管理
export const getTasks = (params?: { status?: string }) =>
  client.get('/tasks', { params });

export const createTask = (data: { link_id: number; name: string; concurrency?: number; target_bytes?: number; speed_limit?: number }) =>
  client.post('/tasks', data);

export const getTask = (id: number) =>
  client.get(`/tasks/${id}`);

export const startTask = (id: number) =>
  client.post(`/tasks/${id}/start`);

export const pauseTask = (id: number) =>
  client.post(`/tasks/${id}/pause`);

export const resumeTask = (id: number) =>
  client.post(`/tasks/${id}/resume`);

export const stopTask = (id: number) =>
  client.post(`/tasks/${id}/stop`);

export const deleteTask = (id: number) =>
  client.delete(`/tasks/${id}`);

export const stopAllTasks = () =>
  client.post('/tasks/stop-all');

// 流量统计
export const getTodayStats = () =>
  client.get('/flow/today');

export const getFlowSummary = (period: string, limit?: number) =>
  client.get('/flow/summary', { params: { period, limit } });

export const getFlowDetails = (params: { task_id?: number; from_date?: string; to_date?: string }) =>
  client.get('/flow/details', { params });

export const getRealtime = () =>
  client.get('/flow/realtime');

// 系统设置
export const getSettings = () =>
  client.get('/settings');

export const updateSettings = (settings: Record<string, string>) =>
  client.put('/settings', { settings });
