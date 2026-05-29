import logging

from app.database import async_session
from app.models.task_log import TaskLog

logger = logging.getLogger(__name__)


async def log_task(task_id: int, task_type: str, level: str, message: str):
    """异步写入任务日志到数据库。"""
    try:
        async with async_session() as session:
            session.add(TaskLog(
                task_id=task_id,
                task_type=task_type,
                level=level,
                message=message,
            ))
            await session.commit()
    except Exception as e:
        logger.error(f"写入任务日志失败: {e}")
