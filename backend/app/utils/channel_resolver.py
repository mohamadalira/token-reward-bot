"""Resolve Telegram channel identifiers from user input."""

import logging
import re
from typing import Any, Optional

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

logger = logging.getLogger(__name__)

_TME_RE = re.compile(
    r"^(?:https?://)?(?:t\.me|telegram\.me)/(?:(\+[\w-]+)|@?([\w]+))/?$",
    re.I,
)


def normalize_channel_input(raw: str) -> str:
    return (raw or "").strip()


def _humanize_telegram_error(exc: Exception) -> str:
    msg = getattr(exc, "message", None) or str(exc)
    lower = msg.lower()
    if "chat not found" in lower:
        return (
            "کانال پیدا نشد.\n"
            "• لینک یا @username را درست بفرست\n"
            "• ربات را به کانال اضافه کن\n"
            "• برای کانال خصوصی لینک دعوت (+...) بفرست"
        )
    if "bot is not a member" in lower or "not a member" in lower:
        return "ربات هنوز عضو کانال نیست — اول ربات را به کانال اضافه کن."
    if "not enough rights" in lower or "administrator" in lower:
        return "ربات باید ادمین کانال باشد (با دسترسی دعوت کاربر)."
    if "invite link" in lower:
        return "لینک دعوت نامعتبر است — لینک تازه از تنظیمات کانال بگیر."
    return f"خطای تلگرام: {msg}"


async def resolve_channel_chat(bot: Bot, raw: str) -> tuple[bool, Optional[str], Optional[Any]]:
    """Return (ok, error_message, Chat object)."""
    text = normalize_channel_input(raw)
    if not text:
        return False, "لینک یا @username کانال را بفرست.", None

    chat_ref: str = text
    m = _TME_RE.match(text)
    if m:
        if m.group(1):
            chat_ref = f"https://t.me/{m.group(1)}"
        else:
            chat_ref = f"@{m.group(2)}"
    elif text.startswith("@"):
        chat_ref = text
    elif text.startswith("-100") or text.startswith("-"):
        chat_ref = text
    elif not text.startswith("http"):
        chat_ref = f"@{text.lstrip('@')}"

    try:
        chat = await bot.get_chat(chat_ref)
        return True, None, chat
    except TelegramBadRequest as e:
        logger.warning("resolve_channel_chat failed for %r: %s", raw, e)
        return False, _humanize_telegram_error(e), None
    except TelegramForbiddenError as e:
        return False, _humanize_telegram_error(e), None
    except Exception as e:
        logger.exception("resolve_channel_chat unexpected error")
        return False, _humanize_telegram_error(e), None


async def validate_channel_for_bot(
    bot: Bot, raw: str
) -> tuple[bool, Optional[str], Optional[dict[str, Any]]]:
    """
    Validate channel and bot permissions.
    Returns info dict: channel_id, title, username, invite_link
    """
    ok, err, chat = await resolve_channel_chat(bot, raw)
    if not ok or not chat:
        return False, err, None

    channel_id = str(chat.id)
    try:
        me = await bot.get_me()
        member = await bot.get_chat_member(chat_id=channel_id, user_id=me.id)
    except TelegramBadRequest as e:
        logger.warning("get_chat_member failed %s: %s", channel_id, e)
        return False, _humanize_telegram_error(e), None

    if member.status not in ("administrator", "creator"):
        return False, "ربات ادمین کانال نیست — در تنظیمات کانال ربات را ادمین کن.", None

    invite_link: Optional[str] = None
    if getattr(chat, "invite_link", None):
        invite_link = chat.invite_link
    elif chat.username:
        invite_link = f"https://t.me/{chat.username}"
    else:
        try:
            link = await bot.create_chat_invite_link(channel_id)
            invite_link = link.invite_link
        except TelegramBadRequest as e:
            return False, f"ربات نمی‌تواند لینک دعوت بسازد: {_humanize_telegram_error(e)}", None

    return True, None, {
        "channel_id": channel_id,
        "title": chat.title or channel_id,
        "username": chat.username,
        "invite_link": invite_link,
    }
