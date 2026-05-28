from sqlalchemy import String, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class IptvChannel(Base):
    __tablename__ = "iptv_channels"
    __table_args__ = (UniqueConstraint("source_id", "name", name="uq_source_channel"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(Integer, ForeignKey("iptv_sources.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    group_title: Mapped[str] = mapped_column(String(100), default="")
    hls_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
