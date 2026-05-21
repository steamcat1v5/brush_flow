import { useEffect, useState } from 'react';
import { Card, Col, Row, Statistic, Tag, Progress } from 'antd';
import {
  ArrowDownOutlined,
  ThunderboltOutlined,
  PlayCircleOutlined,
} from '@ant-design/icons';
import { getTodayStats, getFlowSummary, getSettings } from '../api';
import { useWebSocket } from '../hooks/useWebSocket';
import FlowChart from '../components/FlowChart';

function formatBytes(bytes: number): string {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
}

function formatSpeed(bytesPerSec: number): string {
  return formatBytes(bytesPerSec) + '/s';
}

export default function Dashboard() {
  const [today, setToday] = useState({ total_bytes: 0, current_speed: 0, active_tasks: 0, uptime_seconds: 0 });
  const [dailyData, setDailyData] = useState<Array<{ period_key: string; total_bytes: number }>>([]);
  const [targetGb, setTargetGb] = useState(0);
  const { data: wsData, connected } = useWebSocket();

  useEffect(() => {
    getTodayStats().then((r) => setToday(r.data));
    getFlowSummary('day', 30).then((r) => setDailyData(r.data));
    getSettings().then((r) => {
        setTargetGb(Number(r.data.settings.daily_traffic_target_gb || 0));
    });
  }, []);

  const currentSpeed = wsData?.total_bytes_per_sec ?? today.current_speed;
  const totalBytes = wsData?.total_bytes ?? today.total_bytes;

  // 动态更新图表中的今日数据
  const chartData = [...dailyData];
  if (chartData.length > 0) {
    const todayStr = new Date().toISOString().split('T')[0];
    if (chartData[0].period_key === todayStr) {
      chartData[0] = { ...chartData[0], total_bytes: totalBytes };
    }
  }

  const currentGb = totalBytes / (1024 ** 3);
  const percent = targetGb > 0 ? Math.min(100, Math.round((currentGb / targetGb) * 100)) : 0;

  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="今日下载量"
              value={formatBytes(totalBytes)}
              prefix={<ArrowDownOutlined />}
            />
            {targetGb > 0 && (
                <div style={{ marginTop: 8 }}>
                    <div style={{ fontSize: 12, color: '#999', marginBottom: 4 }}>目标: {targetGb} GB</div>
                    <Progress percent={percent} size="small" />
                </div>
            )}
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="当前速度"
              value={formatSpeed(currentSpeed)}
              prefix={<ThunderboltOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="活跃任务"
              value={today.active_tasks}
              prefix={<PlayCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <div style={{ fontSize: 14, color: '#999', marginBottom: 8 }}>WebSocket</div>
            <Tag color={connected ? 'green' : 'red'}>
              {connected ? '已连接' : '未连接'}
            </Tag>
          </Card>
        </Col>
      </Row>

      <Card title="近30天流量趋势">
        <FlowChart data={chartData} title="" />
      </Card>
    </div>
  );
}
