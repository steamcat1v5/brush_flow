import asyncio
import logging
import os
import ssl  # 提前导入以尝试解决 Windows OpenSSL Applink 错误
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.config import settings
from app.database import init_db
from app.routers import links, tasks, flow, settings as settings_router, iptv
from app.services.flow_tracker import flow_tracker
from app.services.download_engine import download_engine
from app.services.link_registry import seed_builtin_links
from app.services.scheduler import setup_scheduler, scheduler

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("BrushFlow 启动中...")
    await init_db()

    # 清理暂停状态的任务，恢复之前运行中的任务
    from sqlalchemy import select, update
    from app.models.task import Task
    from app.models.iptv_task import IptvTask
    from app.models.link import Link
    from app.models.iptv_channel import IptvChannel
    from app.database import async_session

    async with async_session() as session:
        # paused 任务重置为 stopped
        await session.execute(update(Task).where(Task.status == "paused").values(status="stopped"))
        await session.execute(update(IptvTask).where(IptvTask.status == "paused").values(status="stopped"))

        # 恢复之前 running 的下载任务
        stmt = select(Task).where(Task.status == "running")
        result = await session.execute(stmt)
        download_tasks = result.scalars().all()
        restored_download = 0
        for task in download_tasks:
            link = await session.get(Link, task.link_id)
            if not link:
                task.status = "stopped"
                continue
            try:
                await download_engine.start_download(
                    task_id=task.id, url=link.url, concurrency=task.concurrency,
                    target_bytes=task.target_bytes, speed_limit=task.speed_limit,
                    initial_downloaded=task.total_downloaded,
                )
                restored_download += 1
            except Exception as e:
                logger.error(f"恢复下载任务 {task.id} 失败: {e}")
                task.status = "stopped"

        # 恢复之前 running 的 IPTV 任务
        from app.services.iptv_engine import iptv_engine
        iptv_stmt = select(IptvTask).where(IptvTask.status == "running")
        iptv_result = await session.execute(iptv_stmt)
        iptv_tasks_list = iptv_result.scalars().all()
        restored_iptv = 0
        for iptv_task in iptv_tasks_list:
            ch = await session.get(IptvChannel, iptv_task.channel_id)
            if not ch:
                iptv_task.status = "stopped"
                continue
            try:
                await iptv_engine.start_task(
                    task_id=iptv_task.id, hls_url=ch.hls_url,
                    speed_limit=iptv_task.speed_limit, target_bytes=iptv_task.target_bytes,
                    auto_switch_enabled=iptv_task.auto_switch_enabled,
                    auto_switch_interval=iptv_task.auto_switch_interval,
                    source_id=iptv_task.source_id, current_channel_id=iptv_task.channel_id,
                    switch_mode=iptv_task.switch_mode,
                )
                restored_iptv += 1
            except Exception as e:
                logger.error(f"恢复 IPTV 任务 {iptv_task.id} 失败: {e}")
                iptv_task.status = "stopped"

        await session.commit()
        logger.info(f"已恢复 {restored_download} 个下载任务，{restored_iptv} 个 IPTV 任务")

    await seed_builtin_links()
    await flow_tracker.start()

    # 应用限速和并发设置
    from app.routers.settings import get_settings, apply_global_settings
    async with async_session() as session:
        current_settings = await get_settings(session)
        await apply_global_settings(current_settings.settings)

    setup_scheduler()
    scheduler.start()
    logger.info(f"BrushFlow 已启动，监听 {settings.host}:{settings.port}")
    yield
    await flow_tracker.stop()
    scheduler.shutdown()
    logger.info("BrushFlow 已停止")


app = FastAPI(
    title="BrushFlow",
    description="刷下行流量管理工具",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(links.router)
app.include_router(tasks.router)
app.include_router(flow.router)
app.include_router(settings_router.router)
app.include_router(iptv.router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "app": settings.app_name}


# IPTV 预览测试页
_static_dir = os.path.join(os.path.dirname(__file__), "static")


@app.get("/iptv-test")
async def iptv_test():
    test_file = os.path.join(_static_dir, "iptv_test.html")
    if os.path.exists(test_file):
        return FileResponse(test_file, media_type="text/html")
    return {"detail": "Not Found"}


# WebSocket 实时推送
connected_clients: set[WebSocket] = set()


@app.websocket("/ws/realtime")
async def websocket_realtime(ws: WebSocket):
    await ws.accept()
    connected_clients.add(ws)
    try:
        while True:
            # 每秒推送一次实时数据
            await asyncio.sleep(1)
            today_stats = await flow_tracker.get_today_stats()
            speeds = flow_tracker.get_all_speeds()
            data = {
                "type": "speed",
                "total_bytes_per_sec": today_stats["current_speed"],
                "total_bytes": today_stats["total_bytes"],
                "tasks": [
                    {"task_id": tid, "speed": spd}
                    for tid, spd in speeds.items()
                ],
            }
            await ws.send_json(data)
    except WebSocketDisconnect:
        connected_clients.discard(ws)
    except Exception:
        connected_clients.discard(ws)


# 前端静态文件路径
from pathlib import Path
_app_dir = Path(__file__).resolve().parent  # /app/app
_base_dir = _app_dir.parent                # /app
frontend_path = str(_base_dir / "frontend" / "dist")


@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    """处理前端静态文件和 React 路由（SPA）"""
    if os.path.exists(frontend_path):
        file_path = os.path.join(frontend_path, full_path)
        if full_path and os.path.isfile(file_path):
            return FileResponse(file_path)
        # 非文件路径一律返回 index.html（SPA 路由）
        return FileResponse(os.path.join(frontend_path, "index.html"))
    return {"detail": "Not Found"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=settings.debug)
