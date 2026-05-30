# IPTV 流量消耗流程图与数据流

## 流程图

```mermaid
flowchart TD
    A[用户添加 m3u 源 URL] --> B[后端请求 m3u 内容]
    B --> C[解析 #EXTINF 提取频道名/分组/HLS地址]
    C --> D[存入 iptv_channels 表]
    D --> E[用户选择频道创建 IPTV 任务]
    E --> F[启动任务]
    F --> G[请求 Master m3u8]
    G --> H{响应类型?}
    H -->|302 重定向| I[跟随 Location 重新请求]
    I --> H
    H -->|200 文本| J[解析 #EXT-X-STREAM-INF 选择最高码率变体]
    J --> K[请求 Variant m3u8]
    K --> L[解析 #EXTINF 时长和 .ts 分片 URL]
    L --> M[逐个下载 .ts 分片]
    M --> N[流式读取 → 计数字节数 → 丢弃]
    N --> O[写入 flow_tracker 流量统计]
    O --> P{达到目标下载量?}
    P -->|是| Q[任务自动完成]
    P -->|否| R{等待分片时长]
    R --> S[重新获取 Variant m3u8]
    S --> T{有新分片?}
    T -->|是| M
    T -->|否| U[等待 3 秒]
    U --> V{距上次解析超过 5 分钟?}
    V -->|是| W[重新请求 Master m3u8 刷新 token]
    W --> K
    V -->|否| S
    X{自动换台?} -->|到期或连续失败5次| Y[随机/顺序选择新频道]
    Y --> G

    style A fill:#e1f5fe
    style Q fill:#c8e6c9
    style N fill:#fff3e0
```

## 数据流详解

### 第 1 步：获取 m3u 播放列表

向 m3u 源地址发起 HTTP GET 请求，获取频道列表。

**请求：**
```
GET https://example.com/tv/cu.m3u HTTP/2
```

**响应：**
```
HTTP/2 200
content-type: audio/x-mpegurl
server: cloudflare

#EXTM3U
#EXTINF:-1 tvg-name="上海新闻综合" group-title="上海",新闻综合HD
http://10.223.3.189:80/PLTV/88888888/224/3221225701/10000100000000060000000000013592_0.smil/index.m3u8?fmt=ts2hls&...&accountinfo=...
#EXTINF:-1 tvg-name="CCTV1" group-title="央视",CCTV-1HD
http://10.223.3.189:80/PLTV/88888888/224/3221225703/...
```

**程序处理：**
- `m3u_parser.py` 逐行解析，提取 `tvg-name`、`group-title` 和下一行的 HLS URL
- 存入 `iptv_channels` 表：name="新闻综合HD"，group_title="上海"，hls_url=完整URL

---

### 第 2 步：请求 Master m3u8（HLS 入口）

IPTV 任务启动时，向频道的 HLS URL 发起请求。

**请求：**
```
GET http://10.223.3.189:80/PLTV/88888888/224/3221225701/
    10000100000000060000000000013592_0.smil/index.m3u8
    ?fmt=ts2hls&zoneoffset=480&servicetype=2&icpid=shlt
    &limitflux=-1&limitdur=-1&tenantId=8601&GuardEncType=2
    &accountinfo=~EV2.0~jXi_dEHZJrb4BhWXybu2mg~...
```

**响应（302 重定向）：**
```
HTTP/1.1 302 Moved Temporarily
Location: http://10.223.3.185:80/PLTV/.../index.m3u8?...&from=2&hms_devid=712&online=1780132296
```

**程序处理：**
- `aiohttp` 自动跟随 302 重定向（`10.223.3.189` → `10.223.3.185`）
- 重定向后的响应：

```
HTTP/1.1 200 OK
Content-Type: application/vnd.apple.mpegurl
Content-Length: 116

#EXTM3U
#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=8941568
01.m3u8?fmt=ts2hls,712,01.m3u8,0,8732,0,0&tenantId=8601
```

