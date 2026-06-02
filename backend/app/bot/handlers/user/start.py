import logging
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters.admin import NotBannedFilter
from app.bot.keyboards.main import (
    check_membership_keyboard,
    confirm_purchase_keyboard,
    earn_mode_keyboard,
    main_menu_keyboard,
    shop_product_keyboard,
    task_keyboard,
)
from app.core.config import get_settings
from app.locales import get_i18n
from app.repositories import ChannelRepository, SettingsRepository, ShopRepository, UserRepository
from app.services import ReferralService, ShopService, TaskService, TokenService
from app.utils.formatters import format_number
from app.utils.telegram_helpers import check_channel_membership

logger = logging.getLogger(__name__)
router = Router(name="user")
settings = get_settings()
i18n = get_i18n()


async def _check_mandatory(bot: Bot, session: AsyncSession, user_id: int) -> tuple[bool, list]:
    settings_repo = SettingsRepository(session)
    if not await settings_repo.get_bool("force_join_enabled", True):
        return True, []
    channels = ChannelRepository(session)
    mandatory = await channels.get_mandatory_channels()
    if not mandatory:
        return True, []
    for ch in mandatory:
        if not await check_channel_membership(bot, user_id, ch.channel_id):
            return False, mandatory
    return True, []


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, bot: Bot):
    referred_by_id: Optional[int] = None
    args = message.text.split(maxsplit=1)
    if len(args) > 1 and args[1].startswith("ref_"):
        code = args[1][4:]
        user_repo = UserRepository(session)
        referrer = await user_repo.get_by_referral_code(code)
        if referrer and referrer.id != message.from_user.id:
            referred_by_id = referrer.id

    user_repo = UserRepository(session)
    is_admin = message.from_user.id in settings.admin_id_list
    user, is_new = await user_repo.get_or_create(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        referred_by_id=referred_by_id,
        is_admin=is_admin,
    )
    await session.commit()

    ok, mandatory = await _check_mandatory(bot, session, message.from_user.id)
    if not ok:
        await message.answer(
            i18n.t("join_channels_first"),
            reply_markup=check_membership_keyboard(mandatory),
        )
        return

    if is_new and referred_by_id:
        referral_svc = ReferralService(session)
        await referral_svc.process_referral(bot, referred_by_id, message.from_user.id)

    settings_repo = SettingsRepository(session)
    welcome = await settings_repo.get("welcome_message", i18n.t("welcome", name=message.from_user.first_name or ""))
    await message.answer(
        welcome,
        reply_markup=main_menu_keyboard(is_admin=user.is_admin, is_sponsor=user.is_sponsor),
    )


