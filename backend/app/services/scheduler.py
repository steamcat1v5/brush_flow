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


async def auto_start_tasks():
    """定时自动启动所有任务"""
    logger.info("触发定时自动启动...")
    try:
        async with async_session() as session:
            # 启动下载任务
            stmt = select(Task).where(Task.status.in_(["pending", "stopped", "failed"]))
            result = await session.execute(stmt)
            tasks = result.scalars().all()
            for task in tasks:
                link_stmt = select(Link).where(Link.id == task.link_id)
                link_result = await session.execute(link_stmt)
                link = link_result.scalar_one_or_none()
                if not link:
                    continue

                task.status = "running"
                task.started_at = datetime.now()
                await download_engine.start_download(
                    task_id=task.id,
                    url=link.url,
                    concurrency=task.concurrency,
                    target_bytes=task.target_bytes,
                    speed_limit=task.speed_limit,
                )

            # 启动 IPTV 任务
            from app.models.iptv_task import IptvTask
            from app.models.iptv_channel import IptvChannel
            from app.services.iptv_engine import iptv_engine

            iptv_stmt = select(IptvTask).where(IptvTask.status.in_(["pending", "stopped", "failed"]))
            iptv_result = await session.execute(iptv_stmt)
            iptv_tasks = iptv_result.scalars().all()
            for iptv_task in iptv_tasks:
                ch = await session.get(IptvChannel, iptv_task.channel_id)
                if not ch:
                    continue

                iptv_task.status = "running"
                iptv_task.started_at = datetime.now()
                await iptv_engine.start_task(
                    task_id=iptv_task.id,
                    hls_url=ch.hls_url,
                    speed_limit=iptv_task.speed_limit,
                    target_bytes=iptv_task.target_bytes,
                    auto_switch_enabled=iptv_task.auto_switch_enabled,
                    auto_switch_interval=iptv_task.auto_switch_interval,
                    source_id=iptv_task.source_id,
                    current_channel_id=iptv_task.channel_id,
                    switch_mode=iptv_task.switch_mode,
                )

            await session.commit()
            logger.info(f"已自动启动 {len(tasks)} 个下载任务，{len(iptv_tasks)} 个 IPTV 任务")
    except Exception as e:
        logger.error(f"自动启动任务失败: {e}")


async def auto_stop_tasks():
    """定时自动停止所有任务"""
    logger.info("触发定时自动停止...")
    try:
        async with async_session() as session:
            # 停止下载任务
            await download_engine.stop_all()
            stmt = select(Task).where(Task.status == "running")
            result = await session.execute(stmt)
            tasks = result.scalars().all()
            for task in tasks:
                task.status = "stopped"
                task.stopped_at = datetime.now()

            # 停止 IPTV 任务
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
            logger.info(f"已自动停止 {len(tasks)} 个下载任务，{len(iptv_tasks)} 个 IPTV 任务")
    except Exception as e:
        logger.error(f"自动停止任务失败: {e}")


async def reload_scheduler_settings():
    """重新加载定时任务配置"""
    logger.info("重新加载定时配置...")
    try:
        async with async_session() as session:
            stmt = select(Setting)
            result = await session.execute(stmt)
            rows = result.scalars().all()
            settings_dict = {row.key: row.value for row in rows}

            # 移除旧任务
            for job_id in ["auto_start", "auto_stop"]:
                if scheduler.get_job(job_id):
                    scheduler.remove_job(job_id)

            if settings_dict.get("auto_start_enabled") == "true":
                cron_start = settings_dict.get("auto_start_cron", "0 0 * * *")
                try:
                    # 解析简单 cron: "分 时 日 月 周"
                    parts = cron_start.split()
                    if len(parts) == 5:
                        scheduler.add_job(
                            auto_start_tasks,
                            "cron",
                            minute=parts[0],
                            hour=parts[1],
                            day=parts[2],
                            month=parts[3],
                            day_of_week=parts[4],
                            id="auto_start"
                        )
                        logger.info(f"已设置自动启动: {cron_start}")
                except Exception as e:
                    logger.error(f"解析启动 cron 失败: {e}")

            if settings_dict.get("auto_stop_cron"):
                cron_stop = settings_dict.get("auto_stop_cron", "0 8 * * *")
                try:
                    parts = cron_stop.split()
                    if len(parts) == 5:
                        scheduler.add_job(
                            auto_stop_tasks,
                            "cron",
                            minute=parts[0],
                            hour=parts[1],
                            day=parts[2],
                            month=parts[3],
                            day_of_week=parts[4],
                            id="auto_stop"
                        )
                        logger.info(f"已设置自动停止: {cron_stop}")
                except Exception as e:
                    logger.error(f"解析停止 cron 失败: {e}")
    except Exception as e:
        logger.error(f"重新加载配置失败: {e}")


async def generate_daily_summary():
    """生成昨日流量日报"""
    yesterday = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    from datetime import timedelta
    day_start = yesterday - timedelta(days=1)
    day_end = yesterday
    period_key = day_start.strftime("%Y-%m-%d")

    try:
        async with async_session() as session:
            # 汇总昨日数据
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

            # 计算平均速度和峰值速度
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

            # 写入汇总
            existing = select(FlowSummary).where(
                FlowSummary.period_type == "day",
                FlowSummary.period_key == period_key,
            )
            existing_result = await session.execute(existing)
            if existing_result.scalar_one_or_none():
                return  # 已存在

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
                await auto_stop_tasks()
    except Exception as e:
        logger.error(f"检查今日目标失败: {e}")


def setup_scheduler():
    """配置定时任务"""
    scheduler.add_job(generate_daily_summary, "cron", hour=0, minute=5, id="daily_summary")
    # 每分钟检查一次流量目标
    scheduler.add_job(check_daily_target, "interval", minutes=1, id="check_target")
    # 异步添加初始加载任务
    scheduler.add_job(reload_scheduler_settings, id="initial_reload")
    logger.info("定时任务已配置")
