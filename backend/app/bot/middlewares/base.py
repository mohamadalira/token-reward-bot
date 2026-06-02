from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.core.security import RateLimiter, check_spam
from app.locales import get_i18n


class DatabaseMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        async with async_session_factory() as session:
            data["session"] = session
            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise


class AntiSpamMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user: User | None = data.get("event_from_user")
        if user:
            if await check_spam(user.id):
                i18n = get_i18n()
                from aiogram.types import Message
                if isinstance(event, Message):
                    await event.answer(i18n.t("rate_limited"))
                return None
        return await handler(event, data)


class RateLimitMiddleware(BaseMiddleware):
    def __init__(self):
        self.limiter = RateLimiter(max_requests=30, window_seconds=60)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user: User | None = data.get("event_from_user")
        if user and not await self.limiter.is_allowed(user.id):
            i18n = get_i18n()
            from aiogram.types import Message
            if isinstance(event, Message):
                await event.answer(i18n.t("rate_limited"))
            return None
        return await handler(event, data)
