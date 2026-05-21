from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.link import Link
from app.models.task import Task
from app.schemas.task import TaskCreate, TaskOut, TaskUpdate
from app.services.download_engine import download_engine
from app.services.flow_tracker import flow_tracker

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
        started_at=task.started_at,
        stopped_at=task.stopped_at,
        created_at=task.created_at,
        current_speed=speed,
    )


@router.get("", response_model=list[TaskOut])
async def list_tasks(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Task)
    if status:
        stmt = stmt.where(Task.status == status)
    stmt = stmt.order_by(Task.id.desc())
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
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
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

    link = await db.get(Link, task.link_id)
    if not link:
        raise HTTPException(404, "关联链接不存在")

    # ��果任务之前失败过，重置重试计数
    task.retry_count = 0
    task.status = "running"
    task.started_at = datetime.now()
    await db.commit()

    # 在引擎中启动
    await download_engine.start_download(
        task_id=task.id,
        url=link.url,
        concurrency=task.concurrency,
        target_bytes=task.target_bytes,
        speed_limit=task.speed_limit,
    )
    return {"ok": True, "message": "任务已启动"}


@router.post("/{task_id}/pause")
async def pause_task(task_id: int, db: AsyncSession = Depends(get_db)):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")

    await download_engine.pause_download(task_id)
    task.status = "paused"
    await db.commit()
    return {"ok": True, "message": "任务已暂停"}


@router.post("/{task_id}/resume")
async def resume_task(task_id: int, db: AsyncSession = Depends(get_db)):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")

    await download_engine.resume_download(task_id)
    task.status = "running"
    await db.commit()
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

    task.status = "stopped"
    task.stopped_at = datetime.now()
    await db.commit()
    return {"ok": True, "message": "任务已停止"}


@router.delete("/{task_id}")
async def delete_task(task_id: int, db: AsyncSession = Depends(get_db)):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "任务不存在")

    if task.status == "running":
        await download_engine.stop_download(task_id)

    await db.delete(task)
    await db.commit()
    return {"ok": True}


@router.post("/stop-all")
async def stop_all_tasks(db: AsyncSession = Depends(get_db)):
    """停止所有运行中的任务"""
    await download_engine.stop_all()

    stmt = select(Task).where(Task.status.in_(["running", "paused"]))
    result = await db.execute(stmt)
    tasks = result.scalars().all()
    for task in tasks:
        task.status = "stopped"
        task.stopped_at = datetime.now()
    await db.commit()
    return {"ok": True, "stopped_count": len(tasks)}
