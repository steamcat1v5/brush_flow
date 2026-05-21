import asyncio
import logging
from datetime import datetime

import aiohttp

from app.config import settings
from app.services.flow_tracker import flow_tracker
from app.utils.limiter import TokenBucket

logger = logging.getLogger(__name__)


class DownloadTask:
    """单个下载任务"""

    def __init__(self, task_id: int, url: str, concurrency: int, target_bytes: int = 0,
                 speed_limit: int = 0):
        self.task_id = task_id
        self.url = url
        self.concurrency = concurrency
        self.target_bytes = target_bytes  # 0=无限
        self.speed_limit = speed_limit  # bytes/s per conn, 0=不限
        self.status = "pending"
        self.total_downloaded = 0
        self._semaphore = asyncio.Semaphore(concurrency)
        self._stop_event = asyncio.Event()
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # 初始非暂停
        self._workers: list[asyncio.Task] = []
        self._retry_count = 0
        self._limiter = TokenBucket(speed_limit, speed_limit * 2) if speed_limit > 0 else None

    async def start(self):
        self.status = "running"
        self._stop_event.clear()
        self._pause_event.set()
        logger.info(f"任务 {self.task_id} 启动，并发数: {self.concurrency}")

        for i in range(self.concurrency):
            worker = asyncio.create_task(self._worker(i))
            self._workers.append(worker)

    async def stop(self):
        self.status = "stopped"
        self._stop_event.set()
        self._pause_event.set()  # 解除暂停以让 worker 退出
        for w in self._workers:
            w.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info(f"任务 {self.task_id} 已停止")

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
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"任务 {self.task_id} worker {worker_id} 发生异常: {e}")
                self._retry_count += 1
                if self._retry_count >= settings.max_retries:
                    logger.error(f"任务 {self.task_id} worker {worker_id} 达到最大重试次数，停止")
                    self.status = "failed"
                    break
                wait = min(2 ** self._retry_count, 30)
                logger.warning(f"任务 {self.task_id} worker {worker_id} 下载出错: {e}，{wait}s 后重试")
                await asyncio.sleep(wait)

    async def _do_download(self, worker_id: int):
        """执行一次下载（流式读取并丢弃）"""
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

                    # 限速
                    if self._limiter:
                        await self._limiter.consume(chunk_size)

                    # 达到目标
                    if self.target_bytes > 0 and self.total_downloaded >= self.target_bytes:
                        break


class DownloadEngine:
    """下载引擎：管理所有下载任务"""

    def __init__(self):
        self._tasks: dict[int, DownloadTask] = {}

    def get_task(self, task_id: int) -> DownloadTask | None:
        return self._tasks.get(task_id)

    def get_all_tasks(self) -> dict[int, DownloadTask]:
        return dict(self._tasks)

    async def start_download(self, task_id: int, url: str, concurrency: int,
                             target_bytes: int = 0, speed_limit: int = 0) -> DownloadTask:
        if task_id in self._tasks:
            await self._tasks[task_id].stop()

        dl_task = DownloadTask(task_id, url, concurrency, target_bytes, speed_limit)
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
