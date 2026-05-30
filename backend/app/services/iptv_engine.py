# IPTV 任务在 flow_tracker 中使用 task_id + OFFSET，避免与下载任务 ID 冲突
IPTV_TASK_ID_OFFSET = 100000
import asyncio
import logging
import random
import time

import aiohttp

from app.config import settings
from app.services.flow_tracker import flow_tracker
from app.services.hls_downloader import hls_downloader
from app.services.task_logger import log_task
from app.utils.limiter import TokenBucket
from app.database import async_session
from app.models.iptv_channel import IptvChannel
from sqlalchemy import select

logger = logging.getLogger(__name__)


class IptvTaskRunner:
    """单个 IPTV 任务的运行器：持续从 HLS 流下载分片。"""

    def __init__(self, task_id: int, hls_url: str, speed_limit: int = 0,
                 target_bytes: int = 0, auto_switch_enabled: bool = False,
                 auto_switch_interval: int = 1800, source_id: int = 0,
                 current_channel_id: int = 0, switch_mode: str = "random"):
        self.task_id = task_id
        self.hls_url = hls_url
        self.speed_limit = speed_limit
        self.target_bytes = target_bytes
        self.auto_switch_enabled = auto_switch_enabled
        self.auto_switch_interval = auto_switch_interval
        self.source_id = source_id
        self.current_channel_id = current_channel_id
        self.switch_mode = switch_mode

        self.status = "pending"
        self.total_downloaded = 0
        self._stop_event = asyncio.Event()
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # 初始非暂停
        self._task: asyncio.Task | None = None
        self._limiter = TokenBucket(speed_limit, speed_limit * 2) if speed_limit > 0 else None
        self._session: aiohttp.ClientSession | None = None

    async def start(self):
        self.status = "running"
        self._stop_event.clear()
        self._pause_event.set()
        self._task = asyncio.create_task(self._main_loop())
        logger.info(f"IPTV 任务 {self.task_id} 启动，频道 URL: {self.hls_url}")
        await log_task(self.task_id, "iptv", "info", "IPTV 任务启动")

    async def stop(self):
        self.status = "stopped"
        self._stop_event.set()
        self._pause_event.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        logger.info(f"IPTV 任务 {self.task_id} 已停止，总下载: {self.total_downloaded}")
        await log_task(self.task_id, "iptv", "info", f"IPTV 任务停止，累计下载: {self.total_downloaded}")

    async def pause(self):
        self.status = "paused"
        self._pause_event.clear()
        logger.info(f"IPTV 任务 {self.task_id} 已暂停")

    async def resume(self):
        self.status = "running"
        self._pause_event.set()
        logger.info(f"IPTV 任务 {self.task_id} 已恢复")

    async def _main_loop(self):
        timeout = aiohttp.ClientTimeout(total=None, connect=10, sock_read=20)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        # 获取全局限速器
        from app.services.iptv_engine import iptv_engine

        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            self._session = session
            seen_segments: set[str] = set()
            self._switch_deadline = (time.monotonic() + self.auto_switch_interval
                               if self.auto_switch_enabled else float("inf"))
            retry_count = 0

            try:
                while not self._stop_event.is_set():
                    await self._pause_event.wait()
                    if self._stop_event.is_set():
                        break

                    try:
                        # 解析流地址
                        logger.debug(f"IPTV 任务 {self.task_id} 解析流地址: {self.hls_url[:80]}...")
                        variant_url = await hls_downloader.resolve_stream_url(session, self.hls_url)
                        logger.debug(f"IPTV 任务 {self.task_id} 变体地址: {variant_url[:80]}...")
                        await log_task(self.task_id, "iptv", "info", f"流地址解析成功，开始获取分片")
                        last_resolve_time = time.monotonic()

                        while not self._stop_event.is_set():
                            await self._pause_event.wait()
                            if self._stop_event.is_set():
                                break

                            # 每 5 分钟重新解析流地址（刷新认证 token）
                            if time.monotonic() - last_resolve_time >= 300:
                                logger.debug(f"IPTV 任务 {self.task_id} 定期刷新流地址")
                                try:
                                    variant_url = await hls_downloader.resolve_stream_url(session, self.hls_url)
                                    last_resolve_time = time.monotonic()
                                    seen_segments.clear()
                                    await log_task(self.task_id, "iptv", "info", "流地址已刷新")
                                except Exception as e:
                                    logger.warning(f"IPTV 任务 {self.task_id} 刷新流地址失败: {e}")

                            # 获取分片列表（返回 (url, duration) 元组）
                            segments = await hls_downloader.fetch_segment_list(session, variant_url)
                            new_segments = [(url, dur) for url, dur in segments if url not in seen_segments]
                            logger.debug(f"IPTV 任务 {self.task_id} 分片列表: {len(segments)} 个, 新增: {len(new_segments)} 个")

                            if not new_segments:
                                # 直播流：等待新分片
                                logger.debug(f"IPTV 任务 {self.task_id} 无新分片，等待 3s")
                                await asyncio.sleep(3)
                                # 检查是否需要换台
                                if (self.auto_switch_enabled and
                                        time.monotonic() >= self._switch_deadline):
                                    await self._switch_channel(session)
                                    break
                                continue

                            # 以实时速率逐个下载分片
                            for seg_url, seg_duration in new_segments:
                                if self._stop_event.is_set():
                                    break
                                await self._pause_event.wait()

                                bytes_down = await hls_downloader.download_segment(
                                    session=session,
                                    segment_url=seg_url,
                                    flow_callback=lambda n: flow_tracker.record(self.task_id + IPTV_TASK_ID_OFFSET, n),
                                    limiter=self._limiter,
                                    global_limiter=iptv_engine._global_limiter,
                                    stop_event=self._stop_event,
                                )
                                self.total_downloaded += bytes_down
                                if bytes_down > 0:
                                    logger.debug(f"IPTV 任务 {self.task_id} 下载分片: {bytes_down} bytes, 累计: {self.total_downloaded}")
                                else:
                                    logger.warning(f"IPTV 任务 {self.task_id} 分片下载 0 字节: {seg_url[:80]}")
                                    await log_task(self.task_id, "iptv", "warn", f"分片下载 0 字节: {seg_url[:80]}")
                                seen_segments.add(seg_url)

                                # 限制 seen_segments 大小
                                if len(seen_segments) > 500:
                                    # 移除最早的一半
                                    to_remove = list(seen_segments)[:250]
                                    for s in to_remove:
                                        seen_segments.discard(s)

                                # 检查目标量
                                if self.target_bytes > 0 and self.total_downloaded >= self.target_bytes:
                                    self.status = "completed"
                                    from app.utils.format import format_bytes
                                    await log_task(self.task_id, "iptv", "info",
                                                   f"已达目标下载量 ({format_bytes(self.total_downloaded)})，任务自动完成")
                                    return

                            # 模拟实时播放：等待最后一个分片的时长再拉取新分片
                            last_duration = new_segments[-1][1] if new_segments else 5.0
                            logger.debug(f"IPTV 任务 {self.task_id} 等待 {last_duration:.1f}s 模拟播放")
                            await asyncio.sleep(last_duration)

                            # 检查是否需要换台
                            if (self.auto_switch_enabled and
                                    time.monotonic() >= self._switch_deadline):
                                await self._switch_channel(session)
                                break  # 跳出内层循环，重新解析流地址

                            # 等待一小段时间再获取新分片
                            await asyncio.sleep(2)
                            retry_count = 0

                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        retry_count += 1
                        wait = min(2 ** retry_count, 30)
                        logger.warning(f"IPTV 任务 {self.task_id} 出错: {e}，{wait}s 后重试")
                        await log_task(self.task_id, "iptv", "warn", f"出错: {e}，{wait}s 后重试")
                        await asyncio.sleep(wait)
                        # 连续失败 5 次且启用了自动换台，尝试换台
                        if retry_count >= 5 and self.auto_switch_enabled:
                            logger.info(f"IPTV 任务 {self.task_id} 连续失败 {retry_count} 次，尝试换台")
                            await log_task(self.task_id, "iptv", "warn", f"连续失败 {retry_count} 次，自动换台")
                            await self._switch_channel(session)
                            retry_count = 0

            except asyncio.CancelledError:
                pass
            finally:
                self._session = None

    async def _switch_channel(self, session: aiohttp.ClientSession):
        """切换到同一源的另一个频道。"""
        try:
            async with async_session() as db:
                # 获取同一源的所有频道
                stmt = select(IptvChannel).where(IptvChannel.source_id == self.source_id)
                result = await db.execute(stmt)
                channels = list(result.scalars().all())

                if len(channels) <= 1:
                    logger.info(f"IPTV 任务 {self.task_id} 只有一个频道，无法换台")
                    return

                # 排除当前频道
                other_channels = [c for c in channels if c.id != self.current_channel_id]
                if not other_channels:
                    return

                if self.switch_mode == "random":
                    new_channel = random.choice(other_channels)
                else:
                    # 顺序模式：找下一个
                    current_idx = next(
                        (i for i, c in enumerate(channels) if c.id == self.current_channel_id), 0
                    )
                    next_idx = (current_idx + 1) % len(channels)
                    new_channel = channels[next_idx]

                self.hls_url = new_channel.hls_url
                self.current_channel_id = new_channel.id
                logger.info(
                    f"IPTV 任务 {self.task_id} 换台: {new_channel.name} ({new_channel.group_title})"
                )
                await log_task(self.task_id, "iptv", "info", f"换台: {new_channel.name} ({new_channel.group_title})")
        except Exception as e:
            logger.error(f"IPTV 任务 {self.task_id} 换台失败: {e}")
            await log_task(self.task_id, "iptv", "error", f"换台失败: {e}")

        # 重置换台定时器
        self._switch_deadline = time.monotonic() + self.auto_switch_interval


