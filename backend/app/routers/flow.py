from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.flow_log import FlowLog, FlowSummary
from app.models.task import Task
from app.models.task_log import TaskLog
from app.schemas.flow import FlowLogOut, FlowSummaryOut, TodayStats
from app.services.flow_tracker import flow_tracker

router = APIRouter(prefix="/api/flow", tags=["flow"])


@router.get("/today", response_model=TodayStats)
async def get_today_stats(db: AsyncSession = Depends(get_db)):
    stats = await flow_tracker.get_today_stats()

    # 活跃任务数
    active_stmt = select(func.count(Task.id)).where(Task.status == "running")
    active_result = await db.execute(active_stmt)
    active_tasks = active_result.scalar() or 0

    return TodayStats(
        total_bytes=stats["total_bytes"],
        current_speed=stats["current_speed"],
        active_tasks=active_tasks,
        uptime_seconds=0,
    )


@router.get("/summary", response_model=list[FlowSummaryOut])
async def get_flow_summary(
    period: str = "day",
    limit: int = 30,
    db: AsyncSession = Depends(get_db),
):
    if period == "week":
        # 按周：从 flow_logs 按自然周聚合
        stmt = select(
            func.strftime("%Y-W%W", FlowLog.logged_at).label("period_key"),
            func.sum(FlowLog.bytes_down).label("total_bytes"),
        ).group_by(
            func.strftime("%Y-W%W", FlowLog.logged_at)
        ).order_by(
            func.strftime("%Y-W%W", FlowLog.logged_at).desc()
        ).limit(limit)
        result = await db.execute(stmt)
        rows = result.all()
        return [
            FlowSummaryOut(period_type="week", period_key=r.period_key, total_bytes=r.total_bytes or 0,
                           task_count=0, avg_speed=0, peak_speed=0)
            for r in rows
        ]

    if period == "month":
        # 按月：从 flow_logs 按自然月聚合
        stmt = select(
            func.strftime("%Y-%m", FlowLog.logged_at).label("period_key"),
            func.sum(FlowLog.bytes_down).label("total_bytes"),
        ).group_by(
            func.strftime("%Y-%m", FlowLog.logged_at)
        ).order_by(
            func.strftime("%Y-%m", FlowLog.logged_at).desc()
        ).limit(limit)
        result = await db.execute(stmt)
        rows = result.all()
        return [
            FlowSummaryOut(period_type="month", period_key=r.period_key, total_bytes=r.total_bytes or 0,
                           task_count=0, avg_speed=0, peak_speed=0)
            for r in rows
        ]

    # 按日：优先查 flow_summaries 表（已预聚合的历史数据）
    stmt = (
        select(FlowSummary)
        .where(FlowSummary.period_type == period)
        .order_by(FlowSummary.period_key.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    summaries = list(result.scalars().all())

    # 如果列表里没有今天的数据，则实时计算并插入
    if len(summaries) < limit:
        today_str = datetime.now().strftime("%Y-%m-%d")
        if not summaries or summaries[0].period_key != today_str:
            stats = await flow_tracker.get_today_stats()
            today_summary = FlowSummaryOut(
                period_type="day",
                period_key=today_str,
                total_bytes=stats["total_bytes"],
                task_count=0,
                avg_speed=stats["current_speed"],
                peak_speed=0
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
    return result.scalars().all()
