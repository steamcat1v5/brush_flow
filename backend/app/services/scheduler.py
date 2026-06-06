import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.database import async_session
from app.models.flow_log import FlowLog, FlowSummary
from app.models.settings_model import Setting
from app.models.task import Task
from app.models.link import Link
from app.services.download_engine import download_engine
from sqlalchemy import select, func

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


# ---- 单任务启停（被定时器调用）----

async def _start_single_task(task_type: str, task_id: int):
    """定时器回调：启动单个任务"""
    logger.info(f"定时启动任务: {task_type}#{task_id}")
    try:
        async with async_session() as session:
            if task_type == "download":
                task = await session.get(Task, task_id)
                if not task:
                    logger.warning(f"任务不存在: download#{task_id}")
                    return
                if task.status not in ("pending", "stopped", "failed"):
                    logger.info(f"任务状态为 {task.status}，跳过启动")
                    return
                link = await session.get(Link, task.link_id)
                if not link:
                    logger.warning(f"关联链接不存在: task#{task_id}")
                    return
                task.status = "running"
                task.started_at = datetime.now()
                await download_engine.start_download(
                    task_id=task.id,
                    url=link.url,
                    concurrency=task.concurrency,
                    target_bytes=task.target_bytes,
                    speed_limit=task.speed_limit,
                )

            elif task_type == "iptv":
                from app.models.iptv_task import IptvTask
                from app.models.iptv_channel import IptvChannel
                from app.services.iptv_engine import iptv_engine

                task = await session.get(IptvTask, task_id)
                if not task:
                    logger.warning(f"任务不存在: iptv#{task_id}")
                    return
                if task.status not in ("pending", "stopped", "failed"):
                    logger.info(f"任务状态为 {task.status}，跳过启动")
                    return
                ch = await session.get(IptvChannel, task.channel_id)
                if not ch:
                    logger.warning(f"关联频道不存在: iptv_task#{task_id}")
                    return
                task.status = "running"
                task.started_at = datetime.now()
                await iptv_engine.start_task(
                    task_id=task.id,
                    hls_url=ch.hls_url,
                    speed_limit=task.speed_limit,
                    target_bytes=task.target_bytes,
                    auto_switch_enabled=task.auto_switch_enabled,
                    auto_switch_interval=task.auto_switch_interval,
                    source_id=task.source_id,
                    current_channel_id=task.channel_id,
                    switch_mode=task.switch_mode,
                )

            await session.commit()
            logger.info(f"定时启动成功: {task_type}#{task_id}")
    except Exception as e:
        logger.error(f"定时启动任务失败: {task_type}#{task_id}: {e}")


async def _stop_single_task(task_type: str, task_id: int):
    """定时器回调：停止单个任务"""
    logger.info(f"定时停止任务: {task_type}#{task_id}")
    try:
        async with async_session() as session:
            if task_type == "download":
                task = await session.get(Task, task_id)
                if not task:
                    logger.warning(f"任务不存在: download#{task_id}")
                    return
                if task.status not in ("running", "paused"):
                    logger.info(f"任务状态为 {task.status}，跳过停止")
                    return
                dl_task = download_engine.get_task(task_id)
                if dl_task:
                    task.total_downloaded = dl_task.total_downloaded
                    await download_engine.stop_download(task_id)
                task.status = "stopped"
                task.stopped_at = datetime.now()

            elif task_type == "iptv":
                from app.models.iptv_task import IptvTask
                from app.services.iptv_engine import iptv_engine

                task = await session.get(IptvTask, task_id)
                if not task:
                    logger.warning(f"任务不存在: iptv#{task_id}")
                    return
                if task.status not in ("running", "paused"):
                    logger.info(f"任务状态为 {task.status}，跳过停止")
                    return
                runner = iptv_engine.get_runner(task_id)
                if runner:
                    task.total_downloaded = runner.total_downloaded
                    await iptv_engine.stop_task(task_id)
                task.status = "stopped"
                task.stopped_at = datetime.now()

            await session.commit()
            logger.info(f"定时停止成功: {task_type}#{task_id}")
    except Exception as e:
        logger.error(f"定时停止任务失败: {task_type}#{task_id}: {e}")


# ---- Cron Job 管理 ----

def _parse_cron_parts(cron_expr: str) -> dict | None:
    """解析 5 段式 cron 表达式，返回 APScheduler cron 参数字典"""
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        logger.error(f"无效的 cron 表达式: {cron_expr}")
        return None
    return {
        "minute": parts[0],
        "hour": parts[1],
        "day": parts[2],
        "month": parts[3],
        "day_of_week": parts[4],
    }


def remove_task_jobs(task_type: str, task_id: int):
    """移除某个任务的所有定时 job"""
    for suffix in ("start", "stop"):
        job_id = f"task_{task_type}_{task_id}_{suffix}"
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
            logger.info(f"已移除定时任务: {job_id}")


def schedule_task_jobs(task_type: str, task_id: int, auto_start_cron: str | None, auto_stop_cron: str | None):
    """为单个任务设置定时 job（先清除旧的再设置新的）"""
    remove_task_jobs(task_type, task_id)

    if auto_start_cron:
        parts = _parse_cron_parts(auto_start_cron)
        if parts:
            job_id = f"task_{task_type}_{task_id}_start"
            scheduler.add_job(
                _start_single_task,
                "cron",
                args=[task_type, task_id],
                id=job_id,
                **parts,
            )
            logger.info(f"已设置定时启动: {job_id} -> {auto_start_cron}")

    if auto_stop_cron:
        parts = _parse_cron_parts(auto_stop_cron)
        if parts:
            job_id = f"task_{task_type}_{task_id}_stop"
            scheduler.add_job(
                _stop_single_task,
                "cron",
                args=[task_type, task_id],
                id=job_id,
                **parts,
            )
            logger.info(f"已设置定时停止: {job_id} -> {auto_stop_cron}")


