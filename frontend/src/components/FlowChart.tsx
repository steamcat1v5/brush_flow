import ReactECharts from 'echarts-for-react';

interface FlowChartProps {
  data: Array<{ period_key: string; total_bytes: number }>;
  title?: string;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
}

export default function FlowChart({ data, title = '流量统计' }: FlowChartProps) {
  const option = {
    title: { text: title, left: 'center' },
    tooltip: {
      trigger: 'axis' as const,
      formatter: (params: Array<{ name: string; value: number }>) => {
        const p = params[0];
        return `${p.name}<br/>${formatBytes(p.value)}`;
      },
    },
    xAxis: {
      type: 'category' as const,
      data: data.map((d) => d.period_key).reverse(),
    },
    yAxis: {
      type: 'value' as const,
      axisLabel: {
        formatter: (v: number) => formatBytes(v),
      },
    },
    series: [
      {
        data: data.map((d) => d.total_bytes).reverse(),
        type: 'bar',
        itemStyle: { color: '#1890ff' },
      },
    ],
    grid: { left: 80, right: 30, top: 50, bottom: 30 },
  };

  return <ReactECharts option={option} style={{ height: 350 }} />;
}
