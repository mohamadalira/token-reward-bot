"""Sponsor panel — inline wizards only."""

import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.navigation.ui import answer_screen, btn, edit_screen, kb
from app.core.config import get_settings
from app.repositories import SettingsRepository, SponsorRepository
from app.services import ManualPaymentService, PlisioService, SponsorService, TextService
from app.utils.channel_resolver import validate_channel_for_bot

logger = logging.getLogger(__name__)
router = Router(name="sponsor_inline")
settings = get_settings()

SPN_HOME = "spn:home"
SPN_GUIDE = "spn:guide"
SPN_WALLET = "spn:wallet"
SPN_DEPOSIT = "spn:deposit"
SPN_CAMPAIGNS = "spn:campaigns"
SPN_NEW_CAMP = "spn:camp:new"


class DepositWizard(StatesGroup):
    tokens = State()
    method = State()
    receipt = State()


class CampaignWizard(StatesGroup):
    channel = State()
    reward = State()
    budget = State()
    confirm = State()


async def _t(session: AsyncSession) -> TextService:
    return TextService(session)


async def _ensure_sponsor(session: AsyncSession, user_id: int) -> tuple[bool, str]:
    svc = SponsorService(session)
    return await svc.ensure_sponsor(user_id)


@router.callback_query(F.data == SPN_HOME)
async def sponsor_home(callback: CallbackQuery, session: AsyncSession):
    settings_repo = SettingsRepository(session)
    if not await settings_repo.get_bool("sponsor_mode_enabled", True):
        texts = await _t(session)
        await callback.answer(await texts.t("error"), show_alert=True)
        return
    ok, msg = await _ensure_sponsor(session, callback.from_user.id)
    if not ok:
        await callback.answer(msg, show_alert=True)
        return
    svc = SponsorService(session)
    body = await svc.get_dashboard_text(callback.from_user.id)
    markup = kb(
        [btn("📚 راهنما", SPN_GUIDE), btn("💰 شارژ کیف پول", SPN_DEPOSIT)],
        [btn("🚀 کمپین جدید", SPN_NEW_CAMP), btn("📊 کمپین‌های من", SPN_CAMPAIGNS)],
        [btn("💼 موجودی", SPN_WALLET)],
        back="menu:main",
    )
    await edit_screen(callback, body, markup)
    await callback.answer()


@router.callback_query(F.data == SPN_GUIDE)
async def sponsor_guide(callback: CallbackQuery, session: AsyncSession):
    texts = await _t(session)
    repo = SettingsRepository(session)
    price = await repo.get("token_price_toman", "500")
    body = await texts.t("sponsor_guide", token_price=price)
    await edit_screen(callback, body, kb(back=SPN_HOME))
    await callback.answer()


@router.callback_query(F.data == SPN_WALLET)
async def sponsor_wallet(callback: CallbackQuery, session: AsyncSession):
    svc = SponsorService(session)
    body = await svc.get_wallet_info(callback.from_user.id)
    await edit_screen(callback, body, kb(back=SPN_HOME))
    await callback.answer()


@router.callback_query(F.data == SPN_CAMPAIGNS)
async def sponsor_campaigns(callback: CallbackQuery, session: AsyncSession):
    repo = SponsorRepository(session)
    sp = await repo.get_by_user_id(callback.from_user.id)
    if not sp or not sp.campaigns:
        await edit_screen(callback, "کمپینی نداری 😕", kb(back=SPN_HOME))
        await callback.answer()
        return
    lines = ["📊 کمپین‌ها:\n"]
    for c in sp.campaigns:
        lines.append(
            f"• {c.channel_title} | {c.status.value}\n"
            f"  💰 {c.reward_per_join}/عضو | باقی: {c.remaining_budget}"
        )
    await edit_screen(callback, "\n".join(lines), kb(back=SPN_HOME))
    await callback.answer()


# ── Deposit wizard ────────────────────────────────────────────────────────────

