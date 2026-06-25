import { useState } from 'react';
import { Modal, message } from 'antd';

/**
 * 任务日志抽屉的公共状态管理 Hook
 */
export function useLogDrawer() {
  const [logDrawer, setLogDrawer] = useState<{ open: boolean; taskId: number; taskName: string }>(
    { open: false, taskId: 0, taskName: '' }
  );

  const openLog = (taskId: number, taskName: string) => {
    setLogDrawer({ open: true, taskId, taskName });
  };

  const closeLog = () => {
    setLogDrawer((prev) => ({ ...prev, open: false }));
  };

  return { logDrawer, openLog, closeLog };
}

interface UseTaskActionsOptions {
  /** 启动任务的 API 调用 */
  startFn: (id: number) => Promise<{ data: { warning?: string } }>;
  /** 暂停任务的 API 调用 */
  pauseFn: (id: number) => Promise<unknown>;
  /** 恢复任务的 API 调用 */
  resumeFn: (id: number) => Promise<unknown>;
  /** 停止任务的 API 调用 */
  stopFn: (id: number) => Promise<unknown>;
  /** 删除任务的 API 调用 */
  deleteFn: (id: number) => Promise<unknown>;
  /** 操作完成后的刷新回调 */
  onRefresh: () => void;
  /** 任务类型的中文名（用于消息提示） */
  taskLabel?: string;
}

/**
 * 任务操作（启动/暂停/恢复/停止/删除）的公共逻辑 Hook
 */
export function useTaskActions({
  startFn, pauseFn, resumeFn, stopFn, deleteFn,
  onRefresh, taskLabel = '任务',
}: UseTaskActionsOptions) {
  const handleAction = async (action: string, id: number, status?: string) => {
    if (action === 'start') {
      // 已完成任务重启需确认，因为会重置下载量计数
      if (status === 'completed') {
        Modal.confirm({
          title: `重新启动已完成的${taskLabel}`,
          content: '该任务已达到目标下载量。重新启动将重置下载量计数为0，从0开始重新下载。确定要重新启动吗？',
          okText: '确定重启',
          cancelText: '取消',
          onOk: async () => {
            const res = await startFn(id);
            if (res.data.warning) {
              message.warning({ content: res.data.warning, duration: 10 });
            } else {
              message.success(`${taskLabel}已启动，下载量计数已重置`);
            }
            onRefresh();
          },
        });
        return;
      }
      const res = await startFn(id);
      if (res.data.warning) {
        message.warning({ content: res.data.warning, duration: 10 });
      } else {
        message.success(`${taskLabel}已启动`);
      }
    } else if (action === 'pause') await pauseFn(id);
    else if (action === 'resume') await resumeFn(id);
    else if (action === 'stop') await stopFn(id);
    else if (action === 'delete') await deleteFn(id);
    onRefresh();
  };

  return { handleAction };
}
