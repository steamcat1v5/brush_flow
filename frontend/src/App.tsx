import { useState } from 'react';
import { Layout, Menu } from 'antd';
import {
  DashboardOutlined,
  CloudDownloadOutlined,
  LinkOutlined,
  BarChartOutlined,
  SettingOutlined,
  PlayCircleOutlined,
} from '@ant-design/icons';
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Tasks from './pages/Tasks';
import Links from './pages/Links';
import FlowHistory from './pages/FlowHistory';
import Settings from './pages/Settings';
import IPTV from './pages/IPTV';

const { Header, Sider, Content } = Layout;

const menuItems = [
  { key: '/', icon: <DashboardOutlined />, label: '仪表盘' },
  { key: '/tasks', icon: <CloudDownloadOutlined />, label: '任务管理' },
  { key: '/iptv', icon: <PlayCircleOutlined />, label: 'IPTV' },
  { key: '/links', icon: <LinkOutlined />, label: '链接管理' },
  { key: '/history', icon: <BarChartOutlined />, label: '流量历史' },
  { key: '/settings', icon: <SettingOutlined />, label: '设置' },
];

export default function App() {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider collapsible collapsed={collapsed} onCollapse={setCollapsed}>
        <div style={{ height: 32, margin: 16, color: '#fff', textAlign: 'center', fontWeight: 'bold', fontSize: collapsed ? 14 : 18 }}>
          {collapsed ? 'BF' : 'BrushFlow'}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header style={{ padding: '0 24px', background: '#fff', fontSize: 20, fontWeight: 'bold' }}>
          刷下行流量管理
        </Header>
        <Content style={{ margin: 24, padding: 24, background: '#fff', borderRadius: 8 }}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/tasks" element={<Tasks />} />
            <Route path="/iptv" element={<IPTV />} />
            <Route path="/links" element={<Links />} />
            <Route path="/history" element={<FlowHistory />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  );
}
