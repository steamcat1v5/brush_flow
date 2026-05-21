import { useEffect, useState } from 'react';
import { Card, Radio, Space } from 'antd';
import { getFlowSummary } from '../api';
import FlowChart from '../components/FlowChart';

type Period = 'day' | 'week' | 'month';

export default function FlowHistory() {
  const [period, setPeriod] = useState<Period>('day');
  const [data, setData] = useState<Array<{ period_key: string; total_bytes: number }>>([]);

  useEffect(() => {
    getFlowSummary(period, 60).then((r) => setData(r.data));
  }, [period]);

  const labels: Record<Period, string> = { day: '日', week: '周', month: '月' };

  return (
    <Card
      title="流量历史"
      extra={
        <Space>
          <Radio.Group value={period} onChange={(e) => setPeriod(e.target.value)}>
            <Radio.Button value="day">按日</Radio.Button>
            <Radio.Button value="week">按周</Radio.Button>
            <Radio.Button value="month">按月</Radio.Button>
          </Radio.Group>
        </Space>
      }
    >
      <FlowChart data={data} title={`按${labels[period]}流量统计`} />
    </Card>
  );
}
