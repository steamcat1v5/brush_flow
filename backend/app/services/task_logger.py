import asyncio
import logging

from app.database import async_session
from app.models.task_log import TaskLog

logger = logging.getLogger(__name__)


async def log_task(task_id: int, task_type: str, level: str, message: str):
    """异步写入任务日志到数据库，遇到锁冲突时自动重试。"""
    for attempt in range(3):
        try:
            async with async_session() as session:
                session.add(TaskLog(
                    task_id=task_id,
                    task_type=task_type,
                    level=level,
                    message=message,
                ))
                await session.commit()
                return
        except Exception as e:
            if "database is locked" in str(e) and attempt < 2:
                await asyncio.sleep(0.5 * (attempt + 1))
                continue
            logger.error(f"写入任务日志失败: {e}")
