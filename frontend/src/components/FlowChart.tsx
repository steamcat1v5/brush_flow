import ReactECharts from 'echarts-for-react';

interface FlowChartProps {
  data: Array<{ period_key: string; total_bytes: number; download_bytes?: number; iptv_bytes?: number }>;
  title?: string;
  chartType?: 'bar' | 'line';
  showSplit?: boolean;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
}

export default function FlowChart({ data, title = '流量统计', chartType = 'bar', showSplit = false }: FlowChartProps) {
  const categories = data.map((d) => d.period_key).reverse();

  const buildSeries = () => {
    if (showSplit) {
      const base = {
        stack: chartType === 'bar' ? 'total' : undefined,
        areaStyle: chartType === 'line' ? {} : undefined,
        smooth: chartType === 'line',
      };
      return [
        {
          name: '下载',
          type: chartType,
          data: data.map((d) => d.download_bytes ?? d.total_bytes).reverse(),
          itemStyle: { color: '#1890ff' },
          ...base,
        },
        {
          name: 'IPTV',
          type: chartType,
          data: data.map((d) => d.iptv_bytes ?? 0).reverse(),
          itemStyle: { color: '#722ed1' },
          ...base,
        },
      ];
    }
    return [
      {
        name: '总流量',
        type: chartType,
        data: data.map((d) => d.total_bytes).reverse(),
        itemStyle: { color: '#1890ff' },
        areaStyle: chartType === 'line' ? {} : undefined,
        smooth: chartType === 'line',
      },
    ];
  };

  const option = {
    title: { text: title, left: 'center' },
    tooltip: {
      trigger: 'axis' as const,
      formatter: (params: Array<{ seriesName: string; name: string; value: number }>) => {
        let html = `${params[0].name}<br/>`;
        for (const p of params) {
          html += `${p.seriesName}: ${formatBytes(p.value)}<br/>`;
        }
        return html;
      },
    },
    legend: showSplit ? { bottom: 0, data: ['下载', 'IPTV'] } : undefined,
    xAxis: {
      type: 'category' as const,
      data: categories,
    },
    yAxis: {
      type: 'value' as const,
      axisLabel: {
        formatter: (v: number) => formatBytes(v),
      },
    },
    series: buildSeries(),
    grid: { left: 80, right: 30, top: 50, bottom: showSplit ? 40 : 30 },
  };

  return <ReactECharts key={`${chartType}-${showSplit}-${categories.length}-${categories[0] || ''}`} option={option} notMerge={true} style={{ height: 350 }} />;
}
