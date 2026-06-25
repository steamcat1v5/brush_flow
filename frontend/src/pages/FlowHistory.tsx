import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Card, Radio, Space, Table, Tag, Tabs, Switch } from 'antd';
import { getFlowSummary, getTaskLogs } from '../api';
import FlowChart from '../components/FlowChart';
import type { TaskLogEntry } from '../types/task';
import { levelColors } from '../types/task';

type Period = 'hour' | 'day' | 'week' | 'month';

function usePersistedState<T>(key: string, defaultValue: T): [T, (v: T | ((prev: T) => T)) => void] {
  const [value, setValue] = useState<T>(() => {
    const stored = localStorage.getItem(key);
    return stored !== null ? (JSON.parse(stored) as T) : defaultValue;
  });
  const persistedSetValue = (v: T | ((prev: T) => T)) => {
    setValue((prev) => {
      const next = v instanceof Function ? v(prev) : v;
      localStorage.setItem(key, JSON.stringify(next));
      return next;
    });
  };
  return [value, persistedSetValue];
}

export default function FlowHistory() {
  const [searchParams] = useSearchParams();
  const initTaskId = searchParams.get('task_id');
  const initTaskType = searchParams.get('task_type');
  const initTab = initTaskId ? 'logs' : 'flow';

  const [period, setPeriod] = usePersistedState<Period>('flow_period', 'day');
  const [chartType, setChartType] = usePersistedState<'bar' | 'line'>('flow_chartType', 'bar');
  const [showSplit, setShowSplit] = usePersistedState<boolean>('flow_showSplit', false);
  const [data, setData] = useState<Array<{ period_key: string; total_bytes: number; download_bytes?: number; iptv_bytes?: number }>>([]);
  const [logs, setLogs] = useState<TaskLogEntry[]>([]);
  const [logFilter, setLogFilter] = useState<{ task_id?: number; task_type?: string }>({
    task_id: initTaskId ? Number(initTaskId) : undefined,
    task_type: initTaskType || undefined,
  });

  useEffect(() => {
    getFlowSummary(period, 60).then((r) => setData(r.data));
  }, [period]);

  useEffect(() => {
    getTaskLogs({ ...logFilter, limit: 200 }).then((r) => setLogs(r.data));
    const timer = setInterval(() => {
      getTaskLogs({ ...logFilter, limit: 200 }).then((r) => setLogs(r.data));
    }, 5000);
    return () => clearInterval(timer);
  }, [logFilter]);

  const labels: Record<Period, string> = { hour: '小时', day: '日', week: '周', month: '月' };

  const logColumns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    {
      title: '类型', dataIndex: 'task_type', width: 80,
      render: (v: string) => <Tag color={v === 'iptv' ? 'purple' : 'blue'}>{v}</Tag>,
    },
    { title: '任务ID', dataIndex: 'task_id', width: 80 },
    {
      title: '级别', dataIndex: 'level', width: 70,
      render: (v: string) => <Tag color={levelColors[v] || 'default'}>{v}</Tag>,
    },
    { title: '消息', dataIndex: 'message', ellipsis: true },
    {
      title: '时间', dataIndex: 'created_at', width: 180,
      render: (v: number) => v ? new Date(v * 1000).toLocaleString() : '-',
    },
  ];

  return (
    <Tabs
      defaultActiveKey={initTab}
      items={[
        {
          key: 'flow',
          label: '流量统计',
          children: (
            <Card
              extra={
                <Space>
                  <Radio.Group value={period} onChange={(e) => setPeriod(e.target.value)}>
                    <Radio.Button value="hour">按小时</Radio.Button>
                    <Radio.Button value="day">按日</Radio.Button>
                    <Radio.Button value="week">按周</Radio.Button>
                    <Radio.Button value="month">按月</Radio.Button>
                  </Radio.Group>
                  <Radio.Group value={chartType} onChange={(e) => setChartType(e.target.value)}>
                    <Radio.Button value="bar">柱状图</Radio.Button>
                    <Radio.Button value="line">折线图</Radio.Button>
                  </Radio.Group>
                  <span style={{ fontSize: 12 }}>
                    分类显示 <Switch size="small" checked={showSplit} onChange={setShowSplit} />
                  </span>
                </Space>
              }
            >
              <FlowChart data={data} title={`按${labels[period]}流量统计`} chartType={chartType} showSplit={showSplit} />
            </Card>
          ),
        },
        {
          key: 'logs',
          label: '任务日志',
          children: (
            <Card
              extra={
                <Space>
                  <Radio.Group
                    value={logFilter.task_type || 'all'}
                    onChange={(e) => {
                      const v = e.target.value;
                      setLogFilter((prev) => ({ ...prev, task_type: v === 'all' ? undefined : v }));
                    }}
                  >
                    <Radio.Button value="all">全部</Radio.Button>
                    <Radio.Button value="download">下载</Radio.Button>
                    <Radio.Button value="iptv">IPTV</Radio.Button>
                  </Radio.Group>
                  {logFilter.task_id && (
                    <Tag closable onClose={() => setLogFilter((prev) => ({ ...prev, task_id: undefined }))}>
                      任务 #{logFilter.task_id}
                    </Tag>
                  )}
                </Space>
              }
            >
              <Table dataSource={logs} columns={logColumns} rowKey="id" size="small" pagination={{ pageSize: 50 }} />
            </Card>
          ),
        },
      ]}
    />
  );
}
