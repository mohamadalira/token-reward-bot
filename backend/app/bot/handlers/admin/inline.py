"""Admin panel — 100% inline keyboard wizards."""

import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters.admin import AdminCallbackFilter
from app.bot.navigation.ui import answer_screen, btn, edit_screen, kb, validate_card_number
from app.core.config import get_settings
from app.models import CampaignStatus, Sponsor, SponsorChannel, SponsorStatus, TokenTransaction
from app.repositories import ChannelRepository, SettingsRepository, SponsorRepository, UserRepository
from app.services import ManualPaymentService, PlisioService, TextService
from app.utils.channel_resolver import validate_channel_for_bot

logger = logging.getLogger(__name__)
router = Router(name="admin_inline")
router.callback_query.filter(AdminCallbackFilter())
settings = get_settings()

ADM_HOME = "adm:home"
ADM_SETTINGS = "adm:settings"
ADM_DASH = "adm:dash"
ADM_PAY_MGR = "adm:paymgr"
ADM_BANK = "adm:bank"
ADM_PLISIO = "adm:plisio"
ADM_REFERRAL = "adm:referral"
ADM_MANDATORY = "adm:mandatory"
ADM_MANDATORY_ADD = "adm:mandatory:add"
ADM_SPONSORS = "adm:sponsors"
ADM_CHANNELS = "adm:channels"
ADM_TEXTS = "adm:texts"
ADM_SHOP = "adm:shop"
ADM_RECEIPTS = "adm:receipts"
ADM_SEARCH = "adm:search"


class SearchWizard(StatesGroup):
    query = State()


class BankWizard(StatesGroup):
    holder = State()
    card = State()
    confirm = State()


class PlisioWizard(StatesGroup):
    api_key = State()
    secret_key = State()
    confirm = State()


class ReferralWizard(StatesGroup):
    amount = State()


class MandatoryWizard(StatesGroup):
    link = State()
    confirm = State()


class TokenPriceWizard(StatesGroup):
    toman = State()


async def _t(session: AsyncSession) -> TextService:
    return TextService(session)


# ── Home & dashboard ──────────────────────────────────────────────────────────

@router.callback_query(F.data == ADM_HOME)
async def admin_home(callback: CallbackQuery, session: AsyncSession):
    texts = await _t(session)
    markup = kb(
        [btn("📊 داشبورد", ADM_DASH), btn("⚙️ تنظیمات", ADM_SETTINGS)],
        [btn("👥 اسپانسرها", ADM_SPONSORS), btn("📣 کانال‌های اسپانسری", ADM_CHANNELS)],
        [btn("💰 درخواست‌های شارژ", ADM_RECEIPTS), btn("🛒 فروشگاه", ADM_SHOP)],
        [btn("🔍 جستجو", ADM_SEARCH)],
        back="menu:main",
    )
    await edit_screen(callback, await texts.t("admin_menu"), markup)
    await callback.answer()


@router.callback_query(F.data == ADM_DASH)
async def admin_dashboard(callback: CallbackQuery, session: AsyncSession):
    users = UserRepository(session)
    sponsors = SponsorRepository(session)
    result = await session.execute(
        select(func.sum(TokenTransaction.amount)).where(TokenTransaction.amount > 0)
    )
    tokens = int(result.scalar() or 0)
    revenue = await sponsors.get_revenue_stats()
    texts = await _t(session)
    body = await texts.t(
        "dashboard",
        total_users=await users.count_all(),
        active_users=await users.count_active(),
        total_sponsors=await sponsors.count_all(),
        active_campaigns=await sponsors.count_active_campaigns(),
        total_payments=await sponsors.count_payments(),
        tokens_distributed=tokens,
    )
    body += f"\n\n💵 درآمد: ${revenue['total_revenue']:.2f}"
    await edit_screen(callback, body, kb(back=ADM_HOME))
    await callback.answer()


