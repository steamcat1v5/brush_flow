# hls.js 使用文档

hls.js 是一个纯 JavaScript 实现的 HLS (HTTP Live Streaming) 播放器库，基于 MediaSource Extensions (MSE) API，无需 Flash 或其他插件即可在浏览器中播放 HLS 流。

## 安装

```bash
npm install hls.js
```

```html
<!-- 或通过 CDN -->
<script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
```

## 基本用法

```typescript
import Hls from 'hls.js';

const video = document.getElementById('video') as HTMLVideoElement;
const url = 'https://example.com/stream/index.m3u8';

if (Hls.isSupported()) {
  const hls = new Hls();
  hls.loadSource(url);
  hls.attachMedia(video);
  hls.on(Hls.Events.MANIFEST_PARSED, () => {
    video.play();
  });
} else if (video.canPlayType('application/vnd.apple.mpegurl')) {
  // Safari 原生支持 HLS
  video.src = url;
  video.addEventListener('loadedmetadata', () => video.play());
}
```

## 事件系统

hls.js 通过事件机制通知应用各种状态变化。

### 核心事件

```typescript
// 播放列表加载完成
hls.on(Hls.Events.MANIFEST_LOADED, (event, data) => {
  console.log('可用质量级别:', data.levels.length);
});

// 播放列表解析完成，可以开始播放
hls.on(Hls.Events.MANIFEST_PARSED, (event, data) => {
  console.log('解析完成，级别:', data.levels.length);
  video.play();
});

// 变体级别加载完成
hls.on(Hls.Events.LEVEL_LOADED, (event, data) => {
  console.log('级别加载完成，分片数:', data.details.fragments.length);
});

// 分片开始加载
hls.on(Hls.Events.FRAG_LOADING, (event, data) => {
  console.log('开始加载分片:', data.frag.url);
});

// 分片加载完成
hls.on(Hls.Events.FRAG_LOADED, (event, data) => {
  console.log('分片加载完成:', data.frag.url, '大小:', data.payload.byteLength);
});

// 质量级别切换
hls.on(Hls.Events.LEVEL_SWITCHED, (event, data) => {
  console.log('切换到级别:', data.level);
});
```

### 错误处理

```typescript
hls.on(Hls.Events.ERROR, (event, data) => {
  console.error('HLS 错误:', data.type, data.details, data.fatal);

  if (data.fatal) {
    switch (data.type) {
      case Hls.ErrorTypes.NETWORK_ERROR:
        // 网络错误，尝试恢复
        hls.startLoad();
        break;
      case Hls.ErrorTypes.MEDIA_ERROR:
        // 媒体错误，尝试恢复
        hls.recoverMediaError();
        break;
      default:
        // 不可恢复的错误
        hls.destroy();
        break;
    }
  }
});
```

### 所有事件列表

| 事件 | 说明 |
|------|------|
| `MEDIA_ATTACHING` | 媒体元素即将绑定 |
| `MEDIA_ATTACHED` | 媒体元素已绑定 |
| `MEDIA_DETACHING` | 媒体元素即将解绑 |
| `MEDIA_DETACHED` | 媒体元素已解绑 |
| `BUFFER_RESET` | 缓冲区重置 |
| `BUFFER_CODECS` | 缓冲区收到编解码器信息 |
| `BUFFER_CREATED` | 缓冲区已创建 |
| `BUFFER_APPENDED` | 数据已追加到缓冲区 |
| `BUFFER_APPENDING` | 数据正在追加 |
| `FRAG_BUFFERED` | 分片已写入缓冲区 |
| `LEVEL_SWITCHING` | 质量级别即将切换 |
| `LEVEL_SWITCHED` | 质量级别已切换 |
| `LEVEL_LOADING` | 级别播放列表开始加载 |
| `LEVEL_LOADED` | 级别播放列表加载完成 |
| `LEVEL_UPDATED` | 级别信息已更新 |
| `LEVEL_PTS_UPDATED` | 级别 PTS 信息已更新 |
| `FRAG_LOADED` | 分片加载完成 |
| `FRAG_LOADING` | 分片开始加载 |
| `FRAG_LOAD_PROGRESS` | 分片加载进度 |
| `FRAG_PARSING_INIT_SEGMENT` | 分片解析初始化段 |
| `FRAG_PARSING_METADATA` | 分片解析元数据 |
| `FRAG_PARSING_DATA` | 分片解析音视频数据 |
| `FRAG_PARSED` | 分片解析完成 |
| `KEY_LOADING` | 加密密钥开始加载 |
| `KEY_LOADED` | 加密密钥加载完成 |
| `STREAM_STATE_TRANSITION` | 流状态转换 |
| `ERROR` | 发生错误 |
| `DESTROYING` | 实例即将销毁 |
| `MANIFEST_LOADING` | 主播放列表开始加载 |
| `MANIFEST_LOADED` | 主播放列表加载完成 |
| `MANIFEST_PARSED` | 主播放列表解析完成 |
| `AUDIO_TRACKS_UPDATED` | 音频轨道列表更新 |
| `AUDIO_TRACK_SWITCHING` | 音频轨道切换 |
| `SUBTITLE_TRACKS_UPDATED` | 字幕轨道列表更新 |
| `SUBTITLE_TRACK_SWITCH` | 字幕轨道切换 |