async def reload_all_task_schedulers():
    """启动时加载所有任务的定时配置"""
    logger.info("重新加载所有任务定时配置...")
    try:
        async with async_session() as session:
            # 下载任务
            stmt = select(Task).where(
                (Task.auto_start_cron.isnot(None)) | (Task.auto_stop_cron.isnot(None))
            )
            result = await session.execute(stmt)
            tasks = result.scalars().all()
            for task in tasks:
                schedule_task_jobs("download", task.id, task.auto_start_cron, task.auto_stop_cron)

            # IPTV 任务
            from app.models.iptv_task import IptvTask
            iptv_stmt = select(IptvTask).where(
                (IptvTask.auto_start_cron.isnot(None)) | (IptvTask.auto_stop_cron.isnot(None))
            )
            iptv_result = await session.execute(iptv_stmt)
            iptv_tasks = iptv_result.scalars().all()
            for task in iptv_tasks:
                schedule_task_jobs("iptv", task.id, task.auto_start_cron, task.auto_stop_cron)

            logger.info(f"已加载 {len(tasks)} 个下载任务定时，{len(iptv_tasks)} 个 IPTV 任务定时")
    except Exception as e:
        logger.error(f"加载任务定时配置失败: {e}")


# ---- 流量日报和熔断（保留）----

async def generate_daily_summary():
    """生成昨日流量日报"""
    yesterday = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    from datetime import timedelta
    day_start = yesterday - timedelta(days=1)
    day_end = yesterday
    period_key = day_start.strftime("%Y-%m-%d")

    try:
        async with async_session() as session:
            stmt = select(
                func.sum(FlowLog.bytes_down),
                func.count(FlowLog.task_id.distinct()),
            ).where(
                FlowLog.logged_at >= day_start,
                FlowLog.logged_at < day_end,
            )
            result = await session.execute(stmt)
            row = result.one()
            total_bytes = row[0] or 0
            task_count = row[1] or 0

            speed_stmt = select(
                func.sum(FlowLog.bytes_down)
            ).where(
                FlowLog.logged_at >= day_start,
                FlowLog.logged_at < day_end,
            ).group_by(FlowLog.logged_at)

            speed_result = await session.execute(speed_stmt)
            minute_totals = [r[0] for r in speed_result.all()]
            avg_speed = int(sum(minute_totals) / len(minute_totals)) if minute_totals else 0
            peak_speed = max(minute_totals) if minute_totals else 0

            existing = select(FlowSummary).where(
                FlowSummary.period_type == "day",
                FlowSummary.period_key == period_key,
            )
            existing_result = await session.execute(existing)
            if existing_result.scalar_one_or_none():
                return

            summary = FlowSummary(
                period_type="day",
                period_key=period_key,
                total_bytes=total_bytes,
                task_count=task_count,
                avg_speed=avg_speed,
                peak_speed=peak_speed,
            )
            session.add(summary)
            await session.commit()
            logger.info(f"日报生成完成: {period_key}, 总流量: {total_bytes}")
    except Exception as e:
        logger.error(f"生成日报失败: {e}")


async def check_daily_target():
    """检查今日流量是否达到目标，若达到则停止所有任务"""
    try:
        async with async_session() as session:
            stmt = select(Setting).where(Setting.key == "daily_traffic_target_gb")
            result = await session.execute(stmt)
            setting = result.scalar_one_or_none()

            if not setting or setting.value == "0":
                return

            target_gb = float(setting.value)
            from app.services.flow_tracker import flow_tracker
            stats = await flow_tracker.get_today_stats()
            current_gb = stats["total_bytes"] / (1024 ** 3)

            if current_gb >= target_gb:
                logger.info(f"今日流量已达标 ({current_gb:.2f}GB / {target_gb:.2f}GB)，正在停止任务...")
                await download_engine.stop_all()

                task_stmt = select(Task).where(Task.status == "running")
                result = await session.execute(task_stmt)
                tasks = result.scalars().all()
                for task in tasks:
                    task.status = "stopped"
                    task.stopped_at = datetime.now()

                from app.models.iptv_task import IptvTask
                from app.services.iptv_engine import iptv_engine
                await iptv_engine.stop_all()
                iptv_stmt = select(IptvTask).where(IptvTask.status.in_(["running", "paused"]))
                iptv_result = await session.execute(iptv_stmt)
                iptv_tasks = iptv_result.scalars().all()
                for iptv_task in iptv_tasks:
                    iptv_task.status = "stopped"
                    iptv_task.stopped_at = datetime.now()

                await session.commit()
                logger.info(f"已停止 {len(tasks)} 个下载任务，{len(iptv_tasks)} 个 IPTV 任务")
    except Exception as e:
        logger.error(f"检查今日目标失败: {e}")


def setup_scheduler():
    """配置定时任务"""
    scheduler.add_job(generate_daily_summary, "cron", hour=0, minute=5, id="daily_summary")
    scheduler.add_job(check_daily_target, "interval", minutes=1, id="check_target")
    scheduler.add_job(reload_all_task_schedulers, id="initial_reload")
    logger.info("定时任务已配置")
