"""CLI 验证工具：直接运行下载并显示实时速度"""

import argparse
import asyncio
import signal
import sys

from app.services.download_engine import DownloadEngine
from app.services.flow_tracker import FlowTracker
from app.utils.humanize import format_bytes, format_speed


async def run(url: str, concurrency: int, target_mb: int):
    tracker = FlowTracker()
    engine = DownloadEngine()

    target_bytes = target_mb * 1024 * 1024 if target_mb > 0 else 0
    task_id = 1

    print(f"开始下载: {url}")
    print(f"并发数: {concurrency}, 目标: {'无限' if target_bytes == 0 else format_bytes(target_bytes)}")
    print("-" * 60)

    await engine.start_download(task_id, url, concurrency, target_bytes)

    try:
        while True:
            await asyncio.sleep(1)
            dl_task = engine.get_task(task_id)
            if not dl_task:
                break

            speed = tracker.get_speed(task_id)
            total = dl_task.total_downloaded
            status = dl_task.status

            pct = ""
            if target_bytes > 0:
                pct = f" ({total * 100 / target_bytes:.1f}%)"

            sys.stdout.write(
                f"\r状态: {status} | 已下载: {format_bytes(total)}{pct} | "
                f"速度: {format_speed(speed)}       "
            )
            sys.stdout.flush()

            if status in ("completed", "failed", "stopped"):
                break
    except KeyboardInterrupt:
        print("\n正在停止...")
        await engine.stop_download(task_id)

    print(f"\n最终下载量: {format_bytes(dl_task.total_downloaded)}")


def main():
    parser = argparse.ArgumentParser(description="BrushFlow CLI 验证工具")
    parser.add_argument("--url", required=True, help="下载 URL")
    parser.add_argument("--concurrency", type=int, default=5, help="并发数 (默认 5)")
    parser.add_argument("--target-mb", type=int, default=0, help="目标下载量 MB (0=无限)")
    args = parser.parse_args()

    asyncio.run(run(args.url, args.concurrency, args.target_mb))


if __name__ == "__main__":
    main()
