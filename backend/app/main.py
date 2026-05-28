import asyncio
import logging
import os
import ssl  # 提前导入以尝试解决 Windows OpenSSL Applink 错误
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.database import init_db
from app.routers import links, tasks, flow, settings as settings_router, iptv
from app.services.flow_tracker import flow_tracker
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

    # 清理启动前的僵尸任务状态
    from sqlalchemy import update
    from app.models.task import Task
    from app.models.iptv_task import IptvTask
    from app.database import async_session
    async with async_session() as session:
        await session.execute(update(Task).where(Task.status.in_(["running", "paused"])).values(status="stopped"))
        await session.execute(update(IptvTask).where(IptvTask.status.in_(["running", "paused"])).values(status="stopped"))
        await session.commit()
    logger.info("已重置所有异常关闭的任务状态")

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


# 挂载前端静态文件（必须在 API 和 WebSocket 路由之后）
from pathlib import Path
_app_dir = Path(__file__).resolve().parent  # /app/app
_base_dir = _app_dir.parent                # /app
frontend_path = str(_base_dir / "frontend" / "dist")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")


@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    """处理 React 路由，找不到的文件返回 index.html"""
    if os.path.exists(os.path.join(frontend_path, full_path)):
        return FileResponse(os.path.join(frontend_path, full_path))
    return FileResponse(os.path.join(frontend_path, "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=settings.debug)
