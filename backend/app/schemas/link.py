from datetime import datetime
from typing import Optional

from pydantic import BaseModel, HttpUrl


class LinkCreate(BaseModel):
    name: str
    url: str
    file_size: int = 0
    category: str = "general"


class LinkUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    file_size: Optional[int] = None
    is_active: Optional[bool] = None
    category: Optional[str] = None


class LinkOut(BaseModel):
    id: int
    name: str
    url: str
    file_size: int
    is_builtin: bool
    is_active: bool
    category: str
    created_at: datetime

    class Config:
        from_attributes = True


class LinkVerifyResult(BaseModel):
    reachable: bool
    file_size: int = 0
    content_type: str = ""
    error: str = ""