## 配置参数

### 缓冲控制

```typescript
const hls = new Hls({
  // 前向缓冲目标长度（秒），hls.js 会尝试维持这个缓冲量
  maxBufferLength: 30,

  // 前向缓冲最大上限（秒），防止缓冲过多占用内存
  maxMaxBufferLength: 600,

  // 已播放内容的保留长度（秒），超过的部分会被清理
  backBufferLength: 30,

  // 达到此缓冲长度时暂停加载（秒）
  highBufferWatchpoint: 120,

  // 缓冲区低水位（秒），低于此值时优先加载
  lowBufferWatchpoint: 3,
});
```

### 直播流控制

```typescript
const hls = new Hls({
  // 直播同步窗口（分片数），播放位置距离直播边缘的分片数
  liveSyncDurationCount: 3,

  // 最大允许延迟（分片数），超过会跳帧追赶
  liveMaxLatencyDurationCount: Infinity,

  // 直播同步时长（秒），优先于 liveSyncDurationCount
  liveSyncDuration: undefined,

  // 最大允许延迟（秒），优先于 liveMaxLatencyDurationCount
  liveMaxLatencyDuration: undefined,

  // 直播流时长显示为 Infinity
  liveDurationInfinity: false,

  // 低延迟模式（LL-HLS）
  lowLatencyMode: true,
});
```

### 加载超时

```typescript
const hls = new Hls({
  // 主播放列表加载超时（毫秒）
  manifestLoadingTimeOut: 10000,

  // 级别播放列表加载超时（毫秒）
  levelLoadingTimeOut: 10000,

  // 分片加载超时（毫秒）
  fragLoadingTimeOut: 20000,

  // 密钥加载超时（毫秒）
  keyLoadingTimeOut: 10000,
});
```

### 重试策略

```typescript
const hls = new Hls({
  // 主播放列表最大重试次数
  manifestLoadingMaxRetry: 6,

  // 主播放列表重试延迟（毫秒）
  manifestLoadingRetryDelay: 1000,

  // 级别播放列表最大重试次数
  levelLoadingMaxRetry: 6,

  // 级别播放列表重试延迟（毫秒）
  levelLoadingRetryDelay: 1000,

  // 分片最大重试次数
  fragLoadingMaxRetry: 6,

  // 分片重试延迟（毫秒）
  fragLoadingRetryDelay: 1000,

  // 密钥最大重试次数
  keyLoadingMaxRetry: 6,
});
```

### 性能与 Worker

```typescript
const hls = new Hls({
  // 是否使用 Web Worker 进行分片解复用
  enableWorker: true,

  // Worker 脚本路径（默认使用内联 blob URL）
  workerPath: undefined,
});
```

### 自定义加载器

