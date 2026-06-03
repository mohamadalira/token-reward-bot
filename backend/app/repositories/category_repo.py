import re
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import ConfigProduct, ShopCategory


def slugify(name: str) -> str:
    s = name.strip().lower().replace(" ", "-")
    s = re.sub(r"[^a-z0-9\u0600-\u06ff\-]", "", s)
    return s or "category"


class CategoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_active(self) -> list[ShopCategory]:
        result = await self.session.execute(
            select(ShopCategory)
            .where(ShopCategory.is_active == True)
            .order_by(ShopCategory.sort_order, ShopCategory.id)
        )
        return list(result.scalars().all())

    async def list_all(self) -> list[ShopCategory]:
        result = await self.session.execute(
            select(ShopCategory).order_by(ShopCategory.sort_order, ShopCategory.id)
        )
        return list(result.scalars().all())

    async def get_by_id(self, category_id: int) -> Optional[ShopCategory]:
        result = await self.session.execute(
            select(ShopCategory).where(ShopCategory.id == category_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        name: str,
        description: Optional[str] = None,
        default_token_cost: int = 0,
        sort_order: int = 0,
    ) -> ShopCategory:
        base_slug = slugify(name)
        slug = base_slug
        n = 1
        while await self.get_by_slug(slug):
            slug = f"{base_slug}-{n}"
            n += 1
        cat = ShopCategory(
            name=name,
            slug=slug,
            description=description,
            default_token_cost=default_token_cost,
            sort_order=sort_order,
        )
        self.session.add(cat)
        await self.session.flush()
        return cat

    async def get_by_slug(self, slug: str) -> Optional[ShopCategory]:
        result = await self.session.execute(
            select(ShopCategory).where(ShopCategory.slug == slug)
        )
        return result.scalar_one_or_none()

    async def update(self, category_id: int, **kwargs) -> Optional[ShopCategory]:
        cat = await self.get_by_id(category_id)
        if not cat:
            return None
        for k, v in kwargs.items():
            if v is not None and hasattr(cat, k):
                setattr(cat, k, v)
        await self.session.flush()
        return cat

    async def delete(self, category_id: int) -> bool:
        cat = await self.get_by_id(category_id)
        if not cat:
            return False
        await self.session.delete(cat)
        return True

    async def get_products_by_category(
        self, category_id: int, active_only: bool = True
    ) -> list[ConfigProduct]:
        stmt = (
            select(ConfigProduct)
            .where(ConfigProduct.category_id == category_id)
            .options(selectinload(ConfigProduct.shop_category))
        )
        if active_only:
            stmt = stmt.where(ConfigProduct.is_active == True, ConfigProduct.stock > 0)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
