"""Shared UI helpers for inline wizard navigation."""

from typing import Optional

from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message


def btn(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def kb(*rows: list[InlineKeyboardButton], back: Optional[str] = None) -> InlineKeyboardMarkup:
    layout = list(rows)
    if back:
        layout.append([btn("🔙 بازگشت", back)])
    return InlineKeyboardMarkup(inline_keyboard=layout)


async def edit_screen(
    callback: CallbackQuery,
    text: str,
    markup: Optional[InlineKeyboardMarkup] = None,
) -> None:
    try:
        await callback.message.edit_text(text, reply_markup=markup)
    except Exception:
        await callback.message.answer(text, reply_markup=markup)


async def answer_screen(
    message: Message,
    text: str,
    markup: Optional[InlineKeyboardMarkup] = None,
) -> Message:
    return await message.answer(text, reply_markup=markup)


def validate_card_number(number: str) -> tuple[bool, str]:
    digits = "".join(c for c in number if c.isdigit())
    if len(digits) != 16:
        return False, "شماره کارت باید دقیقاً ۱۶ رقم باشد."
    return True, digits
