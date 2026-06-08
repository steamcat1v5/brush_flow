# BrushFlow 使用指南

本指南旨在帮助您快速上手并合理规划下行流量，以平衡您的 ISP 上下行比例。

## 1. 快速开始
1. 运行项目（推荐使用 `run_local.bat` 或 Docker）。
2. 访问管理后台：
   *   **Docker 部署**：浏览器访问 `http://localhost:8765`。
   *   **本地开发**：浏览器访问 `http://localhost:3000`，后端服务默认在 `http://localhost:8765`。
3. **添加链接**：前往“链接管理”，验证内置链接的可用性，或添加您信任的下载地址。
4. **启动任务**：在“任务管理”中新建任务，选择刚才添加的链接，设置并发数，点击“启动”。

## 2. Docker 访问地址与后端接口

Docker 部署时，前端 SPA 构建产物由后端 FastAPI 统一托管，前端页面、后端 API 和 WebSocket 共用 `.env` 中的 `BF_PORT`，默认端口为 `8765`。

| 用途 | 默认地址 |
|------|----------|
| 前端管理后台 | `http://localhost:8765` |
| 后端 API 基础路径 | `http://localhost:8765/api` |
| Swagger API 文档 | `http://localhost:8765/docs` |
| OpenAPI JSON | `http://localhost:8765/openapi.json` |
| ReDoc 文档 | `http://localhost:8765/redoc` |
| 健康检查 | `http://localhost:8765/api/health` |
| 实时 WebSocket | `ws://localhost:8765/ws/realtime` |
| IPTV 预览测试页 | `http://localhost:8765/iptv-test` |

如果部署到服务器，请将 `localhost` 替换为服务器 IP 或域名；如果修改了 `.env` 中的 `BF_PORT`，访问端口也需要同步替换。

### 获取当日流量

通过 REST API 获取当日累计流量和当前速度：

```http
GET http://localhost:8765/api/flow/today
```

返回示例：

```json
{
  "total_bytes": 123456789,
  "current_speed": 102400,
  "active_tasks": 2,
  "uptime_seconds": 0
}
```

字段说明：

*   `total_bytes`：今日累计下行流量，单位为 bytes。
*   `current_speed`：当前总速度，单位为 bytes/s。
*   `active_tasks`：运行中的下载任务数量。
*   `uptime_seconds`：当前实现中固定为 `0`。

PowerShell 调用示例：

```powershell
Invoke-RestMethod -Uri "http://localhost:8765/api/flow/today" -Method Get
```

WebSocket 也会每秒推送实时数据：

```json
{
  "type": "speed",
  "total_bytes_per_sec": 102400,
  "total_bytes": 123456789,
  "tasks": [
    { "task_id": 1, "speed": 51200 }
  ]
}
```

如果只需要实时速度和今日累计流量，可以使用 WebSocket；如果需要 `active_tasks` 等完整当日统计，建议使用 `GET /api/flow/today`。FastAPI 默认 Swagger/OpenAPI 不会列出 WebSocket 路由，`/ws/realtime` 请以本文档说明为准。

### 鉴权说明

当前后端 API 和 `ws://localhost:8765/ws/realtime` 均未实现登录验证、Token 校验或 Session 校验。若需要在公网访问，建议先通过 VPN、反向代理鉴权或防火墙限制访问范围。

## 3. 流量规划与安全
本工具提供了多层控制机制，建议您根据实际需求组合使用：

### A. 每日下载目标 (GB) —— [推荐设置]
*   **位置**：设置页面 -> 每日下载目标 (GB)
*   **作用**：这是一个“全局开关”。当今日所有任务产生的下行流量总和达到此值时，系统会**自动停止所有任务**。
*   **场景**：如果您计算出每天需要 50GB 下行流量来对冲 PCDN 上传，将其设为 `50`。这样即使您人不在电脑旁，系统也不会超刷。

### B. 定时自动启停 (Cron)
*   **位置**：设置页面 -> 自动启动/停止 Cron 表达式
*   **作用**：
    *   **自动启动**：默认 `0 0 * * *` (凌晨 0 点)，让系统在网络空闲期自动开始工作。
    *   **自动停止**：默认 `0 8 * * *` (早晨 8 点)，确保在您开始日常用网前停止。

### C. 任务级目标 (MB)
*   **位置**：新建任务弹窗 -> 目标下载量 (MB)
*   **作用**：只针对该特定任务。例如某些下载链接比较敏感，您只想用它刷 5GB，设为 `5120`。任务完成后，该任务状态会变为 `completed`。

## 4. 常见参数建议
*   **并发数 (Concurrency)**：
    *   国内主流 CDN (腾讯/阿里)：建议 **5-20**。
    *   教育网/开源镜像站：建议 **3-10**。
    *   *注意*：并发数过高（如 >50）可能导致您的 IP 被目标服务器封禁或被 ISP 识别为异常流量。
*   **任务最大速度 (KB/s)**：
    *   如果您不希望某个任务瞬间占满您的全部物理带宽（导致打游戏、看视频卡顿），可以设置限速。例如填入 `2048` 表示该任务下所有连接的总速度限制在 2MB/s。

### D. 全局最大下载速度 (KB/s)
*   **位置**：设置页面 -> 全局最大下载速度 (KB/s)
*   **作用**：限制整个程序的总下行带宽。无论同时运行多少个任务，总速度都不会超过此上限。
*   **场景**：如果您有一条 100M 带宽的线路，希望给刷流量工具分配 50M (约 6250 KB/s)，在这里设置即可。

## 5. 如何查看效果
*   **仪表盘**：查看实时的下载速度、今日进度条。
*   **流量历史**：系统会自动记录每日总量，您可以切换“日/周/月”维度，对比分析长期的流量走势，确保您的上下行比例保持在安全区间。

---
**提示**：如果发现流量展示不正常，请尝试刷新页面。后端服务重启会自动重置僵尸任务状态。
