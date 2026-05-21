from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FlowLog(Base):
    __tablename__ = "flow_logs"
    __table_args__ = (UniqueConstraint("task_id", "logged_at", name="uq_task_logged"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    bytes_down: Mapped[int] = mapped_column(Integer, nullable=False)
    logged_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)


class FlowSummary(Base):
    __tablename__ = "flow_summaries"
    __table_args__ = (UniqueConstraint("period_type", "period_key", name="uq_period"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    period_type: Mapped[str] = mapped_column(String(10), nullable=False)  # day/week/month
    period_key: Mapped[str] = mapped_column(String(20), nullable=False)  # 2026-05-18 / 2026-W20 / 2026-05
    total_bytes: Mapped[int] = mapped_column(Integer, default=0)
    task_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_speed: Mapped[int] = mapped_column(Integer, default=0)
    peak_speed: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
