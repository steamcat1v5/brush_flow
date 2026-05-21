import { useEffect, useState } from 'react';
import { Button, Card, Modal, Form, Input, InputNumber, Select, Space, Table, Tag, message, Popconfirm } from 'antd';
import { PlusOutlined, PlayCircleOutlined, PauseOutlined, StopOutlined, DeleteOutlined, StopFilled } from '@ant-design/icons';
import { getTasks, createTask, startTask, pauseTask, resumeTask, stopTask, deleteTask, getLinks, stopAllTasks } from '../api';

function formatBytes(bytes: number): string {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
}

const statusColors: Record<string, string> = {
  pending: 'default',
  running: 'processing',
  paused: 'warning',
  completed: 'success',
  failed: 'error',
  stopped: 'default',
};

export default function Tasks() {
  const [tasks, setTasks] = useState<Record<string, unknown>[]>([]);
  const [links, setLinks] = useState<Record<string, unknown>[]>([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm();

  const load = () => {
    getTasks().then((r) => setTasks(r.data));
    getLinks().then((r) => setLinks(r.data));
  };

  useEffect(() => {
    load();
    const timer = setInterval(load, 2000); // 每2秒刷新一次任务列表以同步进度
    return () => clearInterval(timer);
  }, []);

  const handleCreate = async () => {
    const values = await form.validateFields();
    // 转换 KB/s 为 bytes/s
    if (values.speed_limit) {
      values.speed_limit = values.speed_limit * 1024;
    }
    // 转换 MB 为 bytes
    if (values.target_bytes) {
      values.target_bytes = values.target_bytes * 1024 * 1024;
    }
    await createTask(values);
    message.success('任务已创建');
    setModalOpen(false);
    form.resetFields();
    load();
  };

  const handleAction = async (action: string, id: number) => {
    if (action === 'start') await startTask(id);
    else if (action === 'pause') await pauseTask(id);
    else if (action === 'resume') await resumeTask(id);
    else if (action === 'stop') await stopTask(id);
    else if (action === 'delete') { await deleteTask(id); }
    load();
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '名称', dataIndex: 'name' },
    {
      title: '状态', dataIndex: 'status', width: 100,
      render: (s: string) => <Tag color={statusColors[s] || 'default'}>{s}</Tag>,
    },
    {
      title: '已下载', dataIndex: 'total_downloaded', width: 120,
      render: (v: number) => formatBytes(v),
    },
    {
      title: '当前速度', dataIndex: 'current_speed', width: 120,
      render: (v: number) => formatBytes(v) + '/s',
    },
    { title: '并发数', dataIndex: 'concurrency', width: 80 },
    {
      title: '操作', width: 200,
      render: (_: unknown, record: Record<string, unknown>) => (
        <Space>
          {(record.status === 'pending' || record.status === 'stopped' || record.status === 'failed') && (
            <Button type="link" size="small" icon={<PlayCircleOutlined />} onClick={() => handleAction('start', record.id as number)}>启动</Button>
          )}
          {record.status === 'running' && (
            <Button type="link" size="small" icon={<PauseOutlined />} onClick={() => handleAction('pause', record.id as number)}>暂停</Button>
          )}
          {record.status === 'paused' && (
            <Button type="link" size="small" icon={<PlayCircleOutlined />} onClick={() => handleAction('resume', record.id as number)}>恢复</Button>
          )}
          {(record.status === 'running' || record.status === 'paused') && (
            <Button type="link" size="small" danger icon={<StopOutlined />} onClick={() => handleAction('stop', record.id as number)}>停止</Button>
          )}
          <Popconfirm title="确定删除?" onConfirm={() => handleAction('delete', record.id as number)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Card
      title="任务管理"
      extra={
        <Space>
          <Popconfirm title="确定停止所有运行中的任务?" onConfirm={async () => { await stopAllTasks(); load(); }}>
            <Button danger icon={<StopFilled />}>全部停止</Button>
          </Popconfirm>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>新建任务</Button>
        </Space>
      }
    >
      <Table dataSource={tasks} columns={columns} rowKey="id" size="middle" />

      <Modal title="新建下载任务" open={modalOpen} onOk={handleCreate} onCancel={() => setModalOpen(false)}>
        <Form form={form} layout="vertical">
          <Form.Item name="link_id" label="选择链接" rules={[{ required: true }]}>
            <Select placeholder="选择一个下载链接">
              {links.map((l: Record<string, unknown>) => (
                <Select.Option key={l.id as number} value={l.id as number}>
                  {l.name as string}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="name" label="任务名称" rules={[{ required: true }]}>
            <Input placeholder="输入任务名称" />
          </Form.Item>
          <Form.Item name="concurrency" label="并发数" initialValue={5}>
            <InputNumber min={1} max={100} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="target_bytes" label="目标下载量 (MB, 0=无限)" initialValue={0}>
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="speed_limit" label="单连接限速 (KB/s, 0=不限)" initialValue={0}>
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
