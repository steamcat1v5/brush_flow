import { useEffect, useState } from 'react';
import { Button, Card, Form, Input, InputNumber, Switch, message } from 'antd';
import { getSettings, updateSettings } from '../api';

export default function Settings() {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getSettings().then((r) => {
      const s = r.data.settings;
      form.setFieldsValue({
        global_concurrency: Number(s.global_concurrency),
        default_task_concurrency: Number(s.default_task_concurrency),
        auto_start_enabled: s.auto_start_enabled === 'true',
        auto_start_cron: s.auto_start_cron,
        auto_stop_cron: s.auto_stop_cron,
        speed_limit_per_conn: Number(s.speed_limit_per_conn || 0) / 1024,
        daily_traffic_target_gb: Number(s.daily_traffic_target_gb || 0),
        global_speed_limit_kb: Number(s.global_speed_limit_kb || 0),
      });
    });
  }, [form]);

  const handleSave = async () => {
    setLoading(true);
    try {
      const values = form.getFieldsValue();
      await updateSettings({
        global_concurrency: String(values.global_concurrency),
        default_task_concurrency: String(values.default_task_concurrency),
        auto_start_enabled: String(values.auto_start_enabled),
        auto_start_cron: values.auto_start_cron,
        auto_stop_cron: values.auto_stop_cron,
        speed_limit_per_conn: String(values.speed_limit_per_conn * 1024),
        daily_traffic_target_gb: String(values.daily_traffic_target_gb),
        global_speed_limit_kb: String(values.global_speed_limit_kb),
      });
      message.success('设置已保存');
    } catch {
      message.error('保存失败');
    }
    setLoading(false);
  };

  return (
    <Card title="系统设置" extra={<Button type="primary" loading={loading} onClick={handleSave}>保存</Button>}>
      <Form form={form} layout="vertical" style={{ maxWidth: 500 }}>
        <Form.Item name="global_concurrency" label="全局最大并发数">
          <InputNumber min={1} max={200} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item name="default_task_concurrency" label="新任务默认并发数">
          <InputNumber min={1} max={100} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item name="speed_limit_per_conn" label="任务默认最大速度 (KB/s, 0=不限)">
          <InputNumber min={0} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item name="daily_traffic_target_gb" label="每日下载目标 (GB, 0=不限)">
          <InputNumber min={0} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item name="global_speed_limit_kb" label="全局最大下载速度 (KB/s, 0=不限)">
          <InputNumber min={0} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item name="auto_start_enabled" label="启用定时自动启动" valuePropName="checked">
          <Switch />
        </Form.Item>
        <Form.Item name="auto_start_cron" label="自动启动 Cron 表达式">
          <Input placeholder="0 0 * * *" />
        </Form.Item>
        <Form.Item name="auto_stop_cron" label="自动停止 Cron 表达式">
          <Input placeholder="0 8 * * *" />
        </Form.Item>
      </Form>
    </Card>
  );
}
