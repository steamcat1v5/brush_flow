import { useEffect, useState } from 'react';
import { Button, Card, Modal, Form, Input, InputNumber, Select, Space, Table, Tag, message, Popconfirm } from 'antd';
import { PlusOutlined, DeleteOutlined, CheckCircleOutlined, LinkOutlined } from '@ant-design/icons';
import { getLinks, createLink, deleteLink, verifyLink } from '../api';
import { formatBytes } from '../utils/format';

export default function Links() {
  const [links, setLinks] = useState<Record<string, unknown>[]>([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm();

  const load = () => getLinks().then((r) => setLinks(r.data));
  useEffect(() => { load(); }, []);

  const handleCreate = async () => {
    const values = await form.validateFields();
    await createLink(values);
    message.success('链接已添加');
    setModalOpen(false);
    form.resetFields();
    load();
  };

  const handleVerify = async (id: number) => {
    const res = await verifyLink(id);
    if (res.data.reachable) {
      message.success(`可达，文件大小: ${formatBytes(res.data.file_size)}`);
    } else {
      message.error(`不可达: ${res.data.error}`);
    }
    load();
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '名称', dataIndex: 'name' },
    {
      title: 'URL', dataIndex: 'url', ellipsis: true,
      render: (v: string) => <a href={v} target="_blank" rel="noreferrer">{v}</a>,
    },
    {
      title: '文件大小', dataIndex: 'file_size', width: 120,
      render: (v: number) => v > 0 ? formatBytes(v) : '未知',
    },
    {
      title: '分类', dataIndex: 'category', width: 100,
      render: (v: string) => <Tag>{v}</Tag>,
    },
    {
      title: '类型', dataIndex: 'is_builtin', width: 80,
      render: (v: boolean) => v ? <Tag color="blue">内置</Tag> : <Tag color="green">自定义</Tag>,
    },
    {
      title: '操作', width: 160,
      render: (_: unknown, record: Record<string, unknown>) => (
        <Space>
          <Button type="link" size="small" icon={<CheckCircleOutlined />} onClick={() => handleVerify(record.id as number)}>验证</Button>
          <Popconfirm title="确定删除?" onConfirm={() => { deleteLink(record.id as number).then(load); }}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Card
      title="链接管理"
      extra={<Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>添加链接</Button>}
    >
      <Table dataSource={links} columns={columns} rowKey="id" size="middle" />

      <Modal title="添加下载链接" open={modalOpen} onOk={handleCreate} onCancel={() => setModalOpen(false)}>
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="资源名称" />
          </Form.Item>
          <Form.Item name="url" label="URL" rules={[{ required: true }]}>
            <Input placeholder="https://..." prefix={<LinkOutlined />} />
          </Form.Item>
          <Form.Item name="file_size" label="文件大小 (字节)" initialValue={0}>
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="category" label="分类" initialValue="general">
            <Select>
              <Select.Option value="general">通用</Select.Option>
              <Select.Option value="speedtest">测速</Select.Option>
              <Select.Option value="mirror">镜像</Select.Option>
              <Select.Option value="software">软件</Select.Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
