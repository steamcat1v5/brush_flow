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

export const updateTask = (id: number, data: Record<string, unknown>) =>
  client.put(`/tasks/${id}`, data);

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

// 任务日志
export const getTaskLogs = (params?: { task_id?: number; task_type?: string; limit?: number }) =>
  client.get('/flow/logs', { params });

// 系统设置
export const getSettings = () =>
  client.get('/settings');

export const updateSettings = (settings: Record<string, string>) =>
  client.put('/settings', { settings });

// IPTV 源管理
export const getIptvSources = () =>
  client.get('/iptv/sources');

export const createIptvSource = (data: { name: string; m3u_url: string }) =>
  client.post('/iptv/sources', data);

export const deleteIptvSource = (id: number) =>
  client.delete(`/iptv/sources/${id}`);

export const refreshIptvSource = (id: number) =>
  client.post(`/iptv/sources/${id}/refresh`);

// IPTV 频道
export const getIptvChannels = (sourceId: number, group?: string) =>
  client.get(`/iptv/sources/${sourceId}/channels`, { params: group ? { group } : {} });

// IPTV 任务管理
export const getIptvTasks = () =>
  client.get('/iptv/tasks');

export const createIptvTask = (data: {
  source_id: number; channel_id: number; name: string;
  speed_limit?: number; target_bytes?: number;
  auto_switch_enabled?: boolean; auto_switch_interval?: number; switch_mode?: string;
}) => client.post('/iptv/tasks', data);

export const updateIptvTask = (id: number, data: Record<string, unknown>) =>
  client.put(`/iptv/tasks/${id}`, data);

export const deleteIptvTask = (id: number) =>
  client.delete(`/iptv/tasks/${id}`);

export const startIptvTask = (id: number) =>
  client.post(`/iptv/tasks/${id}/start`);

export const pauseIptvTask = (id: number) =>
  client.post(`/iptv/tasks/${id}/pause`);

export const resumeIptvTask = (id: number) =>
  client.post(`/iptv/tasks/${id}/resume`);

export const stopIptvTask = (id: number) =>
  client.post(`/iptv/tasks/${id}/stop`);

export const stopAllIptvTasks = () =>
  client.post('/iptv/tasks/stop-all');
