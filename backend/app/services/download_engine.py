import asyncio
import logging
from datetime import datetime

import aiohttp

from app.config import settings
from app.constants import DEFAULT_USER_AGENT
from app.services.flow_tracker import flow_tracker
from app.services.task_logger import log_task
from app.services.base_runner import BaseTaskRunner, BaseEngine
from app.models.task import TaskStatus
from app.utils.limiter import TokenBucket

logger = logging.getLogger(__name__)


class DownloadTask(BaseTaskRunner):
    """单个下载任务"""

    _task_type = "download"

    def __init__(self, task_id: int, url: str, concurrency: int, target_bytes: int = 0,
                 speed_limit: int = 0, initial_downloaded: int = 0):
        self.task_id = task_id
        self.url = url
        self.concurrency = concurrency
        self.target_bytes = target_bytes  # 0=无限
        self.speed_limit = speed_limit  # bytes/s per task (共享), 0=不限
        self.status = TaskStatus.PENDING.value
        self.total_downloaded = initial_downloaded
        self._stop_event = asyncio.Event()
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # 初始非暂停
        self._workers: list[asyncio.Task] = []
        self._retry_count = 0
        # 任务级限速器：该任务下的所有 worker 共享此令牌桶
        self._limiter = TokenBucket(speed_limit, speed_limit * 2) if speed_limit > 0 else None

    async def start(self):
        self.status = TaskStatus.RUNNING.value
        self._stop_event.clear()
        self._pause_event.set()
        logger.info(f"任务 {self.task_id} 启动，并发数: {self.concurrency}")

        for i in range(self.concurrency):
            worker = asyncio.create_task(self._worker(i))
            self._workers.append(worker)

    async def stop(self):
        self.status = TaskStatus.STOPPED.value
        self._stop_event.set()
        self._pause_event.set()
        for w in self._workers:
            w.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info(f"任务 {self.task_id} 已停止")
        await log_task(self.task_id, "download", "info", f"任务停止，累计下载: {self.total_downloaded}")

    async def _worker(self, worker_id: int):
        """单个下载协程"""
        while not self._stop_event.is_set():
            await self._pause_event.wait()
            if self._stop_event.is_set():
                break

            # 检查是否达到目标
            if self.target_bytes > 0 and self.total_downloaded >= self.target_bytes:
                asyncio.create_task(download_engine.complete_download(self.task_id))
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
            headers = {"User-Agent": DEFAULT_USER_AGENT}
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
                            asyncio.create_task(download_engine.complete_download(self.task_id))
                            break
        finally:
            # 释放全局并发许可
            if semaphore:
                semaphore.release()


class DownloadEngine(BaseEngine):
    """下载引擎：管理所有下载任务"""

    _engine_name = "下载"

    def __init__(self):
        self._runners: dict[int, DownloadTask] = {}
        self._global_limiter: TokenBucket | None = None
        self._global_semaphore: asyncio.Semaphore | None = None
        self._global_max_concurrency: int = 0

    # 保持旧 API 别名
    @property
    def _tasks(self) -> dict[int, DownloadTask]:
        return self._runners

    def set_global_concurrency(self, limit: int):
        """设置全局最大并发数"""
        self._global_max_concurrency = limit
        if limit > 0:
            self._global_semaphore = asyncio.Semaphore(limit)
        else:
            self._global_semaphore = None
        logger.info(f"全局最大并发数已设置为: {limit}")

    def get_task(self, task_id: int) -> DownloadTask | None:
        return self._runners.get(task_id)

    def get_all_tasks(self) -> dict[int, DownloadTask]:
        return dict(self._runners)

    async def start_download(self, task_id: int, url: str, concurrency: int,
                             target_bytes: int = 0, speed_limit: int = 0,
                             initial_downloaded: int = 0) -> DownloadTask:
        if task_id in self._runners:
            await self._runners[task_id].stop()

        dl_task = DownloadTask(task_id, url, concurrency, target_bytes, speed_limit, initial_downloaded)
        self._runners[task_id] = dl_task
        await dl_task.start()
        return dl_task

    async def stop_download(self, task_id: int):
        await self._stop_runner(task_id)

    async def pause_download(self, task_id: int):
        await self.pause_runner(task_id)

    async def resume_download(self, task_id: int):
        await self.resume_runner(task_id)

    async def _cancel_runner_tasks(self, runner):
        """取消下载任务的所有 worker 协程。"""
        for w in runner._workers:
            w.cancel()
        await asyncio.gather(*runner._workers, return_exceptions=True)
        runner._workers.clear()

    async def complete_download(self, task_id: int):
        """下载任务达量完成处理"""
        from app.models.task import Task
        await self.complete_runner(task_id, "download", Task)


download_engine = DownloadEngine()
