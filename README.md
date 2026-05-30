# BrushFlow - 刷下行流量工具

用于应对国内 ISP 对上传流量的审查，通过自动下载公开大文件或 IPTV 流来平衡上下行比例。

## 功能

- **下载链接管理**：内置公开测速资源（Hetzner, Cloudflare, 清华镜像等），支持自定义 URL。
- **IPTV 流量消耗**：支持导入 m3u 播放列表，通过持续观看 IPTV 频道消耗下行流量，流量模式更自然，不易被 ISP 风控。
- **自动换台**：IPTV 任务支持定时自动切换频道（随机或顺序模式），模拟正常电视观看行为。
- **并发控制**：可自定义每个下载任务的并发连接数。
- **流量统计**：记录并展示每日、每周、每月的累计下行流量。
- **Web 管理后台**：仪表盘、任务列表、IPTV 管理、流量图表和系统设置。
- **定时调度**：支持通过 Cron 表达式设置全自动启停时间（同时覆盖下载和 IPTV 任务）。
- **流量规划 (熔断机制)**：支持设置"每日下载目标 (GB)"，达标后自动停止所有任务，精准对冲上传流量。
- **限速功能**：支持任务级及全局限速（令牌桶算法），同时覆盖下载和 IPTV 任务。

## 快速开始

### Docker 部署 (推荐)

1. 从 `.env.example` 创建配置文件：
   ```bash
   cp .env.example .env
   ```
2. 按需修改端口等配置，然后启动：
   ```bash
   docker compose up -d --build
   ```

访问 `http://localhost:8765` 即可进入管理后台（端口可在 `.env` 中修改）。

### 本地开发部署

#### 后端

1. 进入 `backend` 目录
2. 使用 uv 创建虚拟环境并安装依赖：
   ```bash
   uv sync
   ```
3. 启动服务：
   ```bash
   uv run python -m app.main
   ```

#### 前端

1. 进入 `frontend` 目录
2. 安装依赖并启动开发服务器：
   ```bash
   npm install
   npm run dev
   ```

### 一键启动 (Windows)

双击运行项目根目录下的 `run_local.bat` 即可同时启动前后端。

## 技术栈

- **后端**: FastAPI, aiohttp, SQLAlchemy, SQLite, APScheduler
- **前端**: React, Vite, TypeScript, Ant Design, ECharts
- **包管理**: uv (后端), npm/yarn (前端)

## 文档

- [技术设计文档](docs/TECHNICAL_DESIGN.md) — 核心技术策略、数据库表结构、部署方案
- [使用指南](docs/USAGE_GUIDE.md) — 安装部署、功能使用说明
- [hls.js 参考手册](docs/hlsjs-reference.md) — HLS 播放器配置参数与用法

## 开发工具

- **IPTV 预览测试页**：`http://localhost:8765/iptv-test` — 独立的 HLS 播放测试页面，支持直连和通过后端代理两种模式，用于调试 IPTV 流媒体播放问题。源码位于 `backend/app/static/iptv_test.html`。

## 截图

*(待添加)*

## 免责声明

本工具仅供学习和个人测试使用。请遵守当地法律法规及 ISP 服务条款，不要滥用网络资源。
