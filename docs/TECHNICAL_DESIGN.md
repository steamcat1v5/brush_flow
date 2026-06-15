# BrushFlow 技术设计文档

本文档详细说明了 BrushFlow 在实现"高效刷取下行流量"目标时所采取的核心技术策略与代码实现逻辑。

## 1. 核心目标：高性能且"不写盘"的下载引擎

刷流量工具的核心痛点在于：如何在不损耗硬件（尤其是 SSD）寿命的前提下，尽可能快地消耗下行带宽。

### 代码策略：流式读取与即时丢弃
在 `backend/app/services/download_engine.py` 中，下载逻辑并未采用常见的文件保存模式，而是采用了**内存流式迭代**：

```python
# 核心下载循环
async for chunk in resp.content.iter_chunked(settings.chunk_size):
    # 1. 仅在内存中计算长度
    chunk_size = len(chunk)
    # 2. 累加到统计器
    self.total_downloaded += chunk_size
    # 3. 循环进入下一轮，旧的 chunk 对象被 Python GC 自动回收
```

*   **零磁盘 I/O**：没有任何 `file.write()` 操作，数据在内存中即用即抛。
*   **低内存占用**：通过设置 `chunk_size` (默认 128KB)，每个连接在任意时刻占用的内存都是恒定的，不会随下载总量增长。

## 2. 并发模型：协程 vs 线程

为了支撑数百个并发连接（应对多任务、高并发场景），项目选择了基于 **Python asyncio** 的异步非阻塞模型。

*   **轻量化**：相比于多线程，协程切换的开销极低。单进程即可轻松管理成百上千个下载 Worker。
*   **Semaphore 并发控制**：通过 `asyncio.Semaphore` 实现了任务级和全局级的两层并发控制，确保系统资源（如 Socket 句柄）不会耗尽。

## 3. 流量计量与持久化策略

实时且准确的流量统计是规划的核心。

### 内存累加 + 定时 Flush
为了避免高频写入数据库导致的性能瓶颈，项目在 `flow_tracker.py` 中采取了以下策略：

1.  **内存原子累加**：下载 Worker 实时将字节数推送到 `FlowTracker` 内存字典中。
2.  **分钟级窗口同步**：后台 `flush_loop` 每隔 5 秒（可调）将内存中的增量同步到 SQLite 的 `flow_logs` 表中。
3.  **防止统计抖动**：采用"Commit 成功后再清除增量"的逻辑，确保了即使在数据库繁忙时，仪表盘显示的今日总量也不会出现回退现象。

## 4. 多级限速机制 (Token Bucket)

项目实现了两个维度的限速，底层均采用**令牌桶 (Token Bucket) 算法**：

*   **任务级限速**：针对单个任务的所有连接共享一个令牌桶，限制该任务的总带宽。
*   **全局限速**：所有运行中的任务共享一个全局令牌桶，确保程序总带宽不影响家庭其他成员上网。

## 5. 自动熔断与调度机制

为了实现"自动化流量规划"，系统集成了 `APScheduler`：

*   **Cron 调度**：借用 Cron 语法实现了定时启动/停止下载任务的功能。
*   **分钟级熔断检查**：每分钟计算一次今日已刷总流量，一旦超过 `daily_traffic_target_gb`，立即强制关闭引擎，实现"精准达标"。
*   **统一调度**：定时启停和熔断机制同时覆盖下载任务和 IPTV 任务，无需分别配置。

## 6. 前后端实时交互

*   **WebSocket 推送**：后端每秒计算一次各任务的瞬时速度，通过 WebSocket 主动推送到前端，避免了前端频繁轮询 API。
*   **动态估算**：前端基于实时下载速度和剩余目标流量，动态计算预计达成时间。

### 6.1 当日流量 REST 接口

当日流量统计由 `GET /api/flow/today` 提供，默认 Docker 地址为：

```http
GET http://localhost:8765/api/flow/today
```

返回数据包含：

```json
{
  "total_bytes": 123456789,
  "current_speed": 102400,
  "active_tasks": 2,
  "uptime_seconds": 0
}
```

*   `total_bytes`：今日累计下行流量，单位为 bytes。
*   `current_speed`：当前总速度，单位为 bytes/s。
*   `active_tasks`：当前运行中的下载任务数量。
*   `uptime_seconds`：当前实现中固定为 `0`。

### 6.2 WebSocket 实时数据

实时推送地址为：

```text
ws://localhost:8765/ws/realtime
```

连接建立后，后端每秒推送一次实时速度和今日累计流量：

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

WebSocket 可用于实时展示 `total_bytes` 和 `total_bytes_per_sec`；如果需要 `active_tasks` 等完整当日统计，应调用 `GET /api/flow/today`。FastAPI 默认 Swagger/OpenAPI 不会列出 WebSocket 路由，`/ws/realtime` 需要在项目文档中单独说明。

### 6.3 鉴权边界

