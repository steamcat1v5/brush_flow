/** 任务状态对应的 Ant Design Tag 颜色 */
export const statusColors: Record<string, string> = {
  pending: 'default',
  running: 'processing',
  paused: 'warning',
  completed: 'success',
  failed: 'error',
  stopped: 'default',
};

/** 任务状态对应的中文标签 */
export const statusLabels: Record<string, string> = {
  pending: '待启动',
  running: '运行中',
  paused: '已暂停',
  completed: '已完成',
  failed: '失败',
  stopped: '已停止',
};
