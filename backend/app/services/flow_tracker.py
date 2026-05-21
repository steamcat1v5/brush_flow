import asyncio
import logging
from collections import defaultdict
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.models.flow_log import FlowLog

logger = logging.getLogger(__name__)


class FlowTracker:
    """流量追踪器：内存实时计数 + 定时持久化到数据库"""

    def __init__(self):
        self._task_session_total: dict[int, int] = defaultdict(int)  # 本次程序启动后任务累计下载
        self._task_minute_increment: dict[int, int] = defaultdict(int) # 当前分钟内的增量
        self._speeds: dict[int, int] = defaultdict(int)  # 实时速度 bytes/s
        self._last_snapshot: dict[int, int] = defaultdict(int)
        self._session_total_bytes: int = 0
        self._flush_task: asyncio.Task | None = None
        self._running = False

    def record(self, task_id: int, byte_count: int):
        """记录下载字节增量"""
        self._task_session_total[task_id] += byte_count
        self._task_minute_increment[task_id] += byte_count
        self._session_total_bytes += byte_count

    def get_task_bytes(self, task_id: int) -> int:
        return self._task_session_total[task_id]

    def get_total_bytes(self) -> int:
        return self._session_total_bytes

    def get_total_speed(self) -> int:
        return sum(self._speeds.values())

    def get_speed(self, task_id: int) -> int:
        return self._speeds[task_id]

    def get_all_speeds(self) -> dict[int, int]:
        return dict(self._speeds)

    async def start(self):
        self._running = True
        self._flush_task = asyncio.create_task(self._flush_loop())
        logger.info("流量追踪器已启动")

    async def stop(self):
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()
        await self._do_flush()

    async def _flush_loop(self):
        while self._running:
            await asyncio.sleep(settings.flush_interval)
            self._calc_speeds()
            await self._do_flush()

    def _calc_speeds(self):
        interval = settings.flush_interval
        for task_id in list(self._task_session_total.keys()):
            current = self._task_session_total[task_id]
            last = self._last_snapshot.get(task_id, 0)
            self._speeds[task_id] = max(0, (current - last) // interval) if interval > 0 else 0
            self._last_snapshot[task_id] = current

    async def _do_flush(self):
        """将增量写入数据库"""
        if not self._task_minute_increment:
            return

        now = datetime.now()
        minute_ts = now.replace(second=0, microsecond=0)

        # 复制当前增量
        to_flush = dict(self._task_minute_increment)

        try:
            async with async_session() as session:
                for task_id, bytes_inc in to_flush.items():
                    stmt = select(FlowLog).where(
                        FlowLog.task_id == task_id,
                        FlowLog.logged_at == minute_ts
                    )
                    result = await session.execute(stmt)
                    existing = result.scalar_one_or_none()

                    if existing:
                        existing.bytes_down += bytes_inc
                    else:
                        log = FlowLog(
                            task_id=task_id,
                            bytes_down=bytes_inc,
                            logged_at=minute_ts
                        )
                        session.add(log)
                await session.commit()

            # Commit 成功后再减去增量，防止统计抖动
            for task_id, bytes_inc in to_flush.items():
                self._task_minute_increment[task_id] -= bytes_inc
                if self._task_minute_increment[task_id] <= 0:
                    del self._task_minute_increment[task_id]

        except Exception as e:
            logger.error(f"持久化流量数据失败: {e}")

    async def get_today_stats(self) -> dict:
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        try:
            from sqlalchemy import func
            async with async_session() as session:
                stmt = select(func.sum(FlowLog.bytes_down)).where(FlowLog.logged_at >= today_start)
                result = await session.execute(stmt)
                db_total = result.scalar() or 0

                # 今日总量 = 数据库记录 + 内存中尚未持久化的增量
                total = db_total + sum(self._task_minute_increment.values())

                return {
                    "total_bytes": total,
                    "current_speed": self.get_total_speed(),
                }
        except Exception as e:
            logger.error(f"获取今日统计失败: {e}")
            return {"total_bytes": self._session_total_bytes, "current_speed": self.get_total_speed()}


flow_tracker = FlowTracker()