当前项目未实现登录系统，REST API 和 WebSocket 均不校验 Token、Cookie 或 Session。部署到公网前，应通过 VPN、反向代理鉴权或防火墙限制访问范围。

## 7. 存储架构

*   **SQLite WAL 模式**：考虑到工具的单机使用场景，选用了 SQLite 并开启了 WAL (Write-Ahead Logging) 模式。
*   **优势**：零运维、单文件、支持并发读写，完美契合流量日志高频写入的场景。

## 8. 数据库表结构

共 8 张表，分为下载任务、IPTV 任务、流量统计、系统配置四组。

### 8.1 links — 下载链接

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer PK | 自增主键 |
| `name` | String(200) | 链接名称 |
| `url` | String(2000) | 下载地址，唯一 |
| `file_size` | Integer | 文件大小（字节），默认 0 |
| `is_builtin` | Boolean | 是否内置链接，默认 false |
| `is_active` | Boolean | 是否启用，默认 true |
| `category` | String(50) | 分类，默认 "general" |
| `created_at` | DateTime | 创建时间 |

### 8.2 tasks — 下载任务

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer PK | 自增主键 |
| `link_id` | Integer FK → links.id | 关联下载链接 |
| `name` | String(200) | 任务名称 |
| `status` | String(20) | 状态：pending/running/paused/completed/failed/stopped |
| `concurrency` | Integer | 并发连接数，默认 5 |
| `total_downloaded` | Integer | 累计下载量（字节），跨启停持久化 |
| `target_bytes` | Integer | 目标下载量（字节），0=无限 |
| `speed_limit` | Integer | 任务最大速度（bytes/s），0=不限 |
| `retry_count` | Integer | 当前连续重试次数，成功后重置 |
| `auto_start_cron` | String(50) | 定时启动的 cron 表达式，可空 |
| `auto_stop_cron` | String(50) | 定时停止的 cron 表达式，可空 |
| `started_at` | DateTime | 启动时间，可空 |
| `stopped_at` | DateTime | 停止时间，可空 |
| `created_at` | DateTime | 创建时间 |

### 8.3 iptv_sources — IPTV m3u 源

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer PK | 自增主键 |
| `name` | String(200) | 源名称 |
| `m3u_url` | String(2000) | m3u 播放列表地址，唯一 |
| `channel_count` | Integer | 频道数量（解析后更新） |
| `last_parsed_at` | DateTime | 上次解析时间，可空 |
| `created_at` | DateTime | 创建时间 |

### 8.4 iptv_channels — IPTV 频道

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer PK | 自增主键 |
| `source_id` | Integer FK → iptv_sources.id | 所属 m3u 源 |
| `name` | String(200) | 频道名称 |
| `group_title` | String(100) | 分组（如"央视"、"卫视"），默认空 |
| `hls_url` | String(2000) | HLS 流地址 |
| `sort_order` | Integer | 排序序号 |

唯一约束：`(source_id, name)`

### 8.5 iptv_tasks — IPTV 任务

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer PK | 自增主键 |
| `source_id` | Integer FK → iptv_sources.id | 关联 m3u 源 |
| `channel_id` | Integer FK → iptv_channels.id | 当前频道 |
| `name` | String(200) | 任务名称 |
| `status` | String(20) | 状态：pending/running/paused/completed/failed/stopped |
| `speed_limit` | Integer | 任务最大速度（bytes/s），0=不限 |
| `target_bytes` | Integer | 目标下载量（字节），0=无限 |
| `total_downloaded` | Integer | 累计下载量（字节） |
| `auto_switch_enabled` | Boolean | 是否启用自动换台，默认 false |
| `auto_switch_interval` | Integer | 换台间隔（秒），默认 1800 |
| `switch_mode` | String(20) | 换台模式：random/sequential |
| `auto_start_cron` | String(50) | 定时启动的 cron 表达式，可空 |
| `auto_stop_cron` | String(50) | 定时停止的 cron 表达式，可空 |
| `started_at` | DateTime | 启动时间，可空 |
| `stopped_at` | DateTime | 停止时间，可空 |
| `created_at` | DateTime | 创建时间 |

### 8.6 flow_logs — 流量日志（分钟粒度）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer PK | 自增主键 |
| `task_id` | Integer (indexed) | 任务 ID（无 FK，兼容下载和 IPTV 任务） |
| `bytes_down` | Integer | 该分钟内的下载量（字节） |
| `logged_at` | DateTime (indexed) | 记录时间 |

唯一约束：`(task_id, logged_at)`

### 8.7 flow_summaries — 流量汇总报表

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer PK | 自增主键 |
| `period_type` | String(10) | 周期类型：day/week/month |
| `period_key` | String(20) | 周期标识，如 "2026-05-28" |
| `total_bytes` | Integer | 总下载量（字节） |
| `task_count` | Integer | 参与的任务数 |
| `avg_speed` | Integer | 平均速度（bytes/s） |
| `peak_speed` | Integer | 峰值速度（bytes/s） |
| `created_at` | DateTime | 创建时间 |