# ── Settings menu ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == ADM_SETTINGS)
async def settings_menu(callback: CallbackQuery, session: AsyncSession):
    texts = await _t(session)
    markup = kb(
        [btn("💰 ارزش توکن", "adm:token_price"), btn("💳 کارت بانکی", ADM_BANK)],
        [btn("₿ Plisio", ADM_PLISIO), btn("🎁 پاداش رفرال", ADM_REFERRAL)],
        [btn("📢 کانال اجباری", ADM_MANDATORY), btn("📣 کانال اسپانسری", ADM_CHANNELS)],
        [btn("📝 مدیریت متن‌ها", ADM_TEXTS), btn("💰 مدیریت پرداخت‌ها", ADM_PAY_MGR)],
        [btn("🛒 مدیریت فروشگاه", ADM_SHOP)],
        back=ADM_HOME,
    )
    await edit_screen(callback, "⚙️ تنظیمات", markup)
    await callback.answer()


@router.callback_query(F.data == "adm:token_price")
async def token_price_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    repo = SettingsRepository(session)
    cur = await repo.get("token_price_toman", "500")
    await state.set_state(TokenPriceWizard.toman)
    await state.update_data(back=ADM_SETTINGS)
    await edit_screen(
        callback,
        f"💰 ارزش هر توکن (تومان)\n\nفعلی: {cur}\n\nمقدار جدید را بفرست:",
        kb(back=ADM_SETTINGS),
    )
    await callback.answer()


@router.message(TokenPriceWizard.toman)
async def token_price_save(message: Message, state: FSMContext, session: AsyncSession):
    try:
        val = int(message.text.strip().replace(",", ""))
    except ValueError:
        await message.answer("عدد معتبر بفرست.")
        return
    repo = SettingsRepository(session)
    await repo.set("token_price_toman", str(val))
    await session.commit()
    await state.clear()
    texts = await _t(session)
    await answer_screen(message, f"✅ ارزش توکن: {val:,} تومان", kb(back=ADM_SETTINGS))


# ── Bank card wizard ──────────────────────────────────────────────────────────

@router.callback_query(F.data == ADM_BANK)
async def bank_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    repo = SettingsRepository(session)
    preview = (
        f"💳 کارت فعلی\n\n"
        f"👤 {await repo.get('manual_card_holder', '—')}\n"
        f"💳 {await repo.get('manual_card_number', '—')}\n"
        f"🏦 {await repo.get('manual_bank_name', '—')}"
    )
    markup = kb([btn("✏️ ویرایش کارت", "adm:bank:edit")], back=ADM_SETTINGS)
    await edit_screen(callback, preview, markup)
    await callback.answer()


@router.callback_query(F.data == "adm:bank:edit")
async def bank_edit(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BankWizard.holder)
    await state.update_data(back=ADM_BANK)
    await edit_screen(callback, "مرحله ۱/۳\nنام صاحب حساب:", kb(back=ADM_BANK))
    await callback.answer()


@router.message(BankWizard.holder)
async def bank_holder(message: Message, state: FSMContext):
    await state.update_data(holder=message.text.strip())
    await state.set_state(BankWizard.card)
    await message.answer("مرحله ۲/۳\nشماره کارت (۱۶ رقم):")


@router.message(BankWizard.card)
async def bank_card(message: Message, state: FSMContext):
    ok, result = validate_card_number(message.text)
    if not ok:
        await message.answer(result)
        return
    await state.update_data(card=result)
    await state.set_state(BankWizard.confirm)
    data = await state.get_data()
    preview = f"👤 {data['holder']}\n💳 {result[:4]}-{result[4:8]}-{result[8:12]}-{result[12:]}"
    markup = kb(
        [btn("✅ تایید", "adm:bank:save"), btn("✏️ ویرایش", "adm:bank:edit")],
        back=ADM_BANK,
    )
    await message.answer(f"پیش‌نمایش:\n\n{preview}", reply_markup=markup)


