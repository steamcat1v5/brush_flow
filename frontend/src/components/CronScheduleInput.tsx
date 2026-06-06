import { useState } from 'react';
import { Form, Input, InputNumber, Switch, Space, Select } from 'antd';

const WEEKDAY_OPTIONS = [
  { label: '每天', value: '*' },
  { label: '工作日', value: '1-5' },
  { label: '周末', value: '0,6' },
  { label: '周一', value: '1' },
  { label: '周二', value: '2' },
  { label: '周三', value: '3' },
  { label: '周四', value: '4' },
  { label: '周五', value: '5' },
  { label: '周六', value: '6' },
  { label: '周日', value: '0' },
];

/** 将 hour + minute + weekday 组合为 cron 表达式 */
export function buildCron(hour: number, minute: number, weekday: string): string {
  return `${minute} ${hour} * * ${weekday}`;
}

/** 尝试从 cron 表达式解析出 hour, minute, weekday */
export function parseCron(cron: string): { hour: number; minute: number; weekday: string } | null {
  if (!cron) return null;
  const parts = cron.trim().split(/\s+/);
  if (parts.length !== 5) return null;
  const minute = parseInt(parts[0], 10);
  const hour = parseInt(parts[1], 10);
  if (isNaN(minute) || isNaN(hour)) return null;
  return { hour, minute, weekday: parts[4] };
}

interface CronScheduleInputProps {
  value?: string;
  onChange?: (value: string | undefined) => void;
  label: string;
}

export default function CronScheduleInput({ value, onChange, label }: CronScheduleInputProps) {
  const [advanced, setAdvanced] = useState(() => {
    // 如果已有的 cron 不能被简易选择器解析，则默认切到高级模式
    if (value) {
      const parts = value.trim().split(/\s+/);
      return parts.length !== 5 || parts[2] !== '*' || parts[3] !== '*';
    }
    return false;
  });

  const parsed = parseCron(value || '');
  const hour = parsed?.hour ?? 0;
  const minute = parsed?.minute ?? 0;
  const weekday = parsed?.weekday ?? '*';

  const handleSimpleChange = (h: number, m: number, w: string) => {
    onChange?.(buildCron(h, m, w));
  };

  const handleAdvancedChange = (cron: string) => {
    onChange?.(cron || undefined);
  };

  const handleAdvancedToggle = (checked: boolean) => {
    setAdvanced(checked);
    if (!checked && value) {
      // 切回简易模式时，尝试保留时间
      const p = parseCron(value);
      if (p) {
        onChange?.(buildCron(p.hour, p.minute, '*'));
      } else {
        onChange?.(undefined);
      }
    }
  };

  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 4 }}>
        <span style={{ fontSize: 13, color: '#666' }}>{label}</span>
        <Switch
          size="small"
          checked={advanced}
          onChange={handleAdvancedToggle}
          checkedChildren="cron"
          unCheckedChildren="cron"
          style={{ marginLeft: 8 }}
        />
      </div>
      {advanced ? (
        <Input
          value={value || ''}
          onChange={(e) => handleAdvancedChange(e.target.value)}
          placeholder="分 时 日 月 周  (留空=不启用)"
          style={{ width: '100%' }}
        />
      ) : (
        <Space>
          <InputNumber
            min={0}
            max={23}
            value={hour}
            onChange={(h) => handleSimpleChange(h ?? 0, minute, weekday)}
            style={{ width: 70 }}
            addonAfter="时"
          />
          <InputNumber
            min={0}
            max={59}
            value={minute}
            onChange={(m) => handleSimpleChange(hour, m ?? 0, weekday)}
            style={{ width: 70 }}
            addonAfter="分"
          />
          <Select
            value={weekday}
            onChange={(w) => handleSimpleChange(hour, minute, w)}
            style={{ width: 100 }}
            options={WEEKDAY_OPTIONS}
          />
        </Space>
      )}
    </div>
  );
}
