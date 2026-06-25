"""任务运行器和引擎的基类，消除 DownloadTask/IptvTaskRunner 和 DownloadEngine/IptvEngine 之间的重复。"""

import asyncio
import logging
from datetime import datetime

from app.models.task import TaskStatus
from app.services.task_logger import log_task
from app.utils.limiter import TokenBucket

logger = logging.getLogger(__name__)


class BaseTaskRunner:
    """任务运行器基类，提供通用的状态管理和事件控制。

    子类需要在 __init__ 中设置:
        self.task_id, self.status, self.total_downloaded,
        self._stop_event, self._pause_event
    """

    task_id: int
    status: str
    total_downloaded: int
    _stop_event: asyncio.Event
    _pause_event: asyncio.Event

    # 子类可覆盖，用于日志
    _task_type: str = "unknown"

    async def pause(self):
        """暂停任务（通用实现）。"""
        self.status = TaskStatus.PAUSED.value
        self._pause_event.clear()
        logger.info(f"任务 {self.task_id} 已暂停")

    async def resume(self):
        """恢复任务（通用实现）。"""
        self.status = TaskStatus.RUNNING.value
        self._pause_event.set()
        logger.info(f"任务 {self.task_id} 已恢复")


class BaseEngine:
    """引擎管理基类，提供通用的 runner 管理和全局配置。

    子类需要在 __init__ 中设置:
        self._runners: dict
        self._global_limiter
    """

    _runners: dict
    _global_limiter: TokenBucket | None

    # 子类可覆盖，用于日志和 runner 类型名
    _engine_name: str = "unknown"

    def set_global_limit(self, speed_limit_bps: int):
        """设置全局限速 (bytes/s)"""
        if speed_limit_bps > 0:
            self._global_limiter = TokenBucket(speed_limit_bps, speed_limit_bps * 2)
        else:
            self._global_limiter = None
        logger.info(f"{self._engine_name} 全局限速已设置为: {speed_limit_bps} bytes/s")

    def get_runner(self, task_id: int):
        return self._runners.get(task_id)

    def get_all_runners(self) -> dict:
        return dict(self._runners)

    async def stop_all(self):
        for task_id in list(self._runners.keys()):
            await self._stop_runner(task_id)

    async def pause_runner(self, task_id: int):
        runner = self._runners.get(task_id)
        if runner:
            await runner.pause()

    async def resume_runner(self, task_id: int):
        runner = self._runners.get(task_id)
        if runner:
            await runner.resume()

    async def _stop_runner(self, task_id: int):
        """停止并移除 runner（子类可覆盖以添加额外逻辑）。"""
        runner = self._runners.get(task_id)
        if runner:
            await runner.stop()
            del self._runners[task_id]

    async def complete_runner(self, task_id: int, task_type: str, model_class):
        """通用的达量完成处理。

        子类应调用此方法（或在自己的 complete_* 方法中调用）。
        """
        runner = self._runners.get(task_id)
        if not runner:
            return

        # 幂等：避免并发多次触发
        if runner.status == TaskStatus.COMPLETED.value:
            return
        runner.status = TaskStatus.COMPLETED.value

        runner._stop_event.set()
        runner._pause_event.set()

        # 取消 runner 任务
        await self._cancel_runner_tasks(runner)

        # 记录日志
        from app.utils.humanize import format_bytes
        logger.info(f"{self._engine_name} 任务 {task_id} 已达目标下载量 ({format_bytes(runner.total_downloaded)})，任务自动完成")
        await log_task(task_id, task_type, "info",
                       f"已达目标下载量 ({format_bytes(runner.total_downloaded)})，任务自动完成")

        # 同步数据库状态
        try:
            from app.database import async_session
            async with async_session() as session:
                task = await session.get(model_class, task_id)
                if task:
                    task.status = TaskStatus.COMPLETED.value
                    task.total_downloaded = runner.total_downloaded
                    task.stopped_at = datetime.now()
                    await session.commit()
                    logger.info(f"{self._engine_name} 任务 {task_id} 数据库状态已成功更新为 COMPLETED")
        except Exception as e:
            logger.error(f"更新 {self._engine_name} 任务 {task_id} 完成状态到数据库失败: {e}")

        # 从内存中移除
        if task_id in self._runners:
            del self._runners[task_id]

    async def _cancel_runner_tasks(self, runner):
        """取消 runner 的后台协程（子类可覆盖）。"""
        # 默认取消 _task 属性（IptvTaskRunner 使用单个 asyncio.Task）
        task = getattr(runner, '_task', None)
        if task:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
