from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

DATABASE_URL = f"sqlite+aiosqlite:///{settings.db_path}"

engine = create_async_engine(DATABASE_URL, echo=settings.db_echo)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session


async def init_db():
    async with engine.begin() as conn:
        from app.models import link, task, flow_log, settings_model  # noqa: F401
        from app.models import iptv_source, iptv_channel, iptv_task, task_log  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)

    # SQLite ALTER TABLE: 为已有表新增列（如果不存在）
    await _migrate_add_columns()


async def _migrate_add_columns():
    """安全地为已有表添加缺失的列"""
    import sqlite3

    db_path = settings.db_path
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    migrations = [
        ("tasks", "auto_start_cron", "TEXT"),
        ("tasks", "auto_stop_cron", "TEXT"),
        ("iptv_tasks", "auto_start_cron", "TEXT"),
        ("iptv_tasks", "auto_stop_cron", "TEXT"),
    ]

    for table, column, col_type in migrations:
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        except sqlite3.OperationalError:
            pass  # 列已存在，忽略

    conn.commit()
    conn.close()