@router.callback_query(F.data == SPN_DEPOSIT)
async def deposit_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    ok, msg = await _ensure_sponsor(session, callback.from_user.id)
    if not ok:
        await callback.answer(msg, show_alert=True)
        return
    await state.set_state(DepositWizard.tokens)
    await edit_screen(callback, "💰 چند توکن می‌خوای بخری؟", kb(back=SPN_HOME))
    await callback.answer()


@router.message(DepositWizard.tokens)
async def deposit_tokens(message: Message, state: FSMContext, session: AsyncSession):
    repo = SettingsRepository(session)
    try:
        tokens = int(message.text.strip().replace(",", ""))
    except ValueError:
        await message.answer("عدد معتبر بفرست.")
        return
    min_t = await repo.get_int("min_token_purchase", 1000)
    max_t = await repo.get_int("max_token_purchase", 1000000)
    if tokens < min_t or tokens > max_t:
        await message.answer(f"باید بین {min_t} و {max_t} توکن باشد.")
        return
    price = await repo.get_int("token_price_toman", 500)
    total = tokens * price
    await state.update_data(tokens=tokens, toman=total, price=price)
    await state.set_state(DepositWizard.method)
    pl = await repo.get_bool("plisio_enabled")
    mc = await repo.get_bool("manual_card_enabled")
    rows = []
    if mc:
        rows.append([btn("💳 کارت به کارت", "spn:dep:manual")])
    if pl:
        rows.append([btn("₿ کریپتو", "spn:dep:crypto")])
    if not rows:
        await message.answer("هیچ روش پرداختی فعال نیست — با ادمین تماس بگیر.")
        await state.clear()
        return
    summary = (
        f"🎁 {tokens:,} توکن\n"
        f"💵 هر توکن: {price:,} تومان\n"
        f"💰 مبلغ: {total:,} تومان\n\n"
        f"روش پرداخت:"
    )
    await message.answer(summary, reply_markup=kb(*rows, back=SPN_HOME))


