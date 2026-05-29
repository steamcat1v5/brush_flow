from datetime import datetime

import aiohttp
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.iptv_source import IptvSource
from app.models.iptv_channel import IptvChannel
from app.models.iptv_task import IptvTask
from app.schemas.iptv import (
    IptvSourceCreate, IptvSourceOut,
    IptvChannelOut,
    IptvTaskCreate, IptvTaskUpdate, IptvTaskOut,
)
from app.services.m3u_parser import parse_m3u
from app.services.iptv_engine import iptv_engine
from app.services.flow_tracker import flow_tracker

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
    source = await db.get(IptvSource, source_id)
    if not source:
        raise HTTPException(404, "源不存在")

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
    source = await db.get(IptvSource, source_id)
    if not source:
        raise HTTPException(404, "源不存在")

    await _refresh_channels(source, db)
    await db.refresh(source)
    return {"ok": True, "channel_count": source.channel_count}


@router.get("/sources/{source_id}/channels", response_model=list[IptvChannelOut])
async def list_channels(
    source_id: int,
    group: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    source = await db.get(IptvSource, source_id)
    if not source:
        raise HTTPException(404, "源不存在")

    stmt = select(IptvChannel).where(IptvChannel.source_id == source_id)
    if group:
        stmt = stmt.where(IptvChannel.group_title == group)
    stmt = stmt.order_by(IptvChannel.sort_order)
    result = await db.execute(stmt)
    return result.scalars().all()


async def _refresh_channels(source: IptvSource, db: AsyncSession):
    """获取 m3u 内容并更新频道列表。"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
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
    speed = flow_tracker.get_speed(task.id)
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
        started_at=task.started_at,
        stopped_at=task.stopped_at,
        created_at=task.created_at,
    )


@router.post("/tasks", response_model=IptvTaskOut)
async def create_iptv_task(data: IptvTaskCreate, db: AsyncSession = Depends(get_db)):
    # 验证源和频道
    source = await db.get(IptvSource, data.source_id)
    if not source:
        raise HTTPException(404, "源不存在")
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
    task = await db.get(IptvTask, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(task, key, value)

    await db.commit()
    await db.refresh(task)

    ch = await db.get(IptvChannel, task.channel_id)
    return _iptv_task_to_out(task, ch.name if ch else "")


@router.delete("/tasks/{task_id}")
async def delete_iptv_task(task_id: int, db: AsyncSession = Depends(get_db)):
    task = await db.get(IptvTask, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")

    if task.status == "running":
        await iptv_engine.stop_task(task_id)

    await db.delete(task)
    await db.commit()
    return {"ok": True}


@router.post("/tasks/{task_id}/start")
async def start_iptv_task(task_id: int, db: AsyncSession = Depends(get_db)):
    task = await db.get(IptvTask, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")

    channel = await db.get(IptvChannel, task.channel_id)
    if not channel:
        raise HTTPException(404, "关联频道不存在")

    # 检查今日流量是否已达标
    warning = None
    from app.models.settings_model import Setting
    stmt = select(Setting).where(Setting.key == "daily_traffic_target_gb")
    result = await db.execute(stmt)
    setting = result.scalar_one_or_none()
    if setting and setting.value != "0":
        target_gb = float(setting.value)
        stats = await flow_tracker.get_today_stats()
        current_gb = stats["total_bytes"] / (1024 ** 3)
        if current_gb >= target_gb:
            warning = (
                f"今日下载量 ({current_gb:.2f}GB) 已达到每日目标 ({target_gb:.2f}GB)，"
                f"任务虽已启动，但可能会被后台熔断机制再次停止。"
            )

    task.status = "running"
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
    return {"ok": True, "message": "IPTV 任务已启动", "warning": warning}


@router.post("/tasks/{task_id}/stop")
async def stop_iptv_task(task_id: int, db: AsyncSession = Depends(get_db)):
    task = await db.get(IptvTask, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")

    runner = iptv_engine.get_runner(task_id)
    if runner:
        task.total_downloaded = runner.total_downloaded
        await iptv_engine.stop_task(task_id)

    task.status = "stopped"
    task.stopped_at = datetime.now()
    await db.commit()
    return {"ok": True, "message": "IPTV 任务已停止"}


@router.post("/tasks/{task_id}/pause")
async def pause_iptv_task(task_id: int, db: AsyncSession = Depends(get_db)):
    task = await db.get(IptvTask, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")

    await iptv_engine.pause_task(task_id)
    task.status = "paused"
    await db.commit()
    return {"ok": True, "message": "IPTV 任务已暂停"}


@router.post("/tasks/{task_id}/resume")
async def resume_iptv_task(task_id: int, db: AsyncSession = Depends(get_db)):
    task = await db.get(IptvTask, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")

    await iptv_engine.resume_task(task_id)
    task.status = "running"
    await db.commit()
    return {"ok": True, "message": "IPTV 任务已恢复"}


@router.post("/tasks/stop-all")
async def stop_all_iptv_tasks(db: AsyncSession = Depends(get_db)):
    await iptv_engine.stop_all()

    stmt = select(IptvTask).where(IptvTask.status.in_(["running", "paused"]))
    result = await db.execute(stmt)
    tasks = result.scalars().all()
    for task in tasks:
        task.status = "stopped"
        task.stopped_at = datetime.now()
    await db.commit()
    return {"ok": True, "stopped_count": len(tasks)}


@router.get("/proxy")
async def proxy_stream(url: str = Query(...)):
    """代理 IPTV 流请求，解决浏览器 CORS 和网络访问限制。"""
    from urllib.parse import urljoin

    timeout = aiohttp.ClientTimeout(total=None, connect=10)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    session = aiohttp.ClientSession(timeout=timeout, headers=headers)

    try:
        resp = await session.get(url)
        if resp.status != 200:
            await session.close()
            raise HTTPException(resp.status, f"上游返回 HTTP {resp.status}")

        content_type = resp.headers.get("Content-Type", "application/octet-stream")

        # 尝试读取内容并检测 m3u8
        try:
            raw = await resp.read()
        except Exception:
            await resp.release()
            await session.close()
            raise
        await resp.release()
        await session.close()

        # 检测是否为 m3u8
        is_m3u8 = ("mpegurl" in content_type.lower()
                    or url.endswith(".m3u8") or url.endswith(".m3u")
                    or b"#EXTM3U" in raw[:200])

        if is_m3u8:
            body = raw.decode("utf-8", errors="ignore")
            base_url = url.rsplit("/", 1)[0] + "/"
            lines = []
            for line in body.splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    # 非注释行 = URL，改写为代理 URL
                    if stripped.startswith("http"):
                        abs_url = stripped
                    else:
                        abs_url = urljoin(base_url, stripped)
                    from urllib.parse import quote
                    lines.append(f"/api/iptv/proxy?url={quote(abs_url, safe='')}")
                else:
                    lines.append(line)
            rewritten = "\n".join(lines)
            return StreamingResponse(
                iter([rewritten.encode("utf-8")]),
                media_type="application/vnd.apple.mpegurl",
                headers={"Access-Control-Allow-Origin": "*"},
            )

        # 非 m3u8，直接返回
        return StreamingResponse(
            iter([raw]),
            media_type=content_type,
            headers={"Access-Control-Allow-Origin": "*"},
        )
    except aiohttp.ClientError as e:
        await session.close()
        raise HTTPException(502, f"代理请求失败: {e}")
