from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, DateTime, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class IptvSource(Base):
    __tablename__ = "iptv_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    m3u_url: Mapped[str] = mapped_column(String(2000), nullable=False, unique=True)
    channel_count: Mapped[int] = mapped_column(Integer, default=0)
    last_parsed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
