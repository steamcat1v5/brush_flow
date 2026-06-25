from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import TaskStatus
from app.models.base import TaskFieldsMixin

# 重导出 TaskStatus，保持其他模块的导入路径不变
__all__ = ["Task", "TaskStatus"]


class Task(TaskFieldsMixin, Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    link_id: Mapped[int] = mapped_column(Integer, ForeignKey("links.id"), nullable=False)
    concurrency: Mapped[int] = mapped_column(Integer, default=5)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
