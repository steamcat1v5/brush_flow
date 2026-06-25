from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.link import Link
from app.schemas.link import LinkCreate, LinkOut, LinkUpdate, LinkVerifyResult
from app.utils.validators import verify_url
from app.routers.crud_helpers import get_or_404, partial_update, delete_entity

router = APIRouter(prefix="/api/links", tags=["links"])


@router.get("", response_model=list[LinkOut])
async def list_links(
    category: str | None = None,
    active: bool | None = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Link)
    if category:
        stmt = stmt.where(Link.category == category)
    if active is not None:
        stmt = stmt.where(Link.is_active == active)
    stmt = stmt.order_by(Link.id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("", response_model=LinkOut)
async def create_link(data: LinkCreate, db: AsyncSession = Depends(get_db)):
    # 检查 URL 是否已存在
    existing = await db.execute(select(Link).where(Link.url == data.url))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "URL 已存在")

    link = Link(name=data.name, url=data.url, file_size=data.file_size, category=data.category)
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return link


@router.put("/{link_id}", response_model=LinkOut)
async def update_link(link_id: int, data: LinkUpdate, db: AsyncSession = Depends(get_db)):
    link = await get_or_404(db, Link, link_id, "链接不存在")
    return await partial_update(db, link, data)


@router.delete("/{link_id}")
async def delete_link(link_id: int, db: AsyncSession = Depends(get_db)):
    link = await get_or_404(db, Link, link_id, "链接不存在")
    return await delete_entity(db, link)


@router.post("/{link_id}/verify", response_model=LinkVerifyResult)
async def verify_link(link_id: int, db: AsyncSession = Depends(get_db)):
    link = await get_or_404(db, Link, link_id, "链接不存在")

    result = await verify_url(link.url)
    if result["reachable"] and result["file_size"] > 0:
        link.file_size = result["file_size"]
        await db.commit()
    return LinkVerifyResult(**result)
