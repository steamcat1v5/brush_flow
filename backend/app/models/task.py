from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    link_id: Mapped[int] = mapped_column(Integer, ForeignKey("links.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/running/paused/completed/failed
    concurrency: Mapped[int] = mapped_column(Integer, default=5)
    total_downloaded: Mapped[int] = mapped_column(Integer, default=0)
    target_bytes: Mapped[int] = mapped_column(Integer, default=0)  # 0=无限循环
    speed_limit: Mapped[int] = mapped_column(Integer, default=0)  # bytes/s per conn, 0=不限
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    stopped_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
