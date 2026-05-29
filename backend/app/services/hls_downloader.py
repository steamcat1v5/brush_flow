import asyncio
import logging
from typing import Callable
from urllib.parse import urljoin

import aiohttp

from app.config import settings
from app.utils.limiter import TokenBucket

logger = logging.getLogger(__name__)


class HlsDownloader:
    """HLS 协议辅助类：解析播放列表、下载分片。"""

    async def resolve_stream_url(self, session: aiohttp.ClientSession, url: str) -> str:
        """获取 master m3u8，返回最高带宽变体 URL。
        若已是变体播放列表则直接返回。"""
        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    raise Exception(f"HTTP {resp.status} 获取 m3u8 失败")
                content = await resp.text()
                logger.debug(f"m3u8 响应 ({len(content)} bytes): {content[:200]}")
        except Exception as e:
            logger.error(f"解析流地址失败: {e}")
            raise

        # 如果包含 #EXT-X-STREAM-INF，说明是 master playlist
        if "#EXT-X-STREAM-INF" in content:
            best_bandwidth = 0
            best_url = ""
            lines = content.strip().splitlines()
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                if line.startswith("#EXT-X-STREAM-INF"):
                    # 提取 BANDWIDTH
                    bw = 0
                    m_tokens = [t.strip() for t in line.split(",")]
                    for token in m_tokens:
                        if token.startswith("BANDWIDTH="):
                            try:
                                bw = int(token.split("=", 1)[1])
                            except ValueError:
                                pass
                    # 下一行是变体 URL
                    i += 1
                    while i < len(lines) and not lines[i].strip():
                        i += 1
                    if i < len(lines):
                        variant_line = lines[i].strip()
                        if variant_line and not variant_line.startswith("#"):
                            if bw > best_bandwidth:
                                best_bandwidth = bw
                                best_url = urljoin(url, variant_line) if not variant_line.startswith("http") else variant_line
                i += 1

            if best_url:
                return best_url

        # 已经是变体播放列表，直接返回
        return url

    async def fetch_segment_list(self, session: aiohttp.ClientSession,
                                  variant_url: str) -> list[str]:
        """获取变体 m3u8，返回 .ts 分片 URL 列表。"""
        try:
            async with session.get(variant_url) as resp:
                if resp.status != 200:
                    raise Exception(f"HTTP {resp.status} 获取变体播放列表失败")
                content = await resp.text()
                logger.debug(f"变体 m3u8 响应 ({len(content)} bytes): {content[:200]}")
        except Exception as e:
            logger.error(f"获取分片列表失败: {e}")
            return []

        segments: list[str] = []
        lines = content.strip().splitlines()
        for i, line in enumerate(lines):
            line = line.strip()
            if line and not line.startswith("#"):
                # 这是分片 URL（非注释行）
                if line.startswith("http"):
                    segments.append(line)
                else:
                    # 相对路径，基于变体 URL 解析
                    segments.append(urljoin(variant_url, line))
            elif line.startswith("#EXT-X-ENDLIST"):
                # 点播流结束标志
                break

        return segments

    async def download_segment(
        self,
        session: aiohttp.ClientSession,
        segment_url: str,
        flow_callback: Callable[[int], None],
        limiter: TokenBucket | None = None,
        global_limiter: TokenBucket | None = None,
        stop_event: asyncio.Event | None = None,
    ) -> int:
        """下载单个 .ts 分片，流式读取并丢弃，返回下载字节数。"""
        total = 0
        try:
            async with session.get(segment_url) as resp:
                if resp.status not in (200, 206):
                    logger.warning(f"分片下载 HTTP {resp.status}: {segment_url[:80]}")
                    raise Exception(f"HTTP {resp.status} 下载分片失败")

                async for chunk in resp.content.iter_chunked(settings.chunk_size):
                    if stop_event and stop_event.is_set():
                        break

                    chunk_size = len(chunk)
                    total += chunk_size
                    flow_callback(chunk_size)

                    # 任务限速
                    if limiter:
                        await limiter.consume(chunk_size)
                    # 全局限速
                    if global_limiter:
                        await global_limiter.consume(chunk_size)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(f"下载分片出错 {segment_url}: {e}")

        return total


hls_downloader = HlsDownloader()