@router.callback_query(F.data == "check_membership")
async def callback_check_membership(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    ok, mandatory = await _check_mandatory(bot, session, callback.from_user.id)
    if ok:
        await callback.message.edit_text(i18n.t("membership_ok"))
        user_repo = UserRepository(session)
        user = await user_repo.get_by_id(callback.from_user.id)
        await callback.message.answer(
            i18n.t("main_menu"),
            reply_markup=main_menu_keyboard(
                is_admin=callback.from_user.id in settings.admin_id_list,
                is_sponsor=user.is_sponsor if user else False,
            ),
        )
    else:
        await callback.answer(i18n.t("membership_fail"), show_alert=True)
    await callback.answer()


@router.message(F.text == i18n.t("btn_profile"))
async def show_profile(message: Message, session: AsyncSession):
    svc = TokenService(session)
    text = await svc.get_profile_text(message.from_user.id)
    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(message.from_user.id)
    if user:
        settings_repo = SettingsRepository(session)
        bot_username = await settings_repo.get("bot_username", "")
        link = f"https://t.me/{bot_username}?start=ref_{user.referral_code}" if bot_username else f"ref_{user.referral_code}"
        text += "\n\n" + i18n.t("referral_link", link=link)
    await message.answer(text)


@router.message(F.text == i18n.t("btn_earn"))
async def earn_tokens(message: Message, session: AsyncSession):
    settings_repo = SettingsRepository(session)
    mode = await settings_repo.get("bot_mode", "combined")
    if mode == "combined":
        await message.answer(i18n.t("earn_choose_mode"), reply_markup=earn_mode_keyboard())
    elif mode == "referral":
        await _show_referral(message, session)
    else:
        await _show_tasks(message, session)


@router.callback_query(F.data == "earn:referral")
async def callback_earn_referral(callback: CallbackQuery, session: AsyncSession):
    await _show_referral(callback.message, session)
    await callback.answer()


@router.callback_query(F.data == "earn:tasks")
async def callback_earn_tasks(callback: CallbackQuery, session: AsyncSession):
    await _show_tasks(callback.message, session)
    await callback.answer()


async def _show_referral(message: Message, session: AsyncSession):
    settings_repo = SettingsRepository(session)
    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(message.chat.id)
    reward = await settings_repo.get_int("referral_reward", 50)
    bot_username = await settings_repo.get("bot_username", "")
    link = f"https://t.me/{bot_username}?start=ref_{user.referral_code}" if user and bot_username else ""
    await message.answer(
        i18n.t("referral_info", reward=reward, count=user.referral_count if user else 0, link=link)
    )


async def _show_tasks(message: Message, session: AsyncSession):
    task_svc = TaskService(session)
    tasks = await task_svc.get_available_tasks()
    if not tasks:
        await message.answer(i18n.t("no_tasks"))
        return
    for task in tasks:
        await message.answer(
            i18n.t("task_card", title=task.title, reward=task.reward_amount),
            reply_markup=task_keyboard(task.id, task.invite_link),
        )


@router.callback_query(F.data.startswith("verify_task:"))
async def verify_task(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    channel_id = int(callback.data.split(":")[1])
    task_svc = TaskService(session)
    ok, msg, _ = await task_svc.verify_task(bot, callback.from_user.id, channel_id)
    await callback.answer(msg, show_alert=True)


@router.message(F.text == i18n.t("btn_shop"))
async def show_shop(message: Message, session: AsyncSession):
    shop = ShopRepository(session)
    products = await shop.get_products()
    if not products:
        await message.answer(i18n.t("shop_empty"))
        return
    for p in products:
        await message.answer(
            i18n.t("shop_product", name=p.name, description=p.description or "", price=p.token_cost, category=p.category, stock=p.stock),
            reply_markup=shop_product_keyboard(p.id),
        )


@router.callback_query(F.data.startswith("buy:"))
async def buy_product(callback: CallbackQuery, session: AsyncSession):
    product_id = int(callback.data.split(":")[1])
    shop = ShopRepository(session)
    product = await shop.get_product(product_id)
    if product:
        await callback.message.answer(
            i18n.t("purchase_confirm", name=product.name, price=product.token_cost),
            reply_markup=confirm_purchase_keyboard(product_id),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_buy:"))
async def confirm_buy(callback: CallbackQuery, session: AsyncSession):
    product_id = int(callback.data.split(":")[1])
    shop_svc = ShopService(session)
    ok, msg, config_data = await shop_svc.purchase(callback.from_user.id, product_id)
    if ok and config_data:
        await callback.message.answer(msg)
        await callback.message.answer(f"```\n{config_data}\n```", parse_mode="Markdown")
    else:
        await callback.answer(msg, show_alert=True)
    await callback.answer()


@router.message(F.text == i18n.t("btn_my_configs"))
async def my_configs(message: Message, session: AsyncSession):
    shop = ShopRepository(session)
    purchases = await shop.get_user_purchases(message.from_user.id)
    if not purchases:
        await message.answer("هنوز خریدی نداری 😕")
        return
    for p in purchases:
        await message.answer(f"📦 {p.product.name if p.product else 'کانفیگ'}\n💰 {p.token_cost} توکن\n\n```\n{p.config_data}\n```", parse_mode="Markdown")


@router.message(F.text == i18n.t("btn_leaderboard"))
async def leaderboard(message: Message, session: AsyncSession):
    user_repo = UserRepository(session)
    settings_repo = SettingsRepository(session)
    use_persian = await settings_repo.get_bool("use_persian_numbers", True)
    leaders = await user_repo.get_leaderboard(10)
    entries = []
    for i, u in enumerate(leaders, 1):
        name = u.first_name or u.username or str(u.id)
        entries.append(i18n.t("leaderboard_entry", rank=i, name=name, tokens=format_number(u.total_earned, use_persian)))
    await message.answer(i18n.t("leaderboard", entries="\n".join(entries) or "—"))


@router.message(F.text == i18n.t("btn_support"))
async def support(message: Message, session: AsyncSession):
    settings_repo = SettingsRepository(session)
    username = await settings_repo.get("support_username", "support")
    await message.answer(i18n.t("support", username=username))


@router.message(F.text == i18n.t("btn_rules"))
async def rules(message: Message, session: AsyncSession):
    settings_repo = SettingsRepository(session)
    rules_text = await settings_repo.get("rules_text", "")
    await message.answer(i18n.t("rules", rules=rules_text))
