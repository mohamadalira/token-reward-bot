import asyncio
import logging
from typing import Optional

from aiogram import Bot
from aiogram.types import FSInputFile, InputMediaPhoto, InputMediaVideo
from sqlalchemy.ext.asyncio import AsyncSession

from app.locales import get_i18n
from app.repositories import UserRepository

logger = logging.getLogger(__name__)
i18n = get_i18n()


class BroadcastService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.users = UserRepository(session)

    async def broadcast_text(
        self,
        bot: Bot,
        text: str,
        sponsors_only: bool = False,
        user_ids: Optional[list[int]] = None,
    ) -> tuple[int, int]:
        if user_ids:
            targets = user_ids
        else:
            targets = await self.users.get_all_ids(sponsors_only=sponsors_only)

        success = failed = 0
        for uid in targets:
            try:
                await bot.send_message(uid, text)
                success += 1
            except Exception:
                failed += 1
            await asyncio.sleep(0.05)
        return success, failed

    async def broadcast_media(
        self,
        bot: Bot,
        file_id: str,
        caption: Optional[str],
        media_type: str = "photo",
        sponsors_only: bool = False,
        user_ids: Optional[list[int]] = None,
    ) -> tuple[int, int]:
        if user_ids:
            targets = user_ids
        else:
            targets = await self.users.get_all_ids(sponsors_only=sponsors_only)

        success = failed = 0
        for uid in targets:
            try:
                if media_type == "photo":
                    await bot.send_photo(uid, file_id, caption=caption)
                elif media_type == "video":
                    await bot.send_video(uid, file_id, caption=caption)
                else:
                    await bot.send_document(uid, file_id, caption=caption)
                success += 1
            except Exception:
                failed += 1
            await asyncio.sleep(0.05)
        return success, failed
