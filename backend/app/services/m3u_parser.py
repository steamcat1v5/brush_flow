import re
from dataclasses import dataclass


@dataclass
class M3uChannel:
    name: str
    group_title: str
    hls_url: str


def parse_m3u(content: str) -> list[M3uChannel]:
    """解析 m3u 文本，返回频道列表。"""
    channels: list[M3uChannel] = []
    lines = content.strip().splitlines()
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        if line.startswith("#EXTINF:"):
            # 提取属性
            name = ""
            group_title = ""

            # tvg-name="..."
            m = re.search(r'tvg-name="([^"]*)"', line)
            if m:
                name = m.group(1)

            # group-title="..."
            m = re.search(r'group-title="([^"]*)"', line)
            if m:
                group_title = m.group(1)

            # 逗号后的显示名称优先于 tvg-name
            comma_idx = line.rfind(",")
            if comma_idx != -1:
                display_name = line[comma_idx + 1:].strip()
                if display_name:
                    name = display_name

            # 下一行是 URL
            i += 1
            while i < len(lines) and not lines[i].strip():
                i += 1
            if i < len(lines):
                url = lines[i].strip()
                if url and not url.startswith("#"):
                    channels.append(M3uChannel(
                        name=name or "Unknown",
                        group_title=group_title or "Other",
                        hls_url=url,
                    ))

        i += 1

    return channels
