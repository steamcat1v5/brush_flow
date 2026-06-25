"""流量达标检查工具函数。"""

import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.settings_model import Setting
from app.services.flow_tracker import flow_tracker

logger = logging.getLogger(__name__)


async def check_daily_traffic_target(db: AsyncSession) -> str | None:
    """检查今日流量是否已达每日目标，返回警告信息或 None。

    用法:
        warning = await check_daily_traffic_target(db)
        if warning:
            # 流量已达标，可选择返回给前端提示
    """
    stmt = select(Setting).where(Setting.key == "daily_traffic_target_gb")
    result = await db.execute(stmt)
    setting = result.scalar_one_or_none()

    if not setting or setting.value == "0":
        return None

    target_gb = float(setting.value)
    stats = await flow_tracker.get_today_stats()
    current_gb = stats["total_bytes"] / (1024 ** 3)

    if current_gb >= target_gb:
        return (
            f"今日下载量 ({current_gb:.2f}GB) 已达到每日目标 ({target_gb:.2f}GB)，"
            f"任务虽已启动，但可能会被后台熔断机制再次停止。"
        )

    return None
