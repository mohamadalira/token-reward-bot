import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import ErrorEvent

from app.bot.handlers.admin.panel import router as admin_router
from app.bot.handlers.sponsor.panel import router as sponsor_router
from app.bot.handlers.user.start import router as user_router
from app.bot.middlewares.base import AntiSpamMiddleware, DatabaseMiddleware, RateLimitMiddleware
from app.core.config import get_settings

logger = logging.getLogger(__name__)


def create_bot() -> tuple[Bot, Dispatcher]:
    settings = get_settings()
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    storage = RedisStorage.from_url(settings.redis_url)
    dp = Dispatcher(storage=storage)

    dp.message.middleware(DatabaseMiddleware())
    dp.callback_query.middleware(DatabaseMiddleware())
    dp.message.middleware(AntiSpamMiddleware())
    dp.message.middleware(RateLimitMiddleware())

    dp.include_router(admin_router)
    dp.include_router(sponsor_router)
    dp.include_router(user_router)

    @dp.errors()
    async def on_error(event: ErrorEvent):
        logger.exception(
            "Handler error update=%s: %s",
            getattr(event.update, "update_id", "?"),
            event.exception,
        )

    return bot, dp
