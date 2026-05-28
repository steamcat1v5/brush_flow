import { useEffect, useState, useRef, useCallback } from 'react';
import {
  Button, Card, Modal, Form, Input, InputNumber, Select, Space, Table, Tag,
  message, Popconfirm, Switch, Divider, List, Drawer, Collapse, Empty,
} from 'antd';
import {
  PlusOutlined, PlayCircleOutlined, PauseOutlined, StopOutlined,
  DeleteOutlined, StopFilled, EditOutlined, SyncOutlined, EyeOutlined,
  VideoCameraOutlined, UnorderedListOutlined,
} from '@ant-design/icons';
import Hls from 'hls.js';
import {
  getIptvSources, createIptvSource, deleteIptvSource, refreshIptvSource,
  getIptvChannels, getIptvTasks, createIptvTask, updateIptvTask,
  deleteIptvTask, startIptvTask, pauseIptvTask, resumeIptvTask,
  stopIptvTask, stopAllIptvTasks,
} from '../api';

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

interface IptvSource {
  id: number;
  name: string;
  m3u_url: string;
  channel_count: number;
  last_parsed_at: string | null;
}

interface IptvChannel {
  id: number;
  source_id: number;
  name: string;
  group_title: string;
  hls_url: string;
}

interface IptvTask {
  id: number;
  source_id: number;
  channel_id: number;
  channel_name: string;
  name: string;
  status: string;
  speed_limit: number;
  target_bytes: number;
  total_downloaded: number;
  current_speed: number;
  auto_switch_enabled: boolean;
  auto_switch_interval: number;
  switch_mode: string;
  created_at: string;
}

// ---- 视频预览组件 ----
function VideoPreview({ url, onClose }: { url: string; onClose: () => void }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const hlsRef = useRef<Hls | null>(null);

  // 通过后端代理访问，解决 CORS 和网络限制
  const proxyUrl = `/api/iptv/proxy?url=${encodeURIComponent(url)}`;

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    if (Hls.isSupported()) {
      const hls = new Hls({
        xhrSetup: (xhr, requestUrl) => {
          // 将所有 HLS 请求通过代理转发
          if (requestUrl.startsWith('http')) {
            xhr.open('GET', `/api/iptv/proxy?url=${encodeURIComponent(requestUrl)}`, true);
          }
        },
      });
      hls.loadSource(proxyUrl);
      hls.attachMedia(video);
      hls.on(Hls.Events.MANIFEST_PARSED, () => video.play().catch(() => {}));
      hls.on(Hls.Events.ERROR, (_event, data) => {
        if (data.fatal) {
          message.error('视频流加载失败');
          onClose();
        }
      });
      hlsRef.current = hls;
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = proxyUrl;
      video.addEventListener('loadedmetadata', () => video.play().catch(() => {}));
    } else {
      message.error('当前浏览器不支持 HLS 播放');
      onClose();
    }

    return () => {
      if (hlsRef.current) {
        hlsRef.current.destroy();
        hlsRef.current = null;
      }
    };
  }, [proxyUrl, onClose]);

  return (
    <video
      ref={videoRef}
      controls
      autoPlay
      muted
      style={{ width: '100%', maxHeight: '70vh', background: '#000' }}
    />
  );
}

