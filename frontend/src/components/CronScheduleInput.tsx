import { useState } from 'react';
import { Input, InputNumber, Switch, Space, Select } from 'antd';

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

export function buildCron(hour: number, minute: number, weekday: string): string {
  return `${minute} ${hour} * * ${weekday}`;
}

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
}

export default function CronScheduleInput({ value, onChange }: CronScheduleInputProps) {
  const enabled = !!value;
  const [advanced, setAdvanced] = useState(() => {
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

  const handleEnable = (checked: boolean) => {
    if (checked) {
      onChange?.(buildCron(0, 0, '*'));
    } else {
      onChange?.(undefined);
      setAdvanced(false);
    }
  };

  const handleSimpleChange = (h: number, m: number, w: string) => {
    onChange?.(buildCron(h, m, w));
  };

  if (!enabled) {
    return (
      <Space>
        <Switch size="small" checked={false} onChange={handleEnable} />
        <span style={{ color: '#999', fontSize: 13 }}>未启用</span>
      </Space>
    );
  }

  return (
    <Space size="small" wrap>
      <Switch size="small" checked onChange={handleEnable} />
      {advanced ? (
        <Input
          value={value}
          onChange={(e) => onChange?.(e.target.value || undefined)}
          placeholder="分 时 日 月 周"
          style={{ width: 180 }}
          size="small"
        />
      ) : (
        <>
          <InputNumber
            min={0}
            max={23}
            value={hour}
            onChange={(h) => handleSimpleChange(h ?? 0, minute, weekday)}
            style={{ width: 64 }}
            size="small"
            addonAfter="时"
          />
          <InputNumber
            min={0}
            max={59}
            value={minute}
            onChange={(m) => handleSimpleChange(hour, m ?? 0, weekday)}
            style={{ width: 64 }}
            size="small"
            addonAfter="分"
          />
          <Select
            value={weekday}
            onChange={(w) => handleSimpleChange(hour, minute, w)}
            style={{ width: 80 }}
            size="small"
            options={WEEKDAY_OPTIONS}
          />
        </>
      )}
      <Switch
        size="small"
        checked={advanced}
        onChange={setAdvanced}
        checkedChildren="cron"
        unCheckedChildren="cron"
      />
    </Space>
  );
}