**程序处理：**
- 检测到 `#EXT-X-STREAM-INF`，说明是 Master Playlist
- 解析 `BANDWIDTH=8941568`（约 8.9 Mbps）
- 下一行是变体 URL，基于当前 URL 的目录路径拼接为完整地址

---

### 第 3 步：请求 Variant m3u8（分片列表）

向变体 URL 发起请求，获取具体的 .ts 分片列表。

**请求：**
```
GET http://10.223.3.185:80/PLTV/88888888/224/3221225701/
    10000100000000060000000000013592_0.smil/01.m3u8
    ?fmt=ts2hls,712,01.m3u8,0,8732,0,0&tenantId=8601
```

**响应：**
```
HTTP/1.1 200 OK
Content-Type: application/vnd.apple.mpegurl

#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:11
#EXT-X-MEDIA-SEQUENCE:42303187
#EXT-X-PROGRAM-DATE-TIME:2026-05-29T04:51:10Z
#EXTINF:10.206,
http://10.223.3.189:80/PLTV/.../42303187.ts?fmt=ts2hls,...&tenantId=8601
#EXTINF:8.968,
http://10.223.3.189:80/PLTV/.../42303188.ts?fmt=ts2hls,...&tenantId=8601
#EXTINF:10.296,
http://10.223.3.189:80/PLTV/.../42303189.ts?fmt=ts2hls,...&tenantId=8601
```

**程序处理：**
- `#EXTINF:10.206,` → 该分片时长 10.2 秒
- 解析出 6 个 .ts 分片 URL 及各自时长
- 分片去重（跳过已下载的）
- 逐个下载，下载完一个分片后等待其时长（~10 秒）再下载下一个

---

### 第 4 步：下载 .ts 分片

逐个请求 .ts 视频分片，流式读取后丢弃。

**请求：**
```
GET http://10.223.3.189:80/PLTV/.../42303187.ts
    ?fmt=ts2hls,...&tenantId=8601
```

**响应：**
```
HTTP/1.1 200 OK
Content-Type: video/MP2T
Content-Length: 11382648

[二进制数据，约 10.8 MB 的 MPEG-TS 视频分片]
```

**程序处理：**
```python
# 流式读取，128KB 一块
async for chunk in resp.content.iter_chunked(131072):
    chunk_size = len(chunk)       # 累加字节数
    total_downloaded += chunk_size
    flow_tracker.record(task_id, chunk_size)  # 写入流量统计
    # chunk 对象随循环迭代被 Python GC 回收，不写盘
```

---

### 第 5 步：循环消费

```
下载分片 → 等待分片时长(~10s) → 拉取新分片列表 → 有新分片则下载 → ...
                                       ↓
                              无新分片则等待 3 秒
                                       ↓
                           距上次解析超过 5 分钟？
                              ↓ 是          ↓ 否
                     重新请求 Master m3u8    继续拉取
                     刷新 accountinfo token
```

**自动换台（可选）：**
- 换台间隔到期 → 从同一源随机/顺序选择新频道 → 从第 2 步重新开始
- 连续失败 5 次 → 自动换台，避免卡死在坏频道

**目标量检查：**
- 每下载一个分片后检查 `total_downloaded >= target_bytes`
- 达标则设置 `status = "completed"` 并记录日志

---

### 流量统计集成

```
flow_tracker.record(task_id, chunk_size)
       ↓
内存累加 (_task_session_total)
       ↓ (每 5 秒)
flush 到 SQLite flow_logs 表 (分钟粒度)
       ↓
Dashboard 实时显示 + WebSocket 推送
       ↓
每日目标熔断检查 (每分钟)
       ↓ (达标)
停止所有任务（包括下载和 IPTV）
```

IPTV 任务的 `task_id` 在 flow_tracker 中使用 `+ 100000` 偏移量，与下载任务的 ID 空间隔离，避免速度显示串台。