@router.callback_query(F.data == "spn:dep:manual")
async def deposit_manual(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    repo = SettingsRepository(session)
    holder = await repo.get("manual_card_holder", "—")
    card = await repo.get("manual_card_number", "—")
    body = (
        f"💳 کارت به کарт\n\n"
        f"👤 {holder}\n💳 {card}\n"
        f"💰 مبلغ: {data.get('toman', 0):,} تومان\n"
        f"🎁 توکن: {data.get('tokens', 0):,}\n\n"
        f"📤 بعد از پرداخت رسید را بفرست."
    )
    await state.set_state(DepositWizard.receipt)
    await edit_screen(callback, body, kb(back=SPN_DEPOSIT))
    await callback.answer()


@router.message(DepositWizard.receipt, F.photo)
async def deposit_receipt_photo(
    message: Message, state: FSMContext, session: AsyncSession, bot: Bot
):
    data = await state.get_data()
    repo = SponsorRepository(session)
    sp = await repo.get_by_user_id(message.from_user.id)
    if not sp:
        await message.answer("خطا — دوباره از پنل اسپانسری شروع کن.")
        await state.clear()
        return
    file_id = message.photo[-1].file_id
    svc = ManualPaymentService(session)
    pid = await svc.submit_wallet_deposit(
        sp.id,
        token_amount=data["tokens"],
        amount_toman=data["toman"],
        file_id=file_id,
    )
    await state.clear()
    texts = await _t(session)
    await message.answer(await texts.t("receipt_uploaded"))
    for admin_id in settings.admin_id_list:
        try:
            cap = (
                f"📸 درخواست شارژ #{pid}\n"
                f"👤 {message.from_user.id}\n"
                f"🎁 {data['tokens']} توکن\n"
                f"💰 {data['toman']:,} تومان"
            )
            markup = kb(
                [btn("✅ تایید", f"adm:rcpt:ok:{pid}"), btn("❌ رد", f"adm:rcpt:no:{pid}")],
            )
            await bot.send_photo(admin_id, file_id, caption=cap, reply_markup=markup)
        except Exception:
            logger.exception("notify admin receipt failed")


@router.callback_query(F.data == "spn:dep:crypto")
async def deposit_crypto(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    repo = SponsorRepository(session)
    sp = await repo.get_by_user_id(callback.from_user.id)
    if not sp:
        await callback.answer("خطا", show_alert=True)
        return
    settings_repo = SettingsRepository(session)
    price_usd = await settings_repo.get_float("token_price_usd", 0.01)
    amount_usd = data["tokens"] * price_usd
    plisio = PlisioService(session)
    ok, url, _ = await plisio.create_invoice(sp.id, amount_usd, token_amount=data["tokens"])
    await state.clear()
    if ok:
        await edit_screen(callback, f"₿ لینک پرداخت:\n{url}", kb(back=SPN_HOME))
    else:
        await callback.answer(url or "خطا", show_alert=True)
    await callback.answer()


# ── Campaign wizard ───────────────────────────────────────────────────────────

@router.callback_query(F.data == SPN_NEW_CAMP)
async def campaign_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    ok, msg = await _ensure_sponsor(session, callback.from_user.id)
    if not ok:
        await callback.answer(msg, show_alert=True)
        return
    await state.set_state(CampaignWizard.channel)
    await edit_screen(
        callback,
        "مرحله ۱/۴\n🔗 لینک یا @username کانال:",
        kb(back=SPN_HOME),
    )
    await callback.answer()


@router.message(CampaignWizard.channel)
async def campaign_channel(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    ok, err, info = await validate_channel_for_bot(bot, message.text)
    if not ok or not info:
        await message.answer(err or "خطا در ثبت کانال")
        return
    await state.update_data(channel_info=info)
    await state.set_state(CampaignWizard.reward)
    await message.answer(
        f"✅ کانال: {info['title']}\n\nمرحله ۲/۴\n💰 پاداش هر عضو (توکن):"
    )


@router.message(CampaignWizard.reward)
async def campaign_reward(message: Message, state: FSMContext, session: AsyncSession):
    try:
        reward = int(message.text.strip())
    except ValueError:
        await message.answer("عدد بفرست")
        return
    repo = SettingsRepository(session)
    min_r = await repo.get_int("min_reward_per_join", 5)
    max_r = await repo.get_int("max_reward_per_join", 500)
    if reward < min_r or reward > max_r:
        await message.answer(f"پاداش باید بین {min_r} و {max_r} باشد.")
        return
    await state.update_data(reward=reward)
    await state.set_state(CampaignWizard.budget)
    await message.answer("مرحله ۳/۴\n📦 بودجه کل کمپین (توکن):")


@router.message(CampaignWizard.budget)
async def campaign_budget(message: Message, state: FSMContext, session: AsyncSession):
    try:
        budget = int(message.text.strip())
    except ValueError:
        await message.answer("عدد بفرست")
        return
    data = await state.get_data()
    reward = data["reward"]
    joins = budget // reward if reward else 0
    await state.update_data(budget=budget)
    await state.set_state(CampaignWizard.confirm)
    preview = (
        f"📋 پیش‌نمایش کمپین\n\n"
        f"📣 {data['channel_info']['title']}\n"
        f"💰 {reward} توکن/عضو\n"
        f"📦 بودجه: {budget} توکن\n"
        f"👥 ~{joins} عضو"
    )
    markup = kb([btn("✅ تایید", "spn:camp:save"), btn("❌ لغو", SPN_HOME)])
    await message.answer(preview, reply_markup=markup)


@router.callback_query(F.data == "spn:camp:save")
async def campaign_save(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    data = await state.get_data()
    info = data.get("channel_info")
    if not info:
        await callback.answer("دوباره شروع کن", show_alert=True)
        return
    svc = SponsorService(session)
    ok, msg, cid = await svc.create_campaign_from_info(
        callback.from_user.id,
        info,
        data["reward"],
        data["budget"],
        bot,
        use_wallet=True,
    )
    await state.clear()
    if ok:
        texts = await _t(session)
        await edit_screen(callback, await texts.t("campaign_created_active"), kb(back=SPN_HOME))
    else:
        logger.warning("campaign save failed user=%s: %s", callback.from_user.id, msg)
        await callback.answer(msg, show_alert=True)
    await callback.answer()