@router.callback_query(F.data == "adm:bank:save")
async def bank_save(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    if not data.get("holder") or not data.get("card"):
        await callback.answer("اطلاعات ناقص است", show_alert=True)
        return
    repo = SettingsRepository(session)
    await repo.set("manual_card_holder", data["holder"])
    await repo.set("manual_card_number", data["card"])
    await repo.set("manual_card_enabled", "true")
    await session.commit()
    await state.clear()
    await edit_screen(callback, "✅ کارت بانکی ذخیره شد.", kb(back=ADM_SETTINGS))
    await callback.answer()


# ── Plisio wizard ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == ADM_PLISIO)
async def plisio_menu(callback: CallbackQuery, session: AsyncSession):
    repo = SettingsRepository(session)
    webhook = settings.webhook_url or f"{settings.webapp_url}{settings.webhook_path}"
    body = (
        f"₿ Plisio\n\n"
        f"API: {'✅' if await repo.get('plisio_api_key') else '❌'}\n"
        f"Secret: {'✅' if await repo.get('plisio_secret_key') else '❌'}\n"
        f"Callback: {webhook}"
    )
    markup = kb(
        [btn("✏️ تنظیم API", "adm:plisio:edit"), btn("🧪 تست اتصال", "adm:plisio:test")],
        back=ADM_SETTINGS,
    )
    await edit_screen(callback, body, markup)
    await callback.answer()


@router.callback_query(F.data == "adm:plisio:edit")
async def plisio_edit(callback: CallbackQuery, state: FSMContext):
    await state.set_state(PlisioWizard.api_key)
    await edit_screen(callback, "API Key را بفرست:", kb(back=ADM_PLISIO))
    await callback.answer()


@router.message(PlisioWizard.api_key)
async def plisio_api(message: Message, state: FSMContext):
    await state.update_data(api_key=message.text.strip())
    await state.set_state(PlisioWizard.secret_key)
    await message.answer("Secret Key را بفرست (یا - برای همان API Key):")


@router.message(PlisioWizard.secret_key)
async def plisio_secret(message: Message, state: FSMContext, session: AsyncSession):
    secret = message.text.strip()
    if secret == "-":
        data = await state.get_data()
        secret = data.get("api_key", "")
    data = await state.get_data()
    repo = SettingsRepository(session)
    await repo.set("plisio_api_key", data["api_key"])
    await repo.set("plisio_secret_key", secret)
    await repo.set("plisio_enabled", "true")
    await session.commit()
    await state.clear()
    await message.answer("✅ Plisio ذخیره شد.", reply_markup=kb(back=ADM_PLISIO))


@router.callback_query(F.data == "adm:plisio:test")
async def plisio_test(callback: CallbackQuery, session: AsyncSession):
    svc = PlisioService(session)
    ok, msg = await svc.test_connection()
    await callback.answer(msg, show_alert=True)


# ── Payment manager ───────────────────────────────────────────────────────────

@router.callback_query(F.data == ADM_PAY_MGR)
async def pay_manager(callback: CallbackQuery, session: AsyncSession):
    repo = SettingsRepository(session)
    pl = await repo.get_bool("plisio_enabled")
    mc = await repo.get_bool("manual_card_enabled")
    markup = kb(
        [btn(f"₿ کریپتو {'✅' if pl else '❌'}", "adm:paymgr:toggle:plisio")],
        [btn(f"💳 کارت {'✅' if mc else '❌'}", "adm:paymgr:toggle:manual")],
        back=ADM_SETTINGS,
    )
    await edit_screen(callback, "💰 مدیریت پرداخت‌ها", markup)
    await callback.answer()


@router.callback_query(F.data.startswith("adm:paymgr:toggle:"))
async def pay_toggle(callback: CallbackQuery, session: AsyncSession):
    key = "plisio_enabled" if callback.data.endswith("plisio") else "manual_card_enabled"
    repo = SettingsRepository(session)
    cur = await repo.get_bool(key)
    await repo.set(key, "false" if cur else "true")
    await session.commit()
    await pay_manager(callback, session)


# ── Referral reward ───────────────────────────────────────────────────────────

@router.callback_query(F.data == ADM_REFERRAL)
async def referral_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    repo = SettingsRepository(session)
    cur = await repo.get_int("referral_reward", 50)
    await state.set_state(ReferralWizard.amount)
    await edit_screen(callback, f"🎁 پاداش رفرال فعلی: {cur}\n\nمقدار جدید:", kb(back=ADM_SETTINGS))
    await callback.answer()


@router.message(ReferralWizard.amount)
async def referral_save(message: Message, state: FSMContext, session: AsyncSession):
    try:
        val = int(message.text.strip())
    except ValueError:
        await message.answer("عدد بفرست")
        return
    repo = SettingsRepository(session)
    await repo.set("referral_reward", str(val))
    await session.commit()
    await state.clear()
    await message.answer(f"✅ پاداش رفرال: {val}", reply_markup=kb(back=ADM_SETTINGS))


# ── Mandatory channels ────────────────────────────────────────────────────────

@router.callback_query(F.data == ADM_MANDATORY)
async def mandatory_list(callback: CallbackQuery, session: AsyncSession):
    settings_repo = SettingsRepository(session)
    force_on = await settings_repo.get_bool("force_join_enabled", False)
    repo = ChannelRepository(session)
    channels = await repo.get_mandatory_channels(enabled_only=False)
    status = "✅ فعال" if force_on else "❌ غیرفعال"
    lines = [f"📢 کانال‌های اجباری\n\nسیستم عضویت اجباری: {status}\n"]
    rows = [
        [btn(f"{'⛔ خاموش' if force_on else '✅ روشن'} عضویت اجباری", "adm:mandatory:toggle_force")],
    ]
    for ch in channels:
        lines.append(f"{'✅' if ch.is_enabled else '❌'} #{ch.id} {ch.title}")
        rows.append([btn(f"🗑 #{ch.id}", f"adm:mandatory:del:{ch.id}")])
    rows.append([btn("➕ افزودن", ADM_MANDATORY_ADD)])
    if channels:
        rows.append([btn("🗑 حذف همه کانال‌ها", "adm:mandatory:clearall")])
    markup = kb(*rows, back=ADM_SETTINGS)
    await edit_screen(callback, "\n".join(lines) if channels else lines[0] + "\nکانالی ثبت نشده.", markup)
    await callback.answer()


@router.callback_query(F.data == "adm:mandatory:toggle_force")
async def mandatory_toggle_force(callback: CallbackQuery, session: AsyncSession):
    repo = SettingsRepository(session)
    cur = await repo.get_bool("force_join_enabled", False)
    await repo.set("force_join_enabled", "false" if cur else "true")
    await session.commit()
    await mandatory_list(callback, session)


@router.callback_query(F.data == "adm:mandatory:clearall")
async def mandatory_clear_all(callback: CallbackQuery, session: AsyncSession):
    repo = ChannelRepository(session)
    count = await repo.clear_all_mandatory()
    settings_repo = SettingsRepository(session)
    await settings_repo.set("force_join_enabled", "false")
    await session.commit()
    await callback.answer(f"✅ {count} کانال حذف شد — عضویت اجباری خاموش شد", show_alert=True)
    await mandatory_list(callback, session)


@router.callback_query(F.data.startswith("adm:mandatory:del:"))
async def mandatory_del(callback: CallbackQuery, session: AsyncSession):
    ch_id = int(callback.data.split(":")[3])
    repo = ChannelRepository(session)
    await repo.remove_mandatory(ch_id)
    await session.commit()
    await mandatory_list(callback, session)


@router.callback_query(F.data == ADM_MANDATORY_ADD)
async def mandatory_add(callback: CallbackQuery, state: FSMContext):
    await state.set_state(MandatoryWizard.link)
    await edit_screen(callback, "لینک یا @username کانال:", kb(back=ADM_MANDATORY))
    await callback.answer()


@router.message(MandatoryWizard.link)
async def mandatory_link(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    ok, err, info = await validate_channel_for_bot(bot, message.text)
    if not ok or not info:
        await message.answer(err or "خطا")
        return
    await state.update_data(channel_info=info)
    await state.set_state(MandatoryWizard.confirm)
    preview = f"📢 {info['title']}\n🆔 {info['channel_id']}"
    markup = kb([btn("✅ تایید", "adm:mandatory:save")], back=ADM_MANDATORY)
    await message.answer(preview, reply_markup=markup)


@router.callback_query(F.data == "adm:mandatory:save")
async def mandatory_save(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    info = data.get("channel_info")
    if not info:
        await callback.answer("دوباره تلاش کن", show_alert=True)
        return
    repo = ChannelRepository(session)
    await repo.add_mandatory(
        info["channel_id"],
        info["title"],
        info.get("username"),
        info.get("invite_link"),
    )
    await session.commit()
    await state.clear()
    await edit_screen(callback, "✅ کانال اجباری اضافه شد.", kb(back=ADM_MANDATORY))
    await callback.answer()


# ── Sponsors list ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == ADM_SPONSORS)
async def sponsors_list(callback: CallbackQuery, session: AsyncSession):
    result = await session.execute(
        select(Sponsor).where(Sponsor.status == SponsorStatus.APPROVED).limit(20)
    )
    sponsors = list(result.scalars().all())
    rows = []
    for s in sponsors:
        rows.append([btn(f"👤 {s.user_id} | 💰 {s.wallet_balance}", f"adm:spn:view:{s.id}")])
    markup = kb(*rows, back=ADM_HOME) if rows else kb(back=ADM_HOME)
    await edit_screen(
        callback,
        f"👥 اسپانسرها ({len(sponsors)})",
        markup,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm:spn:view:"))
async def sponsor_view(callback: CallbackQuery, session: AsyncSession):
    sid = int(callback.data.split(":")[3])
    repo = SponsorRepository(session)
    sp = await repo.get_by_id(sid)
    if not sp:
        await callback.answer("پیدا نشد", show_alert=True)
        return
    campaigns = len(sp.campaigns or [])
    body = (
        f"👤 اسپانسر #{sid}\n🆔 {sp.user_id}\n"
        f"💰 موجودی: {sp.wallet_balance}\n📊 کمپین: {campaigns}\n"
        f"🔒 {'مسدود' if sp.is_frozen else 'فعال'}"
    )
    markup = kb(
        [btn("⛔ مسدود", f"adm:spn:ban:{sid}"), btn("🗑 حذف", f"adm:spn:del:{sid}")],
        back=ADM_SPONSORS,
    )
    await edit_screen(callback, body, markup)
    await callback.answer()


@router.callback_query(F.data.startswith("adm:spn:ban:"))
async def sponsor_ban(callback: CallbackQuery, session: AsyncSession):
    sid = int(callback.data.split(":")[3])
    repo = SponsorRepository(session)
    sp = await repo.get_by_id(sid)
    if sp:
        sp.is_frozen = True
        await session.commit()
    await callback.answer("مسدود شد ✅", show_alert=True)
    await sponsors_list(callback, session)


@router.callback_query(F.data.startswith("adm:spn:del:"))
async def sponsor_del(callback: CallbackQuery, session: AsyncSession):
    sid = int(callback.data.split(":")[3])
    repo = SponsorRepository(session)
    sp = await repo.get_by_id(sid)
    if sp:
        sp.status = SponsorStatus.BANNED
        sp.is_frozen = True
        await session.commit()
    await callback.answer("حذف/مسدود شد ✅", show_alert=True)
    await sponsors_list(callback, session)


# ── Sponsor channels ──────────────────────────────────────────────────────────

@router.callback_query(F.data == ADM_CHANNELS)
async def channels_list(callback: CallbackQuery, session: AsyncSession):
    repo = ChannelRepository(session)
    channels = await repo.get_sponsor_channels(enabled_only=False)
    rows = []
    for ch in channels[:15]:
        status = "✅" if ch.is_enabled else "⛔"
        rows.append([btn(f"{status} {ch.title}", f"adm:ch:view:{ch.id}")])
    rows.append([btn("➕ افزودن کانال", "adm:ch:add")])
    markup = kb(*rows, back=ADM_SETTINGS)
    await edit_screen(callback, "📣 کانال‌های اسپانسری", markup)
    await callback.answer()


@router.callback_query(F.data.startswith("adm:ch:view:"))
async def channel_view(callback: CallbackQuery, session: AsyncSession):
    cid = int(callback.data.split(":")[3])
    repo = ChannelRepository(session)
    ch = await repo.get_sponsor_channel_by_id(cid)
    if not ch:
        await callback.answer("پیدا نشد", show_alert=True)
        return
    budget = "—"
    if ch.campaign:
        budget = str(ch.campaign.remaining_budget)
    body = (
        f"📣 {ch.title}\n💰 پاداش: {ch.reward_amount}\n"
        f"📦 بودجه: {budget}\n{'✅ فعال' if ch.is_enabled else '⛔ متوقف'}"
    )
    markup = kb(
        [btn("⛔ توقف", f"adm:ch:stop:{cid}"), btn("🗑 حذف", f"adm:ch:del:{cid}")],
        back=ADM_CHANNELS,
    )
    await edit_screen(callback, body, markup)
    await callback.answer()


@router.callback_query(F.data.startswith("adm:ch:stop:"))
async def channel_stop(callback: CallbackQuery, session: AsyncSession):
    cid = int(callback.data.split(":")[3])
    repo = ChannelRepository(session)
    ch = await repo.get_sponsor_channel_by_id(cid)
    if ch:
        ch.is_enabled = False
        if ch.campaign:
            ch.campaign.status = CampaignStatus.PAUSED
        await session.commit()
    await callback.answer("متوقف شد ✅", show_alert=True)
    await channels_list(callback, session)


@router.callback_query(F.data.startswith("adm:ch:del:"))
async def channel_del(callback: CallbackQuery, session: AsyncSession):
    cid = int(callback.data.split(":")[3])
    repo = ChannelRepository(session)
    ch = await repo.get_sponsor_channel_by_id(cid)
    if ch:
        ch.is_enabled = False
        await session.delete(ch)
        await session.commit()
    await callback.answer("حذف شد ✅", show_alert=True)
    await channels_list(callback, session)


@router.callback_query(F.data == ADM_SEARCH)
async def search_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SearchWizard.query)
    markup = kb(
        [btn("👤 کاربر (آیدی)", "adm:search:user")],
        [btn("📣 کانال (آیدی DB)", "adm:search:ch")],
        back=ADM_HOME,
    )
    await edit_screen(callback, "🔍 جستجو — نوع را انتخاب کن:", markup)
    await callback.answer()


@router.callback_query(F.data == "adm:search:user")
async def search_user_hint(callback: CallbackQuery, state: FSMContext):
    await state.update_data(search_type="user")
    await state.set_state(SearchWizard.query)
    await edit_screen(callback, "🆔 آیدی عددی کاربر را بفرست:", kb(back=ADM_SEARCH))
    await callback.answer()


@router.callback_query(F.data == "adm:search:ch")
async def search_channel_hint(callback: CallbackQuery, state: FSMContext):
    await state.update_data(search_type="channel")
    await state.set_state(SearchWizard.query)
    await edit_screen(callback, "🆔 آیدی عددی کانال (DB) را بفرست:", kb(back=ADM_SEARCH))
    await callback.answer()


@router.message(SearchWizard.query)
async def search_run(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    kind = data.get("search_type", "user")
    await state.clear()
    try:
        qid = int(message.text.strip())
    except ValueError:
        await message.answer("عدد معتبر بفرست.", reply_markup=kb(back=ADM_SEARCH))
        return
    if kind == "user":
        user = await UserRepository(session).get_by_id(qid)
        if not user:
            await message.answer("کاربر پیدا نشد.", reply_markup=kb(back=ADM_SEARCH))
            return
        body = (
            f"👤 {user.first_name or user.username}\n"
            f"🆔 {user.id}\n💰 {user.token_balance} توکن\n"
            f"{'🚫 بن' if user.is_banned else '✅ فعال'}"
        )
    else:
        ch = await ChannelRepository(session).get_sponsor_channel_by_id(qid)
        if not ch:
            await message.answer("کانال پیدا نشد.", reply_markup=kb(back=ADM_SEARCH))
            return
        body = f"📣 {ch.title}\n💰 {ch.reward_amount}\n{'✅' if ch.is_enabled else '⛔'}"
    await message.answer(body, reply_markup=kb(back=ADM_SEARCH))


# ── Pending receipts ──────────────────────────────────────────────────────────

@router.callback_query(F.data == ADM_RECEIPTS)
async def receipts_list(callback: CallbackQuery, session: AsyncSession):
    repo = SponsorRepository(session)
    receipts = await repo.get_pending_receipts()
    if not receipts:
        await edit_screen(callback, "درخواست شارژ pending نیست.", kb(back=ADM_HOME))
        await callback.answer()
        return
    for p in receipts:
        uid = p.sponsor.user_id if p.sponsor else "?"
        markup = kb(
            [btn("✅ تایید", f"adm:rcpt:ok:{p.id}"), btn("❌ رد", f"adm:rcpt:no:{p.id}")],
        )
        cap = (
            f"📸 درخواست #{p.id}\n👤 {uid}\n"
            f"🎁 {p.token_amount} توکن\n💵 {p.receipt_note or ''}"
        )
        if p.receipt_file_id:
            await callback.message.answer_photo(p.receipt_file_id, caption=cap, reply_markup=markup)
        else:
            await callback.message.answer(cap, reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data.startswith("adm:rcpt:ok:"))
async def receipt_approve(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    pid = int(callback.data.split(":")[3])
    svc = ManualPaymentService(session)
    payment = await svc.sponsors.get_payment(pid)
    if await svc.approve_receipt(pid, callback.from_user.id):
        if payment and payment.sponsor:
            try:
                texts = await _t(session)
                await bot.send_message(
                    payment.sponsor.user_id,
                    await texts.t("wallet_deposit_approved", amount=payment.token_amount),
                )
            except Exception:
                pass
        await callback.answer("✅ تایید شد", show_alert=True)
    else:
        await callback.answer("خطا", show_alert=True)


@router.callback_query(F.data.startswith("adm:rcpt:no:"))
async def receipt_reject(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    pid = int(callback.data.split(":")[3])
    svc = ManualPaymentService(session)
    payment = await svc.sponsors.get_payment(pid)
    if await svc.reject_receipt(pid, callback.from_user.id):
        if payment and payment.sponsor:
            try:
                texts = await _t(session)
                await bot.send_message(
                    payment.sponsor.user_id,
                    await texts.t("wallet_deposit_rejected"),
                )
            except Exception:
                pass
        await callback.answer("رد شد ❌", show_alert=True)


# ── Delegates to sub-modules ──────────────────────────────────────────────────

@router.callback_query(F.data == ADM_TEXTS)
async def texts_delegate(callback: CallbackQuery, session: AsyncSession):
    from app.bot.handlers.admin.texts_admin import _text_list_kb
    await edit_screen(callback, "📝 مدیریت متن‌ها", _text_list_kb(0))
    await callback.answer()


@router.callback_query(F.data == ADM_SHOP)
async def shop_delegate(callback: CallbackQuery, session: AsyncSession):
    markup = kb(
        [btn("📂 دسته‌بندی", "adm:shop:cats"), btn("➕ افزودن کانفیگ", "adm:shop:addcfg")],
        back=ADM_SETTINGS,
    )
    await edit_screen(callback, "🛒 مدیریت فروشگاه", markup)
    await callback.answer()


@router.callback_query(F.data == "adm:shop:cats")
async def shop_cats(callback: CallbackQuery, session: AsyncSession):
    from app.bot.handlers.admin.shop_admin import categories_menu_inline
    await categories_menu_inline(callback, session)


@router.callback_query(F.data == "adm:shop:addcfg")
async def shop_addcfg(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    from app.bot.handlers.admin.shop_admin import add_config_start_inline
    await add_config_start_inline(callback, session, state)
