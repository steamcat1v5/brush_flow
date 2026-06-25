"""ORM 模型共享字段 Mixin。"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import TaskStatus


class TaskFieldsMixin:
    """Task 和 IptvTask 共享的字段定义。

    使用方式：class Task(TaskFieldsMixin, Base): ...
    注意：Mixin 不要继承 Base。
    """
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=TaskStatus.PENDING.value)
    speed_limit: Mapped[int] = mapped_column(Integer, default=0)
    target_bytes: Mapped[int] = mapped_column(Integer, default=0)
    total_downloaded: Mapped[int] = mapped_column(Integer, default=0)
    auto_start_cron: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default=None)
    auto_stop_cron: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default=None)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    stopped_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