class IptvEngine:
    """管理所有 IPTV 任务运行器的单例。"""

    def __init__(self):
        self._runners: dict[int, IptvTaskRunner] = {}
        self._global_limiter: TokenBucket | None = None

    def set_global_limit(self, speed_limit_bps: int):
        if speed_limit_bps > 0:
            self._global_limiter = TokenBucket(speed_limit_bps, speed_limit_bps * 2)
        else:
            self._global_limiter = None

    async def start_task(self, task_id: int, hls_url: str, speed_limit: int = 0,
                         target_bytes: int = 0, auto_switch_enabled: bool = False,
                         auto_switch_interval: int = 1800, source_id: int = 0,
                         current_channel_id: int = 0, switch_mode: str = "random") -> IptvTaskRunner:
        if task_id in self._runners:
            await self._runners[task_id].stop()

        runner = IptvTaskRunner(
            task_id=task_id,
            hls_url=hls_url,
            speed_limit=speed_limit,
            target_bytes=target_bytes,
            auto_switch_enabled=auto_switch_enabled,
            auto_switch_interval=auto_switch_interval,
            source_id=source_id,
            current_channel_id=current_channel_id,
            switch_mode=switch_mode,
        )
        self._runners[task_id] = runner
        await runner.start()
        return runner

    async def stop_task(self, task_id: int):
        runner = self._runners.get(task_id)
        if runner:
            await runner.stop()
            del self._runners[task_id]

    async def pause_task(self, task_id: int):
        runner = self._runners.get(task_id)
        if runner:
            await runner.pause()

    async def resume_task(self, task_id: int):
        runner = self._runners.get(task_id)
        if runner:
            await runner.resume()

    async def stop_all(self):
        for task_id in list(self._runners.keys()):
            await self.stop_task(task_id)

    def get_runner(self, task_id: int) -> IptvTaskRunner | None:
        return self._runners.get(task_id)

    def get_all_runners(self) -> dict[int, IptvTaskRunner]:
        return dict(self._runners)


iptv_engine = IptvEngine()
