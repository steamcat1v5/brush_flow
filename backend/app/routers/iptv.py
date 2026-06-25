from datetime import datetime

import aiohttp
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.constants import DEFAULT_USER_AGENT
from app.models.iptv_source import IptvSource
from app.models.iptv_channel import IptvChannel
from app.models.iptv_task import IptvTask
from app.models.task import TaskStatus
from app.schemas.iptv import (
    IptvSourceCreate, IptvSourceOut,
    IptvChannelOut,
    IptvTaskCreate, IptvTaskUpdate, IptvTaskOut,
)
from app.services.m3u_parser import parse_m3u
from app.services.iptv_engine import iptv_engine, IPTV_TASK_ID_OFFSET
from app.services.flow_tracker import flow_tracker
from app.services.task_logger import log_task
from app.services.scheduler import schedule_task_jobs, remove_task_jobs
from app.utils.traffic import check_daily_traffic_target
from app.routers.crud_helpers import get_or_404, partial_update

router = APIRouter(prefix="/api/iptv", tags=["iptv"])


# ---- m3u Source 管理 ----

@router.post("/sources", response_model=IptvSourceOut)
async def create_source(data: IptvSourceCreate, db: AsyncSession = Depends(get_db)):
    """添加 m3u 源并自动解析频道。"""
    # 检查是否已存在
    existing = await db.execute(
        select(IptvSource).where(IptvSource.m3u_url == data.m3u_url)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, "该 m3u 地址已存在")

    source = IptvSource(name=data.name, m3u_url=data.m3u_url)
    db.add(source)
    await db.commit()
    await db.refresh(source)

    # 解析频道
    await _refresh_channels(source, db)
    await db.refresh(source)
    return source


@router.get("/sources", response_model=list[IptvSourceOut])
async def list_sources(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(IptvSource).order_by(IptvSource.id.desc()))
    return result.scalars().all()


@router.delete("/sources/{source_id}")
async def delete_source(source_id: int, db: AsyncSession = Depends(get_db)):
    source = await get_or_404(db, IptvSource, source_id, "源不存在")

    # 删除关联频道
    channels = await db.execute(
        select(IptvChannel).where(IptvChannel.source_id == source_id)
    )
    for ch in channels.scalars().all():
        await db.delete(ch)

    await db.delete(source)
    await db.commit()
    return {"ok": True}


@router.post("/sources/{source_id}/refresh")
async def refresh_source(source_id: int, db: AsyncSession = Depends(get_db)):
    """重新解析 m3u 源的频道列表。"""
    source = await get_or_404(db, IptvSource, source_id, "源不存在")

    await _refresh_channels(source, db)
    await db.refresh(source)
    return {"ok": True, "channel_count": source.channel_count}


