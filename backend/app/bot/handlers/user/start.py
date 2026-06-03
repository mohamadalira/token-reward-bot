import logging
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.inline_menus import (
    back_main_button,
    check_membership_keyboard,
    confirm_purchase_keyboard,
    earn_mode_keyboard,
    shop_categories_keyboard,
    shop_products_keyboard,
    task_channel_keyboard,
    user_main_menu,
)
from app.core.config import get_settings
from app.repositories import CategoryRepository, ChannelRepository, ShopRepository, UserRepository
from app.repositories import SettingsRepository
from app.services import ReferralService, ShopService, TaskService, TextService, TokenService
from app.utils.formatters import format_number
from app.utils.telegram_helpers import channel_is_accessible, check_channel_membership

logger = logging.getLogger(__name__)
router = Router(name="user")
settings = get_settings()


async def _texts(session: AsyncSession) -> TextService:
    return TextService(session)


async def _check_mandatory(bot: Bot, session: AsyncSession, user_id: int) -> tuple[bool, list]:
    if user_id in settings.admin_id_list:
        return True, []

    settings_repo = SettingsRepository(session)
    if not await settings_repo.get_bool("force_join_enabled", False):
        return True, []

    channels = ChannelRepository(session)
    mandatory = await channels.get_mandatory_channels()
    if not mandatory:
        return True, []

    pending = []
    for ch in mandatory:
        if await check_channel_membership(bot, user_id, ch.channel_id):
            continue
        if not await channel_is_accessible(bot, ch.channel_id):
            logger.warning(
                "Auto-disabling broken mandatory channel #%s (%s)",
                ch.id,
                ch.channel_id,
            )
            ch.is_enabled = False
            await session.commit()
            continue
        pending.append(ch)

    if not pending:
        return True, []
    return False, pending


async def _menu_kb(session: AsyncSession, texts: TextService, user_id: int, user=None):
    settings_repo = SettingsRepository(session)
    sponsor_enabled = await settings_repo.get_bool("sponsor_mode_enabled", True)
    if user is None:
        user = await UserRepository(session).get_by_id(user_id)
    return await user_main_menu(
        texts,
        is_admin=user_id in settings.admin_id_list,
        is_sponsor=bool(user and user.is_sponsor),
        sponsor_enabled=sponsor_enabled,
        webapp_url=settings.webapp_url,
    )


async def _send_main_menu(
    message: Message,
    session: AsyncSession,
    user_id: int,
    *,
    edit: bool = False,
) -> None:
    texts = await _texts(session)
    kb = await _menu_kb(session, texts, user_id)
    title = await texts.t("main_menu")
    if edit and message.text:
        await message.edit_text(title, reply_markup=kb)
    else:
        await message.answer(title, reply_markup=kb)


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, bot: Bot):
    texts = await _texts(session)
    try:
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
                await texts.t("join_channels_first"),
                reply_markup=await check_membership_keyboard(texts, mandatory),
            )
            return

        if is_new and referred_by_id:
            referral_svc = ReferralService(session)
            await referral_svc.process_referral(bot, referred_by_id, message.from_user.id)

        settings_repo = SettingsRepository(session)
        welcome = await settings_repo.get(
            "welcome_message",
            await texts.t("welcome", name=message.from_user.first_name or ""),
        )
        if "{name}" in welcome:
            welcome = welcome.format(name=message.from_user.first_name or "")
        kb = await _menu_kb(session, texts, message.from_user.id, user)
        await message.answer(welcome, reply_markup=kb)
    except Exception:
        logger.exception("cmd_start failed for user %s", message.from_user.id)
        await message.answer(await texts.t("error"))


@router.callback_query(F.data == "menu:main")
async def menu_main(callback: CallbackQuery, session: AsyncSession):
    texts = await _texts(session)
    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(callback.from_user.id)
    kb = await _menu_kb(session, texts, callback.from_user.id, user)
    await callback.message.edit_text(await texts.t("main_menu"), reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "check_membership")
