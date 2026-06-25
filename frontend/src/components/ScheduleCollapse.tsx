import { Space, Tag, Collapse } from 'antd';
import { Form } from 'antd';
import CronScheduleInput from './CronScheduleInput';

interface ScheduleCollapseProps {
  /** Form 实例 */
  form: ReturnType<typeof Form.useForm>[0];
  /** 可选的额外 Collapse 样式 */
  style?: React.CSSProperties;
}

/**
 * 定时启动/停止的 Collapse 设置面板，Tasks.tsx 和 IPTV.tsx 共用。
 */
export default function ScheduleCollapse({ form, style }: ScheduleCollapseProps) {
  const autoStartCron = Form.useWatch('auto_start_cron', { form, preserve: true });
  const autoStopCron = Form.useWatch('auto_stop_cron', { form, preserve: true });

  return (
    <Collapse size="small" style={style} items={[{
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
  );
}
