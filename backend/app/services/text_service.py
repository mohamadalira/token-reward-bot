"""Load bot UI texts from DB (settings) with fa.py defaults."""

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.locales import fa
from app.repositories import SettingsRepository


class TextService:
    """All user-facing strings — DB first, then fa.MESSAGES fallback."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self._repo = SettingsRepository(session)

    async def t(self, key: str, default: Optional[str] = None, **kwargs: Any) -> str:
        fallback = default if default is not None else fa.MESSAGES.get(key, key)
        template = await self._repo.get(key, fallback)
        if kwargs:
            try:
                return template.format(**kwargs)
            except (KeyError, ValueError):
                return template
        return template

    async def set(self, key: str, value: str) -> None:
        await self._repo.set(key, value)

    async def reset(self, key: str) -> None:
        default = fa.MESSAGES.get(key, "")
        await self._repo.set(key, default)

    @staticmethod
    def text_keys() -> list[str]:
        return sorted(fa.MESSAGES.keys())