async def callback_check_membership(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    texts = await _texts(session)
    ok, mandatory = await _check_mandatory(bot, session, callback.from_user.id)
    if ok:
        await callback.message.edit_text(await texts.t("membership_ok"))
        await _send_main_menu(callback.message, session, callback.from_user.id)
    else:
        await callback.answer(await texts.t("membership_fail"), show_alert=True)
    await callback.answer()


@router.callback_query(F.data == "menu:profile")
async def menu_profile(callback: CallbackQuery, session: AsyncSession):
    texts = await _texts(session)
    svc = TokenService(session)
    text = await svc.get_profile_text(callback.from_user.id)
    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(callback.from_user.id)
    if user:
        settings_repo = SettingsRepository(session)
        bot_username = await settings_repo.get("bot_username", "")
        link = (
            f"https://t.me/{bot_username}?start=ref_{user.referral_code}"
            if bot_username
            else f"ref_{user.referral_code}"
        )
        text += "\n\n" + await texts.t("referral_link", link=link)
    back = await texts.t("btn_back")
    await callback.message.edit_text(text, reply_markup=back_main_button(back))
    await callback.answer()


@router.callback_query(F.data == "menu:earn")
async def menu_earn(callback: CallbackQuery, session: AsyncSession):
    texts = await _texts(session)
    settings_repo = SettingsRepository(session)
    mode = await settings_repo.get("bot_mode", "combined")
    if mode == "combined":
        await callback.message.edit_text(
            await texts.t("earn_choose_mode"),
            reply_markup=await earn_mode_keyboard(texts),
        )
    elif mode == "referral":
        await _show_referral(callback.message, session, edit=True)
    else:
        await _show_tasks(callback.message, session, edit=True)
    await callback.answer()


@router.callback_query(F.data == "earn:referral")
async def callback_earn_referral(callback: CallbackQuery, session: AsyncSession):
    await _show_referral(callback.message, session, edit=True)
    await callback.answer()


@router.callback_query(F.data == "earn:tasks")
async def callback_earn_tasks(callback: CallbackQuery, session: AsyncSession):
    await _show_tasks(callback.message, session, edit=True)
    await callback.answer()


async def _show_referral(message: Message, session: AsyncSession, edit: bool = False):
    texts = await _texts(session)
    settings_repo = SettingsRepository(session)
    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(message.chat.id)
    reward = await settings_repo.get_int("referral_reward", 50)
    bot_username = await settings_repo.get("bot_username", "")
    link = f"https://t.me/{bot_username}?start=ref_{user.referral_code}" if user and bot_username else ""
    body = await texts.t("referral_info", reward=reward, count=user.referral_count if user else 0, link=link)
    back = await texts.t("btn_back")
    kb = back_main_button(back)
    if edit:
        await message.edit_text(body, reply_markup=kb)
    else:
        await message.answer(body, reply_markup=kb)


async def _show_tasks(message: Message, session: AsyncSession, edit: bool = False):
    texts = await _texts(session)
    task_svc = TaskService(session)
    tasks = await task_svc.get_available_tasks()
    if not tasks:
        back = await texts.t("btn_back")
        text = await texts.t("no_tasks")
        if edit:
            await message.edit_text(text, reply_markup=back_main_button(back))
        else:
            await message.answer(text, reply_markup=back_main_button(back))
        return
    if edit:
        await message.edit_text(await texts.t("earn_menu_tasks"))
    for task in tasks:
        desc = task.description or await texts.t("task_no_description")
        reward = task.reward_amount
        if task.campaign and task.campaign.status.value == "active":
            reward = task.campaign.reward_per_join
        body = await texts.t(
            "task_channel_card",
            title=task.title,
            description=desc,
            reward=reward,
        )
        kb = task_channel_keyboard(
            task.id,
            task.invite_link,
            await texts.t("btn_view_channel"),
            await texts.t("btn_joined"),
        )
        await message.answer(body, reply_markup=kb)


@router.callback_query(F.data.startswith("verify_task:"))
async def verify_task(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    texts = await _texts(session)
    channel_id = int(callback.data.split(":")[1])
    task_svc = TaskService(session)
    ok, msg, _ = await task_svc.verify_task(bot, callback.from_user.id, channel_id)
    await callback.answer(msg, show_alert=True)
    if ok:
        try:
            await callback.message.edit_text(msg)
        except Exception:
            pass


@router.callback_query(F.data == "menu:shop")
async def menu_shop(callback: CallbackQuery, session: AsyncSession):
    texts = await _texts(session)
    cats = CategoryRepository(session)
    categories = await cats.list_active()
    if not categories:
        shop = ShopRepository(session)
        products = await shop.get_products()
        if not products:
            await callback.message.edit_text(
                await texts.t("shop_empty"),
                reply_markup=back_main_button(await texts.t("btn_back")),
            )
        else:
            await callback.message.edit_text(await texts.t("shop_pick_product"))
            for p in products:
                body = await texts.t(
                    "shop_product",
                    name=p.name,
                    description=p.description or "",
                    price=p.token_cost,
                    category=p.category,
                    stock=p.stock,
                )
                from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=await texts.t("btn_buy"), callback_data=f"buy:{p.id}")],
                ])
                await callback.message.answer(body, reply_markup=kb)
    else:
        intro = await texts.t("shop_pick_category")
        await callback.message.edit_text(
            intro,
            reply_markup=await shop_categories_keyboard(texts, categories),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("shop:cat:"))
