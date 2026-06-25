from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.flow_log import FlowLog, FlowSummary
from app.models.task import Task, TaskStatus
from app.models.iptv_task import IptvTask
from app.models.task_log import TaskLog
from app.schemas.flow import FlowLogOut, FlowSummaryOut, TodayStats
from app.services.flow_tracker import flow_tracker

router = APIRouter(prefix="/api/flow", tags=["flow"])


@router.get("/today", response_model=TodayStats)
async def get_today_stats(db: AsyncSession = Depends(get_db)):
    stats = await flow_tracker.get_today_stats()

    # 活跃任务数
    active_stmt = select(func.count(Task.id)).where(Task.status == TaskStatus.RUNNING.value)
    active_result = await db.execute(active_stmt)
    active_tasks = active_result.scalar() or 0

    iptv_active_stmt = select(func.count(IptvTask.id)).where(IptvTask.status == TaskStatus.RUNNING.value)
    iptv_active_result = await db.execute(iptv_active_stmt)
    iptv_active_tasks = iptv_active_result.scalar() or 0

    total_active_tasks = active_tasks + iptv_active_tasks

    return TodayStats(
        total_bytes=stats["total_bytes"],
        current_speed=stats["current_speed"],
        active_tasks=total_active_tasks,
        uptime_seconds=0,
    )


@router.get("/summary", response_model=list[FlowSummaryOut])
async def get_flow_summary(
    period: str = "day",
    limit: int = 30,
    db: AsyncSession = Depends(get_db),
):
    # 各时间维度对应的 strftime 格式
    period_formats: dict[str, str] = {
        "hour": "%Y-%m-%d %H:00",
        "day": "%Y-%m-%d",
        "week": "%Y-W%W",
        "month": "%Y-%m",
    }
    fmt = period_formats.get(period, "%Y-%m-%d")

    # 构建查询
    stmt = select(
        func.strftime(fmt, FlowLog.logged_at).label("period_key"),
        func.sum(FlowLog.bytes_down).label("total_bytes"),
        func.sum(FlowLog.bytes_down).filter(FlowLog.task_id < 100000).label("download_bytes"),
        func.sum(FlowLog.bytes_down).filter(FlowLog.task_id >= 100000).label("iptv_bytes"),
    )

    # day 模式增加日期范围过滤
    if period == "day":
        days_ago = datetime.now() - timedelta(days=limit)
        stmt = stmt.where(FlowLog.logged_at >= days_ago)

    stmt = stmt.group_by(
        func.strftime(fmt, FlowLog.logged_at)
    ).order_by(
        func.strftime(fmt, FlowLog.logged_at).desc()
    ).limit(limit)

    result = await db.execute(stmt)
    rows = result.all()
    summaries = [
        FlowSummaryOut(
            period_type=period, period_key=r.period_key,
            total_bytes=r.total_bytes or 0,
            download_bytes=r.download_bytes or 0, iptv_bytes=r.iptv_bytes or 0,
            task_count=0, avg_speed=0, peak_speed=0,
        )
        for r in rows
    ]

    # day 模式：如果列表里没有今天的数据，则实时计算并插入
    if period == "day" and len(summaries) < limit:
        today_str = datetime.now().strftime("%Y-%m-%d")
        if not summaries or summaries[0].period_key != today_str:
            stats = await flow_tracker.get_today_stats()
            today_summary = FlowSummaryOut(
                period_type="day",
                period_key=today_str,
                total_bytes=stats["total_bytes"],
                task_count=0,
                avg_speed=stats["current_speed"],
                peak_speed=0,
            )
            summaries.insert(0, today_summary)

    return summaries


@router.get("/details", response_model=list[FlowLogOut])
async def get_flow_details(
    task_id: int | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    limit: int = 1440,  # 一天的分钟数
    db: AsyncSession = Depends(get_db),
):
    stmt = select(FlowLog)
    if task_id:
        stmt = stmt.where(FlowLog.task_id == task_id)
    if from_date:
        stmt = stmt.where(FlowLog.logged_at >= from_date)
    if to_date:
        stmt = stmt.where(FlowLog.logged_at <= to_date)
    stmt = stmt.order_by(FlowLog.logged_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/realtime")
async def get_realtime():
    speeds = flow_tracker.get_all_speeds()
    return {
        "total_bytes_per_sec": flow_tracker.get_total_speed(),
        "tasks": [
            {"task_id": tid, "speed": spd}
            for tid, spd in speeds.items()
        ],
    }


@router.get("/logs")
async def get_task_logs(
    task_id: int | None = None,
    task_type: str | None = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(TaskLog)
    if task_id is not None:
        stmt = stmt.where(TaskLog.task_id == task_id)
    if task_type:
        stmt = stmt.where(TaskLog.task_type == task_type)
    stmt = stmt.order_by(TaskLog.id.desc()).limit(limit)
    result = await db.execute(stmt)
    logs = result.scalars().all()
    import calendar
    # SQLite CURRENT_TIMESTAMP 存储 UTC，用 timegm 按 UTC 转为 Unix 时间戳
    return [
        {
            "id": log.id,
            "task_id": log.task_id,
            "task_type": log.task_type,
            "level": log.level,
            "message": log.message,
            "created_at": calendar.timegm(log.created_at.timetuple()) if log.created_at else 0,
        }
        for log in logs
    ]