// ---- 主页面 ----
export default function IPTV() {
  const [sources, setSources] = useState<IptvSource[]>([]);
  const [tasks, setTasks] = useState<IptvTask[]>([]);

  // 频道抽屉
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerSource, setDrawerSource] = useState<IptvSource | null>(null);
  const [drawerChannels, setDrawerChannels] = useState<IptvChannel[]>([]);

  // 视频预览
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewUrl, setPreviewUrl] = useState('');
  const [previewName, setPreviewName] = useState('');

  // 弹窗
  const [sourceModalOpen, setSourceModalOpen] = useState(false);
  const [taskModalOpen, setTaskModalOpen] = useState(false);
  const [editingTask, setEditingTask] = useState<IptvTask | null>(null);
  const [selectedSourceId, setSelectedSourceId] = useState<number | null>(null);
  const [taskFormChannels, setTaskFormChannels] = useState<IptvChannel[]>([]);
  const [taskFormGroups, setTaskFormGroups] = useState<string[]>([]);

  const [sourceForm] = Form.useForm();
  const [taskForm] = Form.useForm();

  const load = useCallback(() => {
    getIptvSources().then((r) => setSources(r.data));
    getIptvTasks().then((r) => setTasks(r.data));
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(load, 2000);
    return () => clearInterval(timer);
  }, [load]);

  // ---- 频道抽屉 ----
  const handleOpenDrawer = async (source: IptvSource) => {
    setDrawerSource(source);
    setDrawerOpen(true);
    const r = await getIptvChannels(source.id);
    setDrawerChannels(r.data);
  };

  const getGroupedChannels = () => {
    const groups: Record<string, IptvChannel[]> = {};
    for (const ch of drawerChannels) {
      const g = ch.group_title || 'Other';
      if (!groups[g]) groups[g] = [];
      groups[g].push(ch);
    }
    return groups;
  };

  // ---- 视频预览 ----
  const handlePreview = (channel: IptvChannel) => {
    setPreviewUrl(channel.hls_url);
    setPreviewName(channel.name);
    setPreviewOpen(true);
  };

  // ---- 从抽屉快速创建任务 ----
  const handleQuickCreateTask = (source: IptvSource, channel: IptvChannel) => {
    setDrawerOpen(false);
    setEditingTask(null);
    taskForm.resetFields();
    setSelectedSourceId(source.id);
    // 加载频道列表
    getIptvChannels(source.id).then((r) => {
      setTaskFormChannels(r.data);
      const groups = [...new Set(r.data.map((c: IptvChannel) => c.group_title))];
      setTaskFormGroups(groups);
    });
    taskForm.setFieldsValue({
      source_id: source.id,
      channel_id: channel.id,
      name: channel.name,
    });
    setTaskModalOpen(true);
  };

  // ---- m3u 源操作 ----
  const handleAddSource = async () => {
    const values = await sourceForm.validateFields();
    await createIptvSource(values);
    message.success('m3u 源已添加并解析');
    setSourceModalOpen(false);
    sourceForm.resetFields();
    load();
  };

  const handleDeleteSource = async (id: number) => {
    await deleteIptvSource(id);
    message.success('源已删除');
    load();
  };

  const handleRefreshSource = async (id: number) => {
    const res = await refreshIptvSource(id);
    message.success(`已刷新，共 ${res.data.channel_count} 个频道`);
    load();
  };

  // ---- IPTV 任务操作 ----
  const handleOpenCreate = () => {
    setEditingTask(null);
    taskForm.resetFields();
    setSelectedSourceId(null);
    setTaskFormChannels([]);
    setTaskFormGroups([]);
    setTaskModalOpen(true);
  };

  const handleOpenEdit = (task: IptvTask) => {
    setEditingTask(task);
    setSelectedSourceId(task.source_id);
    getIptvChannels(task.source_id).then((r) => {
      setTaskFormChannels(r.data);
      const groups = [...new Set(r.data.map((c: IptvChannel) => c.group_title))];
      setTaskFormGroups(groups);
    });
    taskForm.setFieldsValue({
      source_id: task.source_id,
      channel_id: task.channel_id,
      name: task.name,
      speed_limit: task.speed_limit / 1024,
      target_bytes: task.target_bytes / (1024 * 1024),
      auto_switch_enabled: task.auto_switch_enabled,
      auto_switch_interval: task.auto_switch_interval / 60,
      switch_mode: task.switch_mode,
    });
    setTaskModalOpen(true);
  };

  const handleSourceChange = (sourceId: number) => {
    setSelectedSourceId(sourceId);
    getIptvChannels(sourceId).then((r) => {
      setTaskFormChannels(r.data);
      const groups = [...new Set(r.data.map((c: IptvChannel) => c.group_title))];
      setTaskFormGroups(groups);
    });
    taskForm.setFieldValue('channel_id', undefined);
  };

  const handleSubmitTask = async () => {
    const values = await taskForm.validateFields();
    const payload = {
      ...values,
      speed_limit: (values.speed_limit || 0) * 1024,
      target_bytes: (values.target_bytes || 0) * 1024 * 1024,
      auto_switch_interval: (values.auto_switch_interval || 30) * 60,
    };

    if (editingTask) {
      await updateIptvTask(editingTask.id, payload);
      message.success('IPTV 任务已更新');
    } else {
      await createIptvTask(payload);
      message.success('IPTV 任务已创建');
    }

    setTaskModalOpen(false);
    load();
  };

  const handleAction = async (action: string, id: number) => {
    if (action === 'start') {
      const res = await startIptvTask(id);
      if (res.data.warning) {
        message.warning({ content: res.data.warning, duration: 10 });
      } else {
        message.success('IPTV 任务已启动');
      }
    } else if (action === 'pause') await pauseIptvTask(id);
    else if (action === 'resume') await resumeIptvTask(id);
    else if (action === 'stop') await stopIptvTask(id);
    else if (action === 'delete') await deleteIptvTask(id);
    load();
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '名称', dataIndex: 'name' },
    {
      title: '频道', dataIndex: 'channel_name', width: 120,
      render: (v: string) => v || '-',
    },
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
    {
      title: '自动换台', dataIndex: 'auto_switch_enabled', width: 90,
      render: (v: boolean, record: IptvTask) =>
        v ? <Tag color="blue">{Math.round(record.auto_switch_interval / 60)}分</Tag> : <Tag>关</Tag>,
    },
    {
      title: '操作', width: 240,
      render: (_: unknown, record: IptvTask) => (
        <Space>
          {(record.status === 'pending' || record.status === 'stopped' || record.status === 'failed' || record.status === 'completed') && (
            <Button type="link" size="small" icon={<PlayCircleOutlined />} onClick={() => handleAction('start', record.id)}>启动</Button>
          )}
          {record.status === 'running' && (
            <Button type="link" size="small" icon={<PauseOutlined />} onClick={() => handleAction('pause', record.id)}>暂停</Button>
          )}
          {record.status === 'paused' && (
            <Button type="link" size="small" icon={<PlayCircleOutlined />} onClick={() => handleAction('resume', record.id)}>恢复</Button>
          )}
          {(record.status === 'running' || record.status === 'paused') && (
            <Button type="link" size="small" danger icon={<StopOutlined />} onClick={() => handleAction('stop', record.id)}>停止</Button>
          )}
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleOpenEdit(record)}>编辑</Button>
          <Popconfirm title="确定删除?" onConfirm={() => handleAction('delete', record.id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const groupedChannels = getGroupedChannels();

  return (
    <div>
      {/* m3u 源管理 */}
      <Card
        title="m3u 源"
        size="small"
        style={{ marginBottom: 16 }}
        extra={
          <Button size="small" icon={<PlusOutlined />} onClick={() => { sourceForm.resetFields(); setSourceModalOpen(true); }}>
            添加源
          </Button>
        }
      >
        {sources.length === 0 ? (
          <div style={{ color: '#999', padding: 16, textAlign: 'center' }}>
            暂无 m3u 源，请点击"添加源"导入 IPTV 播放列表
          </div>
        ) : (
          <List
            size="small"
            dataSource={sources}
            renderItem={(source) => (
              <List.Item
                actions={[
                  <Button key="channels" type="link" size="small" icon={<UnorderedListOutlined />}
                    onClick={() => handleOpenDrawer(source)}>查看频道</Button>,
                  <Button key="refresh" type="link" size="small" icon={<SyncOutlined />}
                    onClick={() => handleRefreshSource(source.id)}>刷新</Button>,
                  <Popconfirm key="del" title="删除此源及其所有频道?" onConfirm={() => handleDeleteSource(source.id)}>
                    <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
                  </Popconfirm>,
                ]}
              >
                <List.Item.Meta
                  title={source.name}
                  description={
                    <Space size="small">
                      <Tag>{source.channel_count} 个频道</Tag>
                      {source.last_parsed_at && (
                        <span style={{ color: '#999', fontSize: 12 }}>
                          上次解析: {new Date(source.last_parsed_at).toLocaleString()}
                        </span>
                      )}
                    </Space>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </Card>

      {/* IPTV 任务管理 */}
      <Card
        title="IPTV 任务"
        extra={
          <Space>
            <Popconfirm title="确定停止所有运行中的 IPTV 任务?" onConfirm={async () => { await stopAllIptvTasks(); load(); }}>
              <Button danger icon={<StopFilled />}>全部停止</Button>
            </Popconfirm>
            <Button type="primary" icon={<PlusOutlined />} onClick={handleOpenCreate}>新建任务</Button>
          </Space>
        }
      >
        <Table dataSource={tasks} columns={columns} rowKey="id" size="middle" />
      </Card>

      {/* 频道列表抽屉 */}
      <Drawer
        title={drawerSource ? `${drawerSource.name} - 频道列表` : '频道列表'}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={420}
      >
        {drawerChannels.length === 0 ? (
          <Empty description="暂无频道" />
        ) : (
          <Collapse
            defaultActiveKey={Object.keys(groupedChannels)}
            items={Object.entries(groupedChannels).map(([group, channels]) => ({
              key: group,
              label: `${group} (${channels.length})`,
              children: (
                <List
                  size="small"
                  dataSource={channels}
                  renderItem={(ch) => (
                    <List.Item
                      actions={[
                        <Button key="preview" type="link" size="small" icon={<EyeOutlined />}
                          onClick={() => handlePreview(ch)}>预览</Button>,
                        <Button key="task" type="link" size="small" icon={<VideoCameraOutlined />}
                          onClick={() => handleQuickCreateTask(drawerSource!, ch)}>创建任务</Button>,
                      ]}
                    >
                      <List.Item.Meta title={ch.name} />
                    </List.Item>
                  )}
                />
              ),
            }))}
          />
        )}
      </Drawer>

      {/* 视频预览弹窗 */}
      <Modal
        title={`预览: ${previewName}`}
        open={previewOpen}
        onCancel={() => {
          setPreviewOpen(false);
          setPreviewUrl('');
        }}
        footer={null}
        destroyOnClose
        width={720}
      >
        {previewOpen && previewUrl && (
          <VideoPreview url={previewUrl} onClose={() => setPreviewOpen(false)} />
        )}
      </Modal>

      {/* 添加源弹窗 */}
      <Modal
        title="添加 m3u 源"
        open={sourceModalOpen}
        onOk={handleAddSource}
        onCancel={() => setSourceModalOpen(false)}
        destroyOnClose
      >
        <Form form={sourceForm} layout="vertical">
          <Form.Item name="name" label="源名称" rules={[{ required: true }]}>
            <Input placeholder="例如：上海联通 IPTV" />
          </Form.Item>
          <Form.Item name="m3u_url" label="m3u 地址" rules={[{ required: true }]}>
            <Input placeholder="https://example.com/playlist.m3u" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 创建/编辑 IPTV 任务弹窗 */}
      <Modal
        title={editingTask ? "编辑 IPTV 任务" : "新建 IPTV 任务"}
        open={taskModalOpen}
        onOk={handleSubmitTask}
        onCancel={() => setTaskModalOpen(false)}
        destroyOnClose
        width={520}
      >
        <Form form={taskForm} layout="vertical">
          <Form.Item name="source_id" label="选择 m3u 源" rules={[{ required: true }]}>
            <Select placeholder="选择一个 m3u 源" onChange={handleSourceChange}>
              {sources.map((s) => (
                <Select.Option key={s.id} value={s.id}>{s.name} ({s.channel_count} 频道)</Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="channel_id" label="选择频道" rules={[{ required: true }]}>
            <Select placeholder="选择一个频道" showSearch optionFilterProp="label">
              {taskFormGroups.map((group) => (
                <Select.OptGroup key={group} label={group}>
                  {taskFormChannels.filter((c) => c.group_title === group).map((c) => (
                    <Select.Option key={c.id} value={c.id} label={c.name}>{c.name}</Select.Option>
                  ))}
                </Select.OptGroup>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="name" label="任务名称" rules={[{ required: true }]}>
            <Input placeholder="输入任务名称" />
          </Form.Item>
          <Form.Item name="speed_limit" label="任务最大速度 (KB/s, 0=不限)" initialValue={0}>
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="target_bytes" label="目标下载量 (MB, 0=无限)" initialValue={0}>
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>

          <Divider>自动换台</Divider>

          <Form.Item name="auto_switch_enabled" label="启用自动换台" valuePropName="checked" initialValue={false}>
            <Switch />
          </Form.Item>
          <Form.Item name="auto_switch_interval" label="换台间隔 (分钟)" initialValue={30}>
            <InputNumber min={1} max={1440} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="switch_mode" label="换台模式" initialValue="random">
            <Select>
              <Select.Option value="random">随机</Select.Option>
              <Select.Option value="sequential">顺序</Select.Option>
            </Select>
          </Form.Item>

          {editingTask?.status === 'running' && (
            <div style={{ color: '#faad14', fontSize: '12px' }}>
              任务正在运行，修改后的设置将在下次启动时生效。
            </div>
          )}
        </Form>
      </Modal>
    </div>
  );
}
