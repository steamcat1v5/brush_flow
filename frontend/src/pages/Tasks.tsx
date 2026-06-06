import { useEffect, useState } from 'react';
import { Button, Card, Modal, Form, Input, InputNumber, Select, Space, Table, Tag, message, Popconfirm, Tooltip, Collapse } from 'antd';
import { PlusOutlined, PlayCircleOutlined, StopOutlined, DeleteOutlined, StopFilled, EditOutlined, InfoCircleOutlined, FileTextOutlined } from '@ant-design/icons';
import { getTasks, createTask, updateTask, startTask, pauseTask, resumeTask, stopTask, deleteTask, getLinks, stopAllTasks, getSettings } from '../api';
import TaskLogDrawer from '../components/TaskLogDrawer';
import CronScheduleInput from '../components/CronScheduleInput';

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

const statusLabels: Record<string, string> = {
  pending: '待启动',
  running: '运行中',
  paused: '已暂停',
  completed: '已完成',
  failed: '失败',
  stopped: '已停止',
};

export default function Tasks() {
  const [tasks, setTasks] = useState<any[]>([]);
  const [links, setLinks] = useState<any[]>([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingTask, setEditingTask] = useState<any>(null);
  const [settings, setSettings] = useState<any>(null);
  const [logDrawer, setLogDrawer] = useState<{ open: boolean; taskId: number; taskName: string }>(
    { open: false, taskId: 0, taskName: '' }
  );
  const [form] = Form.useForm();
  const autoStartCron = Form.useWatch('auto_start_cron', { form, preserve: true });
  const autoStopCron = Form.useWatch('auto_stop_cron', { form, preserve: true });

  const load = () => {
    getTasks().then((r) => setTasks(r.data));
    getLinks().then((r) => setLinks(r.data));
    getSettings().then((r) => setSettings(r.data.settings));
  };

  useEffect(() => {
    load();
    const timer = setInterval(load, 2000);
    return () => clearInterval(timer);
  }, []);

  const handleOpenCreate = () => {
    setEditingTask(null);
    form.resetFields();
    if (settings) {
      form.setFieldsValue({
        concurrency: Number(settings.default_task_concurrency || 5),
        speed_limit: Number(settings.speed_limit_per_conn || 0) / 1024,
      });
    }
    setModalOpen(true);
  };

  const handleOpenEdit = (task: any) => {
    setEditingTask(task);
    form.setFieldsValue({
      link_id: task.link_id,
      name: task.name,
      concurrency: task.concurrency,
      target_bytes: task.target_bytes / (1024 * 1024),
      speed_limit: task.speed_limit / 1024,
      auto_start_cron: task.auto_start_cron || undefined,
      auto_stop_cron: task.auto_stop_cron || undefined,
    });
    setModalOpen(true);
  };

  const handleSubmit = async () => {
    await form.validateFields();
    const values = form.getFieldsValue(true);
    const payload = {
      ...values,
      speed_limit: (values.speed_limit || 0) * 1024,
      target_bytes: (values.target_bytes || 0) * 1024 * 1024,
      auto_start_cron: values.auto_start_cron || null,
      auto_stop_cron: values.auto_stop_cron || null,
    };

    if (editingTask) {
      await updateTask(editingTask.id, payload);
      message.success('任务已更新');
      if (editingTask.status === 'running') {
        message.info('设置将在任务重启后生效');
      }
    } else {
      await createTask(payload);
      message.success('任务已创建');
    }

    setModalOpen(false);
    load();
  };

  const handleAction = async (action: string, id: number) => {
    if (action === 'start') {
      const res = await startTask(id);
      if (res.data.warning) {
        message.warning({
          content: res.data.warning,
          duration: 10, // 停留长一点，确保用户看到
        });
      } else {
        message.success('任务已启动');
      }
    }
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
      render: (s: string) => <Tag color={statusColors[s] || 'default'}>{statusLabels[s] || s}</Tag>,
    },
    {
      title: '已下载', dataIndex: 'total_downloaded', width: 120,
      render: (v: number) => formatBytes(v),
    },
    {
      title: '当前速度', dataIndex: 'current_speed', width: 120,
      render: (v: number) => formatBytes(v) + '/s',
    },
    { title: '并发', dataIndex: 'concurrency', width: 60 },
    {
      title: '定时启动', dataIndex: 'auto_start_cron', width: 100,
      render: (v: string | null) => v || '-',
    },
    {
      title: '定时停止', dataIndex: 'auto_stop_cron', width: 100,
      render: (v: string | null) => v || '-',
    },
    {
      title: '操作', width: 240,
      render: (_: unknown, record: any) => (
        <Space>
          {(record.status === 'pending' || record.status === 'stopped' || record.status === 'failed' || record.status === 'completed') && (
            <Button type="link" size="small" icon={<PlayCircleOutlined />} onClick={() => handleAction('start', record.id)}>启动</Button>
          )}
          {record.status === 'running' && (
            <Button type="link" size="small" danger icon={<StopOutlined />} onClick={() => handleAction('stop', record.id)}>停止</Button>
          )}
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleOpenEdit(record)}>编辑</Button>
          <Button type="link" size="small" icon={<FileTextOutlined />} onClick={() => setLogDrawer({ open: true, taskId: record.id, taskName: record.name })}>日志</Button>
          <Popconfirm title="确定删除?" onConfirm={() => handleAction('delete', record.id)}>
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
          <Button type="primary" icon={<PlusOutlined />} onClick={handleOpenCreate}>新建任务</Button>
        </Space>
      }
    >
      <Table dataSource={tasks} columns={columns} rowKey="id" size="middle" />

      <Modal
        title={editingTask ? "编辑下载任务" : "新建下载任务"}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item name="link_id" label="选择链接" rules={[{ required: true }]}>
            <Select placeholder="选择一个下载链接">
              {links.map((l: any) => (
                <Select.Option key={l.id} value={l.id}>
                  {l.name}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="name" label="任务名称" rules={[{ required: true }]}>
            <Input placeholder="输入任务名称" />
          </Form.Item>
          <Form.Item
            name="concurrency"
            label={
                <span>
                    并发数&nbsp;
                    <Tooltip title="单个任务占用的最大连接数，受系统全局并发限制。">
                        <InfoCircleOutlined />
                    </Tooltip>
                </span>
            }
            initialValue={5}
          >
            <InputNumber min={1} max={100} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="target_bytes" label="目标下载量 (MB, 0=无限)" initialValue={0}>
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item
            name="speed_limit"
            label={
                <span>
                    任务最大速度 (KB/s)&nbsp;
                    <Tooltip title="该任务下所有并发连接的总下载速度上限。">
                        <InfoCircleOutlined />
                    </Tooltip>
                </span>
            }
            initialValue={0}
          >
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
          <Collapse size="small" items={[{
            key: 'schedule',
            label: (
              <Space size="small">
                <span>定时设置</span>
                {autoStartCron ? <Tag color="green">启动</Tag> : null}
                {autoStopCron ? <Tag color="orange">停止</Tag> : null}
                {!autoStartCron && !autoStopCron ? <Tag>未启用</Tag> : null}
              </Space>
            ),
            children: (
              <>
                <Form.Item name="auto_start_cron" label="定时启动" style={{ marginBottom: 8 }}>
                  <CronScheduleInput />
                </Form.Item>
                <Form.Item name="auto_stop_cron" label="定时停止" style={{ marginBottom: 0 }}>
                  <CronScheduleInput />
                </Form.Item>
              </>
            ),
          }]} />
          {editingTask?.status === 'running' && (
            <div style={{ color: '#faad14', fontSize: '12px', marginTop: 8 }}>
              <InfoCircleOutlined /> 任务正在运行，修改后的设置将在下次启动时生效。
            </div>
          )}
        </Form>
      </Modal>

      <TaskLogDrawer
        open={logDrawer.open}
        onClose={() => setLogDrawer({ ...logDrawer, open: false })}
        taskId={logDrawer.taskId}
        taskType="download"
        taskName={logDrawer.taskName}
      />
    </Card>
  );
}
