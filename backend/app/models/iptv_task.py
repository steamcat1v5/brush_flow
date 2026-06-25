from sqlalchemy import String, Integer, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TaskFieldsMixin


class IptvTask(TaskFieldsMixin, Base):
    __tablename__ = "iptv_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(Integer, ForeignKey("iptv_sources.id"), nullable=False)
    channel_id: Mapped[int] = mapped_column(Integer, ForeignKey("iptv_channels.id"), nullable=False)
    auto_switch_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_switch_interval: Mapped[int] = mapped_column(Integer, default=1800)  # 秒
    switch_mode: Mapped[str] = mapped_column(String(20), default="random")  # random/sequential
