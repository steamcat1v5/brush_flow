import logging

from sqlalchemy import select

from app.database import async_session
from app.models.link import Link

logger = logging.getLogger(__name__)

# 经过手动验证的长期有效、高带宽链接
BUILTIN_RESOURCES = [
    {
        "name": "Ubuntu 26.04 ISO (官方镜像)",
        "url": "https://releases.ubuntu.com/26.04/ubuntu-26.04-desktop-amd64.iso",
        "file_size": 0, # 动态获取
        "category": "mirror",
    },
    {
        "name": "Ubuntu 24.04.1 ISO (阿里云)",
        "url": "https://mirrors.aliyun.com/ubuntu-releases/24.04/ubuntu-24.04.1-desktop-amd64.iso",
        "file_size": 5267128320,
        "category": "mirror",
    },
    {
        "name": "CentOS 7.9 ISO (阿里云)",
        "url": "https://mirrors.aliyun.com/centos/7.9.2009/isos/x86_64/CentOS-7-x86_64-DVD-2009.iso",
        "file_size": 4712300544,
        "category": "mirror",
    },
    {
        "name": "Debian 12.7 DVD (163镜像)",
        "url": "https://mirrors.163.com/debian-cd/12.7.0/amd64/iso-dvd/debian-12.7.0-amd64-DVD-1.iso",
        "file_size": 4011851776,
        "category": "mirror",
    },
    {
        "name": "Python 3.12.5 Windows 安装包",
        "url": "https://www.python.org/ftp/python/3.12.5/python-3.12.5-amd64.exe",
        "file_size": 26565416,
        "category": "software",
    },
]


async def seed_builtin_links():
    """将内置资源注册到数据库（跳过已存在的）"""
    async with async_session() as session:
        for res in BUILTIN_RESOURCES:
            stmt = select(Link).where(Link.url == res["url"])
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            if not existing:
                link = Link(
                    name=res["name"],
                    url=res["url"],
                    file_size=res["file_size"],
                    is_builtin=True,
                    category=res["category"],
                )
                session.add(link)
                logger.info(f"注册内置资源: {res['name']}")
            else:
                # 更新可能失效的旧内置链接名称或大小
                existing.name = res["name"]
                existing.file_size = res["file_size"]

        await session.commit()
    logger.info("内置资源同步完成")
