import logging

from sqlalchemy import select

from app.database import async_session
from app.models.link import Link

logger = logging.getLogger(__name__)

# 经过手动验证的高带宽 CDN 链接
BUILTIN_RESOURCES = [
    {
        "name": "278M 腾讯CDN (QQ)",
        "url": "https://qqdl.gtimg.cn/qqfile/QQNT/9.9.30/guanwang/6a035910/QQ_9.9.30-260511_x64_01.exe",
        "file_size": 291491840,
        "category": "software",
    },
    {
        "name": "240M 阿里CDN (学习强国)",
        "url": "https://wirelesscdn-download.xuexi.cn/publish/xuexi_android/latest/xuexi_android_10002068.apk",
        "file_size": 251658240,
        "category": "software",
    },
    {
        "name": "1000MB (浙江大学教育网)",
        "url": "http://speedtest.zju.edu.cn/1000M",
        "file_size": 1048576000,
        "category": "speedtest",
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
