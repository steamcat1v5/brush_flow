from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class IptvTask(Base):
    __tablename__ = "iptv_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(Integer, ForeignKey("iptv_sources.id"), nullable=False)
    channel_id: Mapped[int] = mapped_column(Integer, ForeignKey("iptv_channels.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    speed_limit: Mapped[int] = mapped_column(Integer, default=0)  # bytes/s, 0=unlimited
    target_bytes: Mapped[int] = mapped_column(Integer, default=0)  # 0=unlimited
    total_downloaded: Mapped[int] = mapped_column(Integer, default=0)
    auto_switch_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_switch_interval: Mapped[int] = mapped_column(Integer, default=1800)  # 秒
    switch_mode: Mapped[str] = mapped_column(String(20), default="random")  # random/sequential
    auto_start_cron: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default=None)
    auto_stop_cron: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default=None)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    stopped_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
