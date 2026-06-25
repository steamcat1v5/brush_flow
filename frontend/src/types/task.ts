/** 任务日志条目接口 */
export interface TaskLogEntry {
  id: number;
  task_id: number;
  task_type: string;
  level: string;
  message: string;
  created_at: string;
}

/** 日志级别对应的 Tag 颜色 */
export const levelColors: Record<string, string> = {
  info: 'blue',
  warn: 'orange',
  error: 'red',
};
