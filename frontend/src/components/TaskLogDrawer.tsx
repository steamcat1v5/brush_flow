import { useEffect, useState } from 'react';
import { Drawer, Table, Tag } from 'antd';
import { getTaskLogs } from '../api';

interface TaskLogEntry {
  id: number;
  task_id: number;
  task_type: string;
  level: string;
  message: string;
  created_at: string;
}

const levelColors: Record<string, string> = {
  info: 'blue',
  warn: 'orange',
  error: 'red',
};

function formatBytes(bytes: number): string {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
}

function formatMessage(msg: string): string {
  // 将消息中紧跟"下载: "或"下载:"后面的数字格式化为可读大小
  return msg.replace(/(下载[：:]\s*)(\d{4,})/g, (_, prefix, num) => {
    return prefix + formatBytes(Number(num));
  });
}

interface TaskLogDrawerProps {
  open: boolean;
  onClose: () => void;
  taskId: number;
  taskType: 'download' | 'iptv';
  taskName?: string;
}

export default function TaskLogDrawer({ open, onClose, taskId, taskName }: TaskLogDrawerProps) {
  const [logs, setLogs] = useState<TaskLogEntry[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    const load = () => {
      setLoading(true);
      getTaskLogs({ task_id: taskId, limit: 200 })
        .then((r) => setLogs(r.data))
        .finally(() => setLoading(false));
    };
    load();
    const timer = setInterval(load, 3000);
    return () => clearInterval(timer);
  }, [open, taskId]);

  const columns = [
    {
      title: '级别', dataIndex: 'level', width: 70,
      render: (v: string) => <Tag color={levelColors[v] || 'default'}>{v}</Tag>,
    },
    { title: '消息', dataIndex: 'message', ellipsis: true, render: (v: string) => formatMessage(v) },
    {
      title: '时间', dataIndex: 'created_at', width: 170,
      render: (v: number) => v ? new Date(v * 1000).toLocaleString() : '-',
    },
  ];

  return (
    <Drawer
      title={`任务日志 - ${taskName || `#${taskId}`}`}
      open={open}
      onClose={onClose}
      width={600}
      destroyOnClose
    >
      <Table
        dataSource={logs}
        columns={columns}
        rowKey="id"
        size="small"
        loading={loading}
        pagination={{ pageSize: 50, size: 'small' }}
      />
    </Drawer>
  );
}
