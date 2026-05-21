from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.settings_model import Setting
from app.schemas.settings import SettingsOut, SettingsUpdate
from app.services.scheduler import reload_scheduler_settings

router = APIRouter(prefix="/api/settings", tags=["settings"])

DEFAULT_SETTINGS = {
    "global_concurrency": "10",
    "default_task_concurrency": "5",
    "auto_start_enabled": "false",
    "auto_start_cron": "0 0 * * *",
    "auto_stop_cron": "0 8 * * *",
    "speed_limit_per_conn": "0",
    "daily_traffic_target_gb": "0",
    "global_speed_limit_kb": "0",  # 0 表示不限速
}


async def apply_global_settings(settings_dict: dict):
    """提取限速和并发设置并应用到引擎"""
    from app.services.download_engine import download_engine

    # 应用限速
    limit_kb = int(settings_dict.get("global_speed_limit_kb", 0))
    download_engine.set_global_limit(limit_kb * 1024)

    # 应用并发数
    max_concy = int(settings_dict.get("global_concurrency", 0))
    download_engine.set_global_concurrency(max_concy)


@router.get("", response_model=SettingsOut)
async def get_settings(db: AsyncSession = Depends(get_db)):
    stmt = select(Setting)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    settings = {row.key: row.value for row in rows}
    # 补充默认值
    for key, value in DEFAULT_SETTINGS.items():
        if key not in settings:
            settings[key] = value
    return SettingsOut(settings=settings)


@router.put("", response_model=SettingsOut)
async def update_settings(data: SettingsUpdate, db: AsyncSession = Depends(get_db)):
    for key, value in data.settings.items():
        stmt = select(Setting).where(Setting.key == key)
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            existing.value = value
        else:
            db.add(Setting(key=key, value=value))
    await db.commit()
    new_settings = await get_settings(db)
    await apply_global_settings(new_settings.settings)
    await reload_scheduler_settings()
    return new_settings
