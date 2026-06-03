"""Admin: payment gateway settings."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters.admin import AdminCallbackFilter, AdminFilter
from app.locales import get_i18n
from app.repositories import SettingsRepository
from app.services import PlisioService

router = Router(name="admin_payments")
router.message.filter(AdminFilter())
i18n = get_i18n()


class PaySettingsStates(StatesGroup):
    field = State()
    value = State()


router.callback_query.filter(AdminCallbackFilter())


@router.callback_query(F.data.startswith("adm_pay:toggle:"))
async def pay_toggle_cb(callback: CallbackQuery, session: AsyncSession):
    part = callback.data.split(":")[2]
    repo = SettingsRepository(session)
    key = "plisio_enabled" if part == "plisio" else "manual_card_enabled"
    cur = await repo.get_bool(key)
    await repo.set(key, "false" if cur else "true")
    await session.commit()
    await callback.answer(i18n.t("done"), show_alert=True)


@router.message(F.text == i18n.t("btn_payment_settings"))
async def payment_settings_menu(message: Message, session: AsyncSession):
    repo = SettingsRepository(session)
    lines = [
        "💳 مدیریت پرداخت‌ها\n",
        f"₿ Plisio: {'✅' if await repo.get_bool('plisio_enabled') else '❌'}",
        f"💳 کارت: {'✅' if await repo.get_bool('manual_card_enabled') else '❌'}",
        f"💵 قیمت توکن: ${await repo.get('token_price_usd')}",
        f"📉 حداقل خرید: {await repo.get('min_token_purchase')} توکن",
        f"📈 حداکثر خرید: {await repo.get('max_token_purchase')} توکن",
        "",
        "دستورات:",
        "/pay_toggle plisio|manual",
        "/pay_set کلید مقدار",
        "/pay_test — تست Plisio",
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="₿ Plisio on/off", callback_data="adm_pay:toggle:plisio")],
        [InlineKeyboardButton(text="💳 کارت on/off", callback_data="adm_pay:toggle:manual")],
    ])
    await message.answer("\n".join(lines), reply_markup=kb)


@router.message(F.text.startswith("/pay_toggle"))
async def pay_toggle(message: Message, session: AsyncSession):
    part = message.text.split()[1].lower()
    repo = SettingsRepository(session)
    key = "plisio_enabled" if part == "plisio" else "manual_card_enabled"
    cur = await repo.get_bool(key)
    await repo.set(key, "false" if cur else "true")
    await session.commit()
    await message.answer(i18n.t("done"))


@router.message(F.text.startswith("/pay_set"))
async def pay_set(message: Message, session: AsyncSession):
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("/pay_set کلید مقدار")
        return
    repo = SettingsRepository(session)
    await repo.set(parts[1], parts[2])
    await session.commit()
    await message.answer(i18n.t("done"))


@router.message(F.text == "/pay_test")
async def pay_test(message: Message, session: AsyncSession):
    svc = PlisioService(session)
    ok, msg = await svc.test_connection()
    await message.answer(msg if msg else ("✅ اتصال OK" if ok else "❌ خطا"))