async def shop_category(callback: CallbackQuery, session: AsyncSession):
    texts = await _texts(session)
    cat_id = int(callback.data.split(":")[2])
    cats = CategoryRepository(session)
    cat = await cats.get_by_id(cat_id)
    if not cat:
        await callback.answer(await texts.t("error"), show_alert=True)
        return
    products = await cats.get_products_by_category(cat_id)
    if not products:
        await callback.message.edit_text(
            await texts.t("shop_empty"),
            reply_markup=back_main_button(await texts.t("btn_back")),
        )
    else:
        desc = cat.description or ""
        header = await texts.t("shop_category_header", name=cat.name, description=desc)
        await callback.message.edit_text(
            header,
            reply_markup=shop_products_keyboard(
                products, await texts.t("btn_back"), cat_id
            ),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("buy:"))
async def buy_product(callback: CallbackQuery, session: AsyncSession):
    texts = await _texts(session)
    product_id = int(callback.data.split(":")[1])
    shop = ShopRepository(session)
    product = await shop.get_product(product_id)
    if product:
        await callback.message.answer(
            await texts.t("purchase_confirm", name=product.name, price=product.token_cost),
            reply_markup=await confirm_purchase_keyboard(texts, product_id),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_buy:"))
async def confirm_buy(callback: CallbackQuery, session: AsyncSession):
    texts = await _texts(session)
    product_id = int(callback.data.split(":")[1])
    shop_svc = ShopService(session)
    ok, msg, config_data = await shop_svc.purchase(callback.from_user.id, product_id)
    if ok and config_data:
        await callback.message.answer(msg)
        await callback.message.answer(f"<pre>{config_data}</pre>", parse_mode="HTML")
    else:
        await callback.answer(msg, show_alert=True)
    await callback.answer()


@router.callback_query(F.data == "cancel")
async def cancel_action(callback: CallbackQuery, session: AsyncSession):
    texts = await _texts(session)
    await callback.answer(await texts.t("cancelled"), show_alert=True)


@router.callback_query(F.data == "menu:configs")
async def menu_configs(callback: CallbackQuery, session: AsyncSession):
    texts = await _texts(session)
    shop = ShopRepository(session)
    purchases = await shop.get_user_purchases(callback.from_user.id)
    if not purchases:
        await callback.message.edit_text(
            await texts.t("no_purchases"),
            reply_markup=back_main_button(await texts.t("btn_back")),
        )
    else:
        await callback.message.edit_text(await texts.t("my_configs_header"))
        for p in purchases:
            name = p.product.name if p.product else "کانفیگ"
            await callback.message.answer(
                f"📦 {name}\n💰 {p.token_cost} توکن\n\n<pre>{p.config_data}</pre>",
                parse_mode="HTML",
            )
    await callback.answer()


@router.callback_query(F.data == "menu:sponsor")
async def menu_sponsor(callback: CallbackQuery, session: AsyncSession):
    from app.bot.handlers.sponsor.inline import sponsor_home
    await sponsor_home(callback, session)


@router.callback_query(F.data == "menu:admin")
async def menu_admin(callback: CallbackQuery, session: AsyncSession):
    texts = await _texts(session)
    if callback.from_user.id not in settings.admin_id_list:
        await callback.answer(await texts.t("admin_only"), show_alert=True)
        return
    from app.bot.handlers.admin.inline import admin_home
    await admin_home(callback, session)


@router.callback_query(F.data == "menu:support")
async def menu_support(callback: CallbackQuery, session: AsyncSession):
    texts = await _texts(session)
    settings_repo = SettingsRepository(session)
    username = await settings_repo.get("support_username", "support")
    back = await texts.t("btn_back")
    await callback.message.edit_text(
        await texts.t("support", username=username),
        reply_markup=back_main_button(back),
    )
    await callback.answer()


@router.callback_query(F.data == "menu:rules")
async def menu_rules(callback: CallbackQuery, session: AsyncSession):
    texts = await _texts(session)
    settings_repo = SettingsRepository(session)
    rules_text = await settings_repo.get("rules_text", "")
    back = await texts.t("btn_back")
    await callback.message.edit_text(
        await texts.t("rules", rules=rules_text),
        reply_markup=back_main_button(back),
    )
    await callback.answer()
