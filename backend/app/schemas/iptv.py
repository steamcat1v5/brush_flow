from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# ---- m3u Source ----

class IptvSourceCreate(BaseModel):
    name: str
    m3u_url: str


class IptvSourceOut(BaseModel):
    id: int
    name: str
    m3u_url: str
    channel_count: int
    last_parsed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ---- Channel ----

class IptvChannelOut(BaseModel):
    id: int
    source_id: int
    name: str
    group_title: str
    hls_url: str
    sort_order: int

    class Config:
        from_attributes = True


# ---- IPTV Task ----

class IptvTaskCreate(BaseModel):
    source_id: int
    channel_id: int
    name: str
    speed_limit: int = 0
    target_bytes: int = 0
    auto_switch_enabled: bool = False
    auto_switch_interval: int = 1800
    switch_mode: str = "random"
    auto_start_cron: Optional[str] = None
    auto_stop_cron: Optional[str] = None


class IptvTaskUpdate(BaseModel):
    name: Optional[str] = None
    channel_id: Optional[int] = None
    speed_limit: Optional[int] = None
    target_bytes: Optional[int] = None
    auto_switch_enabled: Optional[bool] = None
    auto_switch_interval: Optional[int] = None
    switch_mode: Optional[str] = None
    auto_start_cron: Optional[str] = None
    auto_stop_cron: Optional[str] = None


class IptvTaskOut(BaseModel):
    id: int
    source_id: int
    channel_id: int
    channel_name: str = ""
    name: str
    status: str
    speed_limit: int
    target_bytes: int
    total_downloaded: int
    current_speed: int = 0
    auto_switch_enabled: bool
    auto_switch_interval: int
    switch_mode: str
    auto_start_cron: Optional[str] = None
    auto_stop_cron: Optional[str] = None
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