@router.get("/sources/{source_id}/channels", response_model=list[IptvChannelOut])
async def list_channels(
    source_id: int,
    group: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    source = await get_or_404(db, IptvSource, source_id, "源不存在")

    stmt = select(IptvChannel).where(IptvChannel.source_id == source_id)
    if group:
        stmt = stmt.where(IptvChannel.group_title == group)
    stmt = stmt.order_by(IptvChannel.sort_order)
    result = await db.execute(stmt)
    return result.scalars().all()


async def _refresh_channels(source: IptvSource, db: AsyncSession):
    """获取 m3u 内容并更新频道列表。"""
    headers = {"User-Agent": DEFAULT_USER_AGENT}
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(source.m3u_url) as resp:
                if resp.status != 200:
                    raise HTTPException(400, f"获取 m3u 失败: HTTP {resp.status}")
                content = await resp.text()
    except aiohttp.ClientError as e:
        raise HTTPException(400, f"获取 m3u 失败: {e}")

    channels = parse_m3u(content)

    # 删除旧频道
    await db.execute(delete(IptvChannel).where(IptvChannel.source_id == source.id))

    # 插入新频道
    for i, ch in enumerate(channels):
        db.add(IptvChannel(
            source_id=source.id,
            name=ch.name,
            group_title=ch.group_title,
            hls_url=ch.hls_url,
            sort_order=i,
        ))

    source.channel_count = len(channels)
    source.last_parsed_at = datetime.now()
    await db.commit()


# ---- IPTV Task 管理 ----

def _iptv_task_to_out(task: IptvTask, channel_name: str = "") -> IptvTaskOut:
    runner = iptv_engine.get_runner(task.id)
    speed = flow_tracker.get_speed(task.id + IPTV_TASK_ID_OFFSET)
    total = runner.total_downloaded if runner else task.total_downloaded

    return IptvTaskOut(
        id=task.id,
        source_id=task.source_id,
        channel_id=task.channel_id,
        channel_name=channel_name,
        name=task.name,
        status=runner.status if runner else task.status,
        speed_limit=task.speed_limit,
        target_bytes=task.target_bytes,
        total_downloaded=total,
        current_speed=speed,
        auto_switch_enabled=task.auto_switch_enabled,
        auto_switch_interval=task.auto_switch_interval,
        switch_mode=task.switch_mode,
        auto_start_cron=task.auto_start_cron,
        auto_stop_cron=task.auto_stop_cron,
        started_at=task.started_at,
        stopped_at=task.stopped_at,
        created_at=task.created_at,
    )


@router.post("/tasks", response_model=IptvTaskOut)
async def create_iptv_task(data: IptvTaskCreate, db: AsyncSession = Depends(get_db)):
    # 验证源和频道
    source = await get_or_404(db, IptvSource, data.source_id, "源不存在")
    channel = await db.get(IptvChannel, data.channel_id)
    if not channel or channel.source_id != data.source_id:
        raise HTTPException(404, "频道不存在或不属于该源")

    task = IptvTask(
        source_id=data.source_id,
        channel_id=data.channel_id,
        name=data.name,
        speed_limit=data.speed_limit,
        target_bytes=data.target_bytes,
        auto_switch_enabled=data.auto_switch_enabled,
        auto_switch_interval=data.auto_switch_interval,
        switch_mode=data.switch_mode,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    # 注册定时任务
    if task.auto_start_cron or task.auto_stop_cron:
        schedule_task_jobs("iptv", task.id, task.auto_start_cron, task.auto_stop_cron)
    return _iptv_task_to_out(task, channel.name)


@router.get("/tasks", response_model=list[IptvTaskOut])
async def list_iptv_tasks(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(IptvTask).order_by(IptvTask.id.desc()))
    tasks = result.scalars().all()
    out = []
    for task in tasks:
        ch = await db.get(IptvChannel, task.channel_id)
        out.append(_iptv_task_to_out(task, ch.name if ch else ""))
    return out


@router.put("/tasks/{task_id}", response_model=IptvTaskOut)
async def update_iptv_task(task_id: int, data: IptvTaskUpdate, db: AsyncSession = Depends(get_db)):
    task = await get_or_404(db, IptvTask, task_id, "任务不存在")
    await partial_update(db, task, data)

    # 刷新定时任务
    schedule_task_jobs("iptv", task.id, task.auto_start_cron, task.auto_stop_cron)

    ch = await db.get(IptvChannel, task.channel_id)
    return _iptv_task_to_out(task, ch.name if ch else "")


@router.delete("/tasks/{task_id}")
async def delete_iptv_task(task_id: int, db: AsyncSession = Depends(get_db)):
    task = await get_or_404(db, IptvTask, task_id, "任务不存在")

    if task.status == TaskStatus.RUNNING.value:
        await iptv_engine.stop_task(task_id)

    # 移除定时任务
    remove_task_jobs("iptv", task_id)

    await db.delete(task)
    await db.commit()
    return {"ok": True}


@router.post("/tasks/{task_id}/start")
async def start_iptv_task(task_id: int, db: AsyncSession = Depends(get_db)):
    task = await get_or_404(db, IptvTask, task_id, "任务不存在")

    # 任务已在运行中，拒绝重复启动
    if task.status == TaskStatus.RUNNING.value:
        raise HTTPException(400, "任务已在运行中")

    channel = await get_or_404(db, IptvChannel, task.channel_id, "关联频道不存在")

    # 检查今日流量是否已达标
    warning = await check_daily_traffic_target(db)

    # 有目标下载量的已完成任务重启时需重置计数，否则引擎会立即再次触发完成
    if task.status == TaskStatus.COMPLETED.value and task.target_bytes > 0:
        task.total_downloaded = 0
        await log_task(task.id, "iptv", "info", "重启已达量完成 IPTV 任务，下载量计数已重置")

    task.status = TaskStatus.RUNNING.value
    task.started_at = datetime.now()
    await db.commit()

    await iptv_engine.start_task(
        task_id=task.id,
        hls_url=channel.hls_url,
        speed_limit=task.speed_limit,
        target_bytes=task.target_bytes,
        auto_switch_enabled=task.auto_switch_enabled,
        auto_switch_interval=task.auto_switch_interval,
        source_id=task.source_id,
        current_channel_id=task.channel_id,
        switch_mode=task.switch_mode,
    )
    await log_task(task.id, "iptv", "info", "用户启动 IPTV 任务")
    return {"ok": True, "message": "IPTV 任务已启动", "warning": warning}


@router.post("/tasks/{task_id}/stop")
async def stop_iptv_task(task_id: int, db: AsyncSession = Depends(get_db)):
    task = await get_or_404(db, IptvTask, task_id, "任务不存在")

    runner = iptv_engine.get_runner(task_id)
    if runner:
        task.total_downloaded = runner.total_downloaded
        await iptv_engine.stop_task(task_id)

    task.status = TaskStatus.STOPPED.value
    task.stopped_at = datetime.now()
    await db.commit()
    await log_task(task_id, "iptv", "info", "用户停止 IPTV 任务")
    return {"ok": True, "message": "IPTV 任务已停止"}


@router.post("/tasks/{task_id}/pause")
async def pause_iptv_task(task_id: int, db: AsyncSession = Depends(get_db)):
    task = await get_or_404(db, IptvTask, task_id, "任务不存在")

    await iptv_engine.pause_task(task_id)
    task.status = TaskStatus.PAUSED.value
    await db.commit()
    await log_task(task_id, "iptv", "info", "用户暂停 IPTV 任务")
    return {"ok": True, "message": "IPTV 任务已暂停"}


@router.post("/tasks/{task_id}/resume")
async def resume_iptv_task(task_id: int, db: AsyncSession = Depends(get_db)):
    task = await get_or_404(db, IptvTask, task_id, "任务不存在")

    await iptv_engine.resume_task(task_id)
    task.status = TaskStatus.RUNNING.value
    await db.commit()
    await log_task(task_id, "iptv", "info", "用户恢复 IPTV 任务")
    return {"ok": True, "message": "IPTV 任务已恢复"}


@router.post("/tasks/stop-all")
async def stop_all_iptv_tasks(db: AsyncSession = Depends(get_db)):
    await iptv_engine.stop_all()

    stmt = select(IptvTask).where(IptvTask.status.in_([TaskStatus.RUNNING.value, TaskStatus.PAUSED.value]))
    result = await db.execute(stmt)
    tasks = result.scalars().all()
    for task in tasks:
        task.status = TaskStatus.STOPPED.value
        task.stopped_at = datetime.now()
    await db.commit()
    return {"ok": True, "stopped_count": len(tasks)}


@router.get("/stream/{path:path}")
async def stream_proxy(path: str, request: Request, base: str = Query(...)):
    """路径代理，保留原始 URL 的所有查询参数。"""
    # 从请求中提取除 base 以外的原始查询参数
    original_params = dict(request.query_params)
    original_params.pop("base", None)
    from urllib.parse import urlencode
    qs = urlencode(original_params)
    target_url = f"{base.rstrip('/')}/{path}"
    if qs:
        target_url = f"{target_url}?{qs}"

    timeout = aiohttp.ClientTimeout(total=None, connect=10, sock_read=20)
    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Referer": f"{base}/",
    }

    session = aiohttp.ClientSession(timeout=timeout, headers=headers)
    try:
        resp = await session.get(target_url)
        if resp.status != 200:
            await session.close()
            raise HTTPException(resp.status, f"上游返回 HTTP {resp.status}")

        content_type = resp.headers.get("Content-Type", "application/octet-stream")
        raw = await resp.read()
        await resp.release()
        await session.close()

        # 检测 m3u8 并改写 URL
        is_m3u8 = ("mpegurl" in content_type.lower()
                    or target_url.endswith(".m3u8") or target_url.endswith(".m3u")
                    or b"#EXTM3U" in raw[:200])

        if is_m3u8:
            body = raw.decode("utf-8", errors="ignore")
            lines = []
            from urllib.parse import urlparse, urljoin, quote
            # target_url 的目录作为相对路径的解析基准
            target_dir = target_url.rsplit("/", 1)[0] + "/"
            host = request.headers.get("host", "localhost:8765")
            scheme = request.headers.get("x-forwarded-proto", "http")
            self_base = f"{scheme}://{host}"

            for line in body.splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    # 解析为完整的原始绝对 URL
                    if stripped.startswith("http"):
                        abs_url = stripped
                    else:
                        abs_url = urljoin(target_dir, stripped)
                    # 转为代理 URL
                    parsed = urlparse(abs_url)
                    proxy_qs = f"base={quote(parsed.scheme + '://' + parsed.netloc, safe='')}"
                    if parsed.query:
                        proxy_qs += f"&{parsed.query}"
                    lines.append(f"{self_base}/api/iptv/stream{parsed.path}?{proxy_qs}")
                else:
                    lines.append(line)
            rewritten = "\n".join(lines)
            return StreamingResponse(
                iter([rewritten.encode("utf-8")]),
                media_type="application/vnd.apple.mpegurl",
                headers={"Access-Control-Allow-Origin": "*"},
            )

        return StreamingResponse(
            iter([raw]),
            media_type=content_type,
            headers={"Access-Control-Allow-Origin": "*"},
        )
    except aiohttp.ClientError as e:
        await session.close()
        raise HTTPException(502, f"代理请求失败: {e}")
