from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text, event

from app.config import settings

DATABASE_URL = f"sqlite+aiosqlite:///{settings.db_path}"

engine = create_async_engine(
    DATABASE_URL,
    echo=settings.db_echo,
    connect_args={"timeout": 30},
)


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _connection_record):
    """启用 WAL 模式和忙等待超时，减少并发写锁冲突"""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


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

    # 通过异步引擎安全地为已有表添加缺失的列
    await _migrate_add_columns()


async def _migrate_add_columns():
    """安全地为已有表添加缺失的列"""
    migrations = [
        ("tasks", "auto_start_cron", "TEXT"),
        ("tasks", "auto_stop_cron", "TEXT"),
        ("iptv_tasks", "auto_start_cron", "TEXT"),
        ("iptv_tasks", "auto_stop_cron", "TEXT"),
    ]

    async with engine.begin() as conn:
        for table, column, col_type in migrations:
            try:
                await conn.execute(
                    text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
                )
            except Exception:
                pass  # 列已存在，忽略