唯一约束：`(period_type, period_key)`

### 8.8 task_logs — 任务运行日志

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer PK | 自增主键 |
| `task_id` | Integer (indexed) | 任务 ID（无 FK，兼容下载和 IPTV 任务） |
| `task_type` | String(20) | 任务类型：download/iptv |
| `level` | String(10) | 日志级别：info/warn/error |
| `message` | String(500) | 日志内容 |
| `created_at` | DateTime | 创建时间 |

### 8.9 settings — 系统配置

| 字段 | 类型 | 说明 |
|------|------|------|
| `key` | String(100) PK | 配置键名 |
| `value` | String(500) | 配置值 |
| `updated_at` | DateTime | 更新时间 |

### 表间关系

```
links ←── tasks.link_id
iptv_sources ←── iptv_channels.source_id
iptv_sources ←── iptv_tasks.source_id
iptv_channels ←── iptv_tasks.channel_id
```

`flow_logs.task_id` 和 `task_logs.task_id` 不设外键约束，因为下载任务和 IPTV 任务使用独立的 ID 空间（IPTV 任务在 flow_tracker 中加了 100000 的偏移量以避免冲突）。

## 9. IPTV 流媒体流量消耗

除了传统的文件下载，BrushFlow 还支持通过 IPTV 流媒体消耗下行流量。这种方式的流量模式更自然，类似于正常观看电视，不易被 ISP 风控系统识别。

### HLS 流式下载（不解码）

IPTV 流采用 HLS (HTTP Live Streaming) 协议，程序**仅下载数据不进行任何视频解码**，CPU 开销极低。在 `hls_downloader.py` 中实现：

1.  **Master Playlist 解析**：获取 m3u8 主播放列表（纯文本），自动选择最高带宽的变体流。
2.  **分片下载**：持续获取变体播放列表中的 .ts 分片 URL，逐个流式下载并丢弃，与普通文件下载逻辑一致——只计算字节数，不处理视频内容。
3.  **分片去重**：维护已下载分片的集合（上限 500 条），避免直播流中重复下载同一分片。
4.  **相对路径处理**：自动将相对路径的分片 URL 解析为绝对路径。

### m3u 源管理

在 `m3u_parser.py` 中实现了标准 m3u 格式的解析器：

*   解析 `#EXTINF` 行提取频道名称、分组信息。
*   支持通过 Web 界面添加、刷新、删除 m3u 源。
*   频道按分组（如"央视"、"卫视"、"上海"）分类展示，方便选择。

### 自动换台机制

`iptv_engine.py` 中的 `IptvTaskRunner` 支持自动换台：

*   **随机模式**：从同一源的其他频道中随机选择。
*   **顺序模式**：按频道列表顺序依次切换。
*   **换台间隔**：可配置（默认 30 分钟），在当前分片下载完成后执行切换，不会中断正在进行的传输。
*   **流量连续性**：换台后重置分片集合，从新频道继续下载，流量统计不中断。

### 与现有系统的集成

IPTV 功能与现有架构无缝集成：

*   **流量统计共享**：IPTV 任务的 `task_id` 直接复用 `flow_tracker.record()`，Dashboard 和 WebSocket 推送自动包含 IPTV 流量。
*   **独立数据库表**：IPTV 源、频道、任务分别存储在 `iptv_sources`、`iptv_channels`、`iptv_tasks` 表中，不污染现有的下载任务模型。
*   **统一控制**：全局限速、每日目标熔断、定时启停等功能同时覆盖下载和 IPTV 任务。

## 10. 部署与环境配置

项目支持通过 `.env` 文件进行环境配置，实现了"一次构建，多处运行"：

*   **配置加载优先级**：系统优先读取环境变量，其次读取项目根目录下的 `.env` 文件，最后使用代码中的默认值。
*   **Docker 集成**：`docker-compose.yml` 自动加载 `.env` 文件，支持动态端口映射。
*   **前后端分离开发**：在开发环境下，Vite 通过环境变量配置代理，实现前后端联调；在生产环境下（如 Docker），前端被打包成静态资源并由 FastAPI 统一托管，简化了网络拓扑。

### 10.1 Docker 部署后的访问入口

Docker 镜像采用前后端合并部署：FastAPI 进程同时提供 `/api` 后端接口、`/ws/realtime` WebSocket，以及前端 SPA 静态文件。容器端口和宿主机端口均由 `BF_PORT` 控制，默认值为 `8765`。

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

前端通过相对路径 `/api` 调用后端，因此 Docker 部署时无需单独配置前端 API 域名。除 `/api/*`、`/ws/*`、`/docs`、`/openapi.json` 等后端路由外，其余路径由后端返回前端 `index.html`，用于支持 React Router 的 SPA 路由刷新。

---
**BrushFlow 设计原则**：高效、透明、不写盘。
