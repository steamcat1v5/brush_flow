from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class FlowLogOut(BaseModel):
    task_id: int
    bytes_down: int
    logged_at: datetime

    class Config:
        from_attributes = True


class FlowSummaryOut(BaseModel):
    period_type: str
    period_key: str
    total_bytes: int
    task_count: int
    avg_speed: int
    peak_speed: int
    download_bytes: int = 0
    iptv_bytes: int = 0

    class Config:
        from_attributes = True


class TodayStats(BaseModel):
    total_bytes: int
    current_speed: int
    active_tasks: int
    uptime_seconds: int


class RealtimeData(BaseModel):
    total_bytes_per_sec: int
    tasks: list