```typescript
const hls = new Hls({
  // 自定义 XHR 配置（在 XHR 发送前调用）
  xhrSetup: (xhr, url) => {
    xhr.setRequestHeader('Authorization', 'Bearer token');
  },

  // 自定义 Fetch 配置（在 Fetch 发送前调用）
  fetchSetup: (context, initParams) => {
    initParams.headers = { ...initParams.headers, 'Authorization': 'Bearer token' };
    return new Request(context.url, initParams);
  },

  // 自定义加载器类（完全替换内置加载器）
  // loader: MyCustomLoader,
});
```

## 常用方法

```typescript
// 加载流
hls.loadSource(url);

// 绑定媒体元素
hls.attachMedia(video);

// 解绑媒体元素
hls.detachMedia();

// 开始加载（可指定起始级别和时间位置）
hls.startLoad(startPosition?: number);

// 停止加载
hls.stopLoad();

// 切换质量级别（-1 为自动）
hls.currentLevel = -1;
hls.currentLevel = 2;  // 手动选择级别 2

// 获取当前质量级别
console.log(hls.currentLevel);

// 获取所有可用级别
console.log(hls.levels);

// 恢复媒体错误
hls.recoverMediaError();

// 销毁实例，释放资源
hls.destroy();
```

## 配置参数速查表

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `maxBufferLength` | number | 30 | 前向缓冲目标（秒） |
| `maxMaxBufferLength` | number | 600 | 前向缓冲上限（秒） |
| `backBufferLength` | number | 30 | 已播放保留长度（秒） |
| `highBufferWatchpoint` | number | 120 | 缓冲高水位暂停加载（秒） |
| `lowBufferWatchpoint` | number | 3 | 缓冲低水位优先加载（秒） |
| `liveSyncDurationCount` | number | 3 | 直播同步窗口（分片数） |
| `liveMaxLatencyDurationCount` | number | Infinity | 最大允许延迟（分片数） |
| `liveDurationInfinity` | boolean | false | 直播时长显示为 Infinity |
| `lowLatencyMode` | boolean | true | 低延迟模式 |
| `enableWorker` | boolean | true | 使用 Web Worker |
| `manifestLoadingTimeOut` | number | 10000 | 播放列表加载超时（ms） |
| `manifestLoadingMaxRetry` | number | 6 | 播放列表最大重试次数 |
| `levelLoadingTimeOut` | number | 10000 | 级别列表加载超时（ms） |
| `levelLoadingMaxRetry` | number | 6 | 级别列表最大重试次数 |
| `fragLoadingTimeOut` | number | 20000 | 分片加载超时（ms） |
| `fragLoadingMaxRetry` | number | 6 | 分片最大重试次数 |
| `keyLoadingTimeOut` | number | 10000 | 密钥加载超时（ms） |
| `keyLoadingMaxRetry` | number | 6 | 密钥最大重试次数 |
| `startLevel` | number | -1 | 起始质量级别（-1 自动） |
| `capLevelToPlayerSize` | boolean | false | 限制级别不超过播放器尺寸 |
| `debug` | boolean | false | 启用调试日志 |

## BrushFlow 中的配置

BrushFlow 使用以下配置来优化 IPTV 流量消耗：

```typescript
const hls = new Hls({
  enableWorker: false,      // 禁用 Worker（兼容性更好）
  maxBufferLength: 60,      // 前向缓冲 60 秒
  maxMaxBufferLength: 600,  // 最大缓冲 600 秒（默认值）
  backBufferLength: 60,     // 保留 60 秒已播放内容
});
```

视频预览通过后端代理解决 CORS 问题：

```typescript
const parsed = new URL(originalUrl);
const proxyUrl = `/api/iptv/stream${parsed.pathname}?base=${encodeURIComponent(parsed.origin)}&${parsed.searchParams.toString()}`;
hls.loadSource(proxyUrl);
```

代理会将 m3u8 中的所有 URL（包括相对路径和绝对路径）改写为完整的代理地址，hls.js 可以直接使用。

## 参考链接

- [hls.js 官方文档](https://github.com/video-dev/hls.js/blob/master/docs/API.md)
- [hls.js API 参考](https://hlsjs-dev.video-dev.org/api-docs/)
- [HLS 协议规范 (RFC 8216)](https://datatracker.ietf.org/doc/html/rfc8216)
