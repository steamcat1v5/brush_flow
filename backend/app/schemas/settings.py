from typing import Dict

from pydantic import BaseModel


class SettingsOut(BaseModel):
    settings: Dict[str, str]


class SettingsUpdate(BaseModel):
    settings: Dict[str, str]
