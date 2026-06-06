from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class TaskCreate(BaseModel):
    link_id: int
    name: str
    concurrency: int = 5
    target_bytes: int = 0
    speed_limit: int = 0
    auto_start_cron: Optional[str] = None
    auto_stop_cron: Optional[str] = None


class TaskUpdate(BaseModel):
    name: Optional[str] = None
    concurrency: Optional[int] = None
    target_bytes: Optional[int] = None
    speed_limit: Optional[int] = None
    auto_start_cron: Optional[str] = None
    auto_stop_cron: Optional[str] = None


class TaskOut(BaseModel):
    id: int
    link_id: int
    name: str
    status: str
    concurrency: int
    total_downloaded: int
    target_bytes: int
    speed_limit: int
    retry_count: int
    auto_start_cron: Optional[str] = None
    auto_stop_cron: Optional[str] = None
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    created_at: datetime
    current_speed: int = 0  # 实时速度 bytes/s

    class Config:
        from_attributes = True
