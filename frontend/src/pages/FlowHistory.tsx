import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Card, Radio, Space, Table, Tag, Tabs, Switch } from 'antd';
import { getFlowSummary, getTaskLogs } from '../api';
import FlowChart from '../components/FlowChart';

type Period = 'day' | 'week' | 'month';

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

export default function FlowHistory() {
  const [searchParams] = useSearchParams();
  const initTaskId = searchParams.get('task_id');
  const initTaskType = searchParams.get('task_type');
  const initTab = initTaskId ? 'logs' : 'flow';

  const [period, setPeriod] = useState<Period>('day');
  const [chartType, setChartType] = useState<'bar' | 'line'>('bar');
  const [showSplit, setShowSplit] = useState(false);
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

  const labels: Record<Period, string> = { day: '日', week: '周', month: '月' };

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
