# BrushFlow - 刷下行流量工具

用于应对国内 ISP 对上传流量的审查，通过自动下载公开大文件来平衡上下行比例。

## 功能

- **下载链接管理**：内置公开测速资源（Hetzner, Cloudflare, 清华镜像等），支持自定义 URL。
- **并发控制**：可自定义每个任务的并发连接数。
- **流量统计**：记录并展示每日、每周、每月的累计下行流量。
- **Web 管理后台**：仪表盘、任务列表、流量图表和系统设置。
- **定时调度**：支持通过 Cron 表达式设置全自动启停时间。
- **流量规划 (熔断机制)**：支持设置“每日下载目标 (GB)”，达标后自动停止所有任务，精准对冲上传流量。
- **限速功能**：支持任务级及全局限速（令牌桶算法）。

## 快速开始

### Docker 部署 (推荐)

```bash
docker-compose up -d
```

访问 `http://localhost:8000` 即可进入管理后台。

### 本地开发部署

#### 后端

1. 进入 `backend` 目录
2. 创建虚拟环境并安装依赖：
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/macOS
   .venv\Scripts\activate     # Windows
   pip install -r requirements.txt
   ```
3. 启动服务：
   ```bash
   uvicorn app.main:app --reload
   ```

#### 前端

1. 进入 `frontend` 目录
2. 安装依赖并启动开发服务器：
   ```bash
   npm install
   npm run dev
   ```

## 技术栈

- **后端**: FastAPI, aiohttp, SQLAlchemy, SQLite, APScheduler
- **前端**: React, Vite, TypeScript, Ant Design, ECharts

## 截图

*(待添加)*

## 免责声明

本工具仅供学习和个人测试使用。请遵守当地法律法规及 ISP 服务条款，不要滥用网络资源。
