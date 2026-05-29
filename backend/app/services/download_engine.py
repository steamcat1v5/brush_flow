import asyncio
import logging
from datetime import datetime

import aiohttp

from app.config import settings
from app.services.flow_tracker import flow_tracker
from app.services.task_logger import log_task
from app.utils.limiter import TokenBucket

logger = logging.getLogger(__name__)


class DownloadTask:
    """单个下载任务"""

    def __init__(self, task_id: int, url: str, concurrency: int, target_bytes: int = 0,
                 speed_limit: int = 0, initial_downloaded: int = 0):
        self.task_id = task_id
        self.url = url
        self.concurrency = concurrency
        self.target_bytes = target_bytes  # 0=无限
        self.speed_limit = speed_limit  # bytes/s per task (共享), 0=不限
        self.status = "pending"
        self.total_downloaded = initial_downloaded
        self._stop_event = asyncio.Event()
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # 初始非暂停
        self._workers: list[asyncio.Task] = []
        self._retry_count = 0
        # 任务级限速器：该任务下的所有 worker 共享此令牌桶
        self._limiter = TokenBucket(speed_limit, speed_limit * 2) if speed_limit > 0 else None

    async def start(self):
        self.status = "running"
        self._stop_event.clear()
        self._pause_event.set()
        logger.info(f"任务 {self.task_id} 启动，并发数: {self.concurrency}")
        await log_task(self.task_id, "download", "info", f"任务启动，并发数: {self.concurrency}")

        for i in range(self.concurrency):
            worker = asyncio.create_task(self._worker(i))
            self._workers.append(worker)

    async def stop(self):
        self.status = "stopped"
        self._stop_event.set()
        self._pause_event.set()
        for w in self._workers:
            w.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info(f"任务 {self.task_id} 已停止")
        await log_task(self.task_id, "download", "info", f"任务停止，累计下载: {self.total_downloaded}")

    async def pause(self):
        self.status = "paused"
        self._pause_event.clear()
        logger.info(f"任务 {self.task_id} 已暂停")

    async def resume(self):
        self.status = "running"
        self._pause_event.set()
        logger.info(f"任务 {self.task_id} 已恢复")

    async def _worker(self, worker_id: int):
        """单个下载协程"""
        while not self._stop_event.is_set():
            await self._pause_event.wait()
            if self._stop_event.is_set():
                break

            # 检查是否达到目标
            if self.target_bytes > 0 and self.total_downloaded >= self.target_bytes:
                self.status = "completed"
                break

            try:
                await self._do_download(worker_id)
                self._retry_count = 0  # 成功后重置退避计数
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._retry_count += 1
                wait = min(2 ** self._retry_count, 30)
                logger.warning(f"任务 {self.task_id} worker {worker_id} 下载出错: {e}，{wait}s 后重试")
                await log_task(self.task_id, "download", "warn", f"下载出错: {e}，{wait}s 后重试")
                await asyncio.sleep(wait)

    async def _do_download(self, worker_id: int):
        """执行一次下载（流式读取并丢弃）"""
        # 获取全局并发许可
        semaphore = download_engine._global_semaphore
        if semaphore:
            await semaphore.acquire()

        try:
            timeout = aiohttp.ClientTimeout(total=None, connect=30)
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.get(self.url) as resp:
                    if resp.status not in (200, 206):
                        raise Exception(f"HTTP {resp.status}")

                    async for chunk in resp.content.iter_chunked(settings.chunk_size):
                        if self._stop_event.is_set():
                            break
                        await self._pause_event.wait()

                        chunk_size = len(chunk)
                        self.total_downloaded += chunk_size
                        flow_tracker.record(self.task_id, chunk_size)

                        # 限速：消耗任务共享的限速器
                        if self._limiter:
                            await self._limiter.consume(chunk_size)

                        # 同时消耗全局共享限速器
                        if download_engine._global_limiter:
                            await download_engine._global_limiter.consume(chunk_size)

                        # 达到目标
                        if self.target_bytes > 0 and self.total_downloaded >= self.target_bytes:
                            break
        finally:
            # 释放全局并发许可
            if semaphore:
                semaphore.release()


class DownloadEngine:
    """下载引擎：管理所有下载任务"""

    def __init__(self):
        self._tasks: dict[int, DownloadTask] = {}
        self._global_limiter: TokenBucket | None = None
        self._global_semaphore: asyncio.Semaphore | None = None
        self._global_max_concurrency: int = 0

    def set_global_limit(self, speed_limit_bps: int):
        """设置全局限速 (bytes/s)"""
        if speed_limit_bps > 0:
            self._global_limiter = TokenBucket(speed_limit_bps, speed_limit_bps * 2)
        else:
            self._global_limiter = None
        logger.info(f"全局限速已设置为: {speed_limit_bps} bytes/s")

    def set_global_concurrency(self, limit: int):
        """设置全局最大并发数"""
        self._global_max_concurrency = limit
        if limit > 0:
            self._global_semaphore = asyncio.Semaphore(limit)
        else:
            self._global_semaphore = None
        logger.info(f"全局最大并发数已设置为: {limit}")

    def get_task(self, task_id: int) -> DownloadTask | None:
        return self._tasks.get(task_id)

    def get_all_tasks(self) -> dict[int, DownloadTask]:
        return dict(self._tasks)

    async def start_download(self, task_id: int, url: str, concurrency: int,
                             target_bytes: int = 0, speed_limit: int = 0,
                             initial_downloaded: int = 0) -> DownloadTask:
        if task_id in self._tasks:
            await self._tasks[task_id].stop()

        dl_task = DownloadTask(task_id, url, concurrency, target_bytes, speed_limit, initial_downloaded)
        self._tasks[task_id] = dl_task
        await dl_task.start()
        return dl_task

    async def stop_download(self, task_id: int):
        dl_task = self._tasks.get(task_id)
        if dl_task:
            await dl_task.stop()
            del self._tasks[task_id]

    async def pause_download(self, task_id: int):
        dl_task = self._tasks.get(task_id)
        if dl_task:
            await dl_task.pause()

    async def resume_download(self, task_id: int):
        dl_task = self._tasks.get(task_id)
        if dl_task:
            await dl_task.resume()

    async def stop_all(self):
        for task_id in list(self._tasks.keys()):
            await self.stop_download(task_id)


download_engine = DownloadEngine()
