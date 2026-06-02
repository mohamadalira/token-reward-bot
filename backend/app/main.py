import asyncio
import logging
import sys

import uvicorn
from aiogram import Bot

from app.api.app import create_api_app
from app.bot.setup import create_bot
from app.core.config import get_settings
from app.core.database import async_session_factory, init_db
from app.core.redis_client import close_redis
from app.repositories import SettingsRepository, UserRepository

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)
settings = get_settings()


async def setup_defaults():
    from aiogram import Bot

    bot = Bot(token=settings.bot_token)
    me = await bot.get_me()
    await bot.session.close()

    async with async_session_factory() as session:
        settings_repo = SettingsRepository(session)
        await settings_repo.init_defaults()
        await settings_repo.set("bot_username", me.username or "")
        user_repo = UserRepository(session)
        for admin_id in settings.admin_id_list:
            user, _ = await user_repo.get_or_create(
                user_id=admin_id,
                is_admin=True,
            )
            user.is_admin = True
        await session.commit()
    logger.info("Default settings and admins initialized")


async def run_bot(bot: Bot, dp):
    # Webhook blocks polling — clear it (common after BotFather / other panels)
    await bot.delete_webhook(drop_pending_updates=True)
    me = await bot.get_me()
    logger.info("Telegram bot @%s (id=%s) — polling started", me.username, me.id)
    await dp.start_polling(bot, handle_signals=False)


async def main():
    await init_db()
    await setup_defaults()

    bot, dp = create_bot()
    api_app = create_api_app()

    config = uvicorn.Config(
        api_app,
        host=settings.api_host,
        port=settings.api_port,
        log_level=settings.log_level.lower(),
    )
    server = uvicorn.Server(config)

    await asyncio.gather(
        run_bot(bot, dp),
        server.serve(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        asyncio.run(close_redis())
