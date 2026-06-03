import logging
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

logger = logging.getLogger(__name__)


async def channel_is_accessible(bot: Bot, channel_id: str) -> bool:
    """True if the bot can resolve the channel (exists and bot has access)."""
    try:
        await bot.get_chat(channel_id)
        return True
    except TelegramBadRequest as e:
        logger.warning("Channel not accessible %s: %s", channel_id, e)
        return False


async def check_channel_membership(
    bot: Bot, user_id: int, channel_id: str
) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except TelegramBadRequest as e:
        logger.warning("Membership check failed for %s in %s: %s", user_id, channel_id, e)
        return False


async def validate_bot_channel_admin(
    bot: Bot, channel_id: str
) -> tuple[bool, Optional[str]]:
    try:
        me = await bot.get_me()
        member = await bot.get_chat_member(chat_id=channel_id, user_id=me.id)
        if member.status not in ("administrator", "creator"):
            return False, "ربات ادمین کانال نیست"
        if not getattr(member, "can_invite_users", False):
            return False, "دسترسی دعوت کاربر نداره"
        return True, None
    except TelegramBadRequest as e:
        return False, str(e.message)
