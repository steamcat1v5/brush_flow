from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.link import Link
from app.models.task import Task, TaskStatus
from app.schemas.task import TaskCreate, TaskOut, TaskUpdate
from app.services.download_engine import download_engine
from app.services.flow_tracker import flow_tracker
from app.services.task_logger import log_task
from app.services.scheduler import schedule_task_jobs, remove_task_jobs

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _task_to_out(task: Task) -> TaskOut:
    speed = flow_tracker.get_speed(task.id)
    # 尝试从下载引擎同步最新的已下载总量
    total_downloaded = task.total_downloaded
    dl_task = download_engine.get_task(task.id)
    if dl_task:
        total_downloaded = dl_task.total_downloaded

    return TaskOut(
        id=task.id,
        link_id=task.link_id,
        name=task.name,
        status=dl_task.status if dl_task else task.status,
        concurrency=task.concurrency,
        total_downloaded=total_downloaded,
        target_bytes=task.target_bytes,
        speed_limit=task.speed_limit,
        retry_count=task.retry_count,
        auto_start_cron=task.auto_start_cron,
        auto_stop_cron=task.auto_stop_cron,
        started_at=task.started_at,
        stopped_at=task.stopped_at,
        created_at=task.created_at,
        current_speed=speed,
    )


@router.get("", response_model=list[TaskOut])
async def list_tasks(
    status: TaskStatus | None = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Task)
    if status:
        stmt = stmt.where(Task.status == status.value)
    stmt = stmt.order_by(Task.id)
    result = await db.execute(stmt)
    tasks = result.scalars().all()
    return [_task_to_out(t) for t in tasks]


@router.post("", response_model=TaskOut)
async def create_task(data: TaskCreate, db: AsyncSession = Depends(get_db)):
    link = await db.get(Link, data.link_id)
    if not link:
        raise HTTPException(404, "链接不存在")

    task = Task(
        link_id=data.link_id,
        name=data.name,
        concurrency=data.concurrency,
        target_bytes=data.target_bytes,
        speed_limit=data.speed_limit,
        auto_start_cron=data.auto_start_cron,
        auto_stop_cron=data.auto_stop_cron,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    # 注册定时任务
    if task.auto_start_cron or task.auto_stop_cron:
        schedule_task_jobs("download", task.id, task.auto_start_cron, task.auto_stop_cron)
    return _task_to_out(task)


@router.put("/{task_id}", response_model=TaskOut)
async def update_task(task_id: int, data: TaskUpdate, db: AsyncSession = Depends(get_db)):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(task, key, value)

    await db.commit()
    await db.refresh(task)

    # 刷新定时任务
    schedule_task_jobs("download", task.id, task.auto_start_cron, task.auto_stop_cron)

    # 如果任务正在运行，提醒用户重启生效
    return _task_to_out(task)


@router.get("/{task_id}", response_model=TaskOut)
async def get_task(task_id: int, db: AsyncSession = Depends(get_db)):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")

    # 同步下载引擎中的实时数据
    dl_task = download_engine.get_task(task_id)
    if dl_task:
        task.total_downloaded = dl_task.total_downloaded
        task.status = dl_task.status

    return _task_to_out(task)


@router.post("/{task_id}/start")
async def start_task(task_id: int, db: AsyncSession = Depends(get_db)):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")

    # 任务已在运行中，拒绝重复启动
    if task.status == TaskStatus.RUNNING.value:
        raise HTTPException(400, "任务已在运行中")

    link = await db.get(Link, task.link_id)
    if not link:
        raise HTTPException(404, "关联链接不存在")

    # 检查今日流量是否已达标 (仅用于返回提醒)
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
            warning = f"今日下载量 ({current_gb:.2f}GB) 已达到每日目标 ({target_gb:.2f}GB)，任务虽已启动，但可能会被后台熔断机制再次停止。"

    # 有目标下载量的已完成任务重启时需重置计数，否则引擎会立即再次触发完成
    if task.status == TaskStatus.COMPLETED.value and task.target_bytes > 0:
        task.total_downloaded = 0
        await log_task(task.id, "download", "info", "重启已达量完成任务，下载量计数已重置")

    # 如果任务之前失败过，重置重试计数
    task.retry_count = 0
    task.status = TaskStatus.RUNNING.value
    task.started_at = datetime.now()
    await db.commit()

    # 在引擎中启动
    await download_engine.start_download(
        task_id=task.id,
        url=link.url,
        concurrency=task.concurrency,
        target_bytes=task.target_bytes,
        speed_limit=task.speed_limit,
        initial_downloaded=task.total_downloaded,
    )
    await log_task(task.id, "download", "info", "用户手动启动任务")
    return {"ok": True, "message": "任务已启动", "warning": warning}


@router.post("/{task_id}/pause")
async def pause_task(task_id: int, db: AsyncSession = Depends(get_db)):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")

    await download_engine.pause_download(task_id)
    task.status = TaskStatus.PAUSED.value
    await db.commit()
    await log_task(task_id, "download", "info", "用户暂停任务")
    return {"ok": True, "message": "任务已暂停"}


@router.post("/{task_id}/resume")
async def resume_task(task_id: int, db: AsyncSession = Depends(get_db)):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")

    await download_engine.resume_download(task_id)
    task.status = TaskStatus.RUNNING.value
    await db.commit()
    await log_task(task_id, "download", "info", "用户恢复任务")
    return {"ok": True, "message": "任务已恢复"}


@router.post("/{task_id}/stop")
async def stop_task(task_id: int, db: AsyncSession = Depends(get_db)):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")

    dl_task = download_engine.get_task(task_id)
    if dl_task:
        # 持久化最终下载量：数据库原有量 + 本次运行量
        task.total_downloaded = dl_task.total_downloaded
        await download_engine.stop_download(task_id)

    task.status = TaskStatus.STOPPED.value
    task.stopped_at = datetime.now()
    await db.commit()
    await log_task(task_id, "download", "info", "用户停止任务")
    return {"ok": True, "message": "任务已停止"}


@router.delete("/{task_id}")
async def delete_task(task_id: int, db: AsyncSession = Depends(get_db)):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")

    if task.status == TaskStatus.RUNNING.value:
        await download_engine.stop_download(task_id)

    # 移除定时任务
    remove_task_jobs("download", task_id)

    await db.delete(task)
    await db.commit()
    return {"ok": True}


@router.post("/stop-all")
async def stop_all_tasks(db: AsyncSession = Depends(get_db)):
    """停止所有运行中的任务"""
    await download_engine.stop_all()

    stmt = select(Task).where(Task.status.in_([TaskStatus.RUNNING.value, TaskStatus.PAUSED.value]))
    result = await db.execute(stmt)
    tasks = result.scalars().all()
    for task in tasks:
        task.status = TaskStatus.STOPPED.value
        task.stopped_at = datetime.now()
    await db.commit()
    return {"ok": True, "stopped_count": len(tasks)}
