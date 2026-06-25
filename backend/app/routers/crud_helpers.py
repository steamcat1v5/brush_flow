"""通用 CRUD 辅助函数，消除路由中的重复模式。"""

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession


async def get_or_404(
    db: AsyncSession,
    model,
    entity_id: int,
    msg: str = "资源不存在",
):
    """获取实体，不存在则抛 404。"""
    entity = await db.get(model, entity_id)
    if not entity:
        raise HTTPException(404, msg)
    return entity


async def partial_update(
    db: AsyncSession,
    entity,
    data,
):
    """通用 partial-update：将 Pydantic schema 中 exclude_unset 的字段写入实体。"""
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(entity, key, value)
    await db.commit()
    await db.refresh(entity)
    return entity


async def delete_entity(
    db: AsyncSession,
    entity,
):
    """通用删除实体并提交。"""
    await db.delete(entity)
    await db.commit()
    return {"ok": True}
