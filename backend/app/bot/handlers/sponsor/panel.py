from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.main import sponsor_menu_keyboard
from app.locales import get_i18n
from app.repositories import SponsorRepository
from app.services import ManualPaymentService, PlisioService, SponsorService

router = Router(name="sponsor")
i18n = get_i18n()


class SponsorStates(StatesGroup):
    campaign_channel = State()
    campaign_reward = State()
    campaign_budget = State()
    deposit_amount = State()
    receipt_upload = State()


@router.message(F.text == i18n.t("sponsor_menu"))
async def sponsor_menu(message: Message):
    await message.answer(i18n.t("sponsor_menu"), reply_markup=sponsor_menu_keyboard())


@router.message(F.text == i18n.t("btn_become_sponsor"))
async def become_sponsor(message: Message, session: AsyncSession):
    svc = SponsorService(session)
    ok, msg = await svc.request_sponsor(message.from_user.id)
    await message.answer(msg)


@router.message(F.text == i18n.t("btn_my_campaigns"))
async def my_campaigns(message: Message, session: AsyncSession):
    repo = SponsorRepository(session)
    sponsor = await repo.get_by_user_id(message.from_user.id)
    if not sponsor:
        await message.answer("اول اسپانسر شو 🚀")
        return
    if not sponsor.campaigns:
        await message.answer("کمپینی نداری 😕\n/new_campaign برای ساخت")
        return
    for c in sponsor.campaigns:
        remaining_joins = c.remaining_budget // c.reward_per_join if c.reward_per_join else 0
        conv = (c.total_joins / c.total_views * 100) if c.total_views else 0
        await message.answer(
            f"📊 {c.channel_title}\n"
            f"💰 پاداش: {c.reward_per_join} توکن\n"
            f"📦 بودجه: {c.total_budget} | باقی: {c.remaining_budget}\n"
            f"👥 عضویت: {c.total_joins} | 👁 {c.total_views}\n"
            f"📈 نرخ تبدیل: {conv:.1f}%\n"
            f"🎯 عضویت باقی: {remaining_joins}\n"
            f"📌 وضعیت: {c.status.value}\n\n"
            f"/pause_campaign {c.id}\n/resume_campaign {c.id}\n/recharge_campaign {c.id} AMOUNT"
        )


@router.message(F.text.startswith("/new_campaign"))
async def new_campaign(message: Message, state: FSMContext):
    await message.answer("🔗 لینک یا آیدی کانال رو بفرست:")
    await state.set_state(SponsorStates.campaign_channel)


@router.message(SponsorStates.campaign_channel)
async def campaign_channel(message: Message, state: FSMContext):
    await state.update_data(channel=message.text.strip())
    await state.set_state(SponsorStates.campaign_reward)
    await message.answer("💰 پاداش هر عضویت (توکن):")


@router.message(SponsorStates.campaign_reward)
async def campaign_reward(message: Message, state: FSMContext):
    await state.update_data(reward=int(message.text))
    await state.set_state(SponsorStates.campaign_budget)
    await message.answer("📦 بودجه کل کمپین (توکن):")


@router.message(SponsorStates.campaign_budget)
async def campaign_budget(message: Message, state: FSMContext, session: AsyncSession, bot):
    budget = int(message.text)
    data = await state.get_data()
    svc = SponsorService(session)
    ok, msg, campaign_id = await svc.create_campaign(
        message.from_user.id,
        data["channel"],
        data["reward"],
        budget,
        bot,
        use_wallet=False,
    )
    await state.clear()
    if ok and campaign_id:
        plisio = PlisioService(session)
        settings_repo = __import__("app.repositories.settings_repo", fromlist=["SettingsRepository"]).SettingsRepository(session)
        token_price = await settings_repo.get_float("token_price_usd", 0.01)
        amount_usd = budget * token_price
        ok2, invoice_url, info = await plisio.create_invoice(
            (await repo_get_sponsor(session, message.from_user.id)).id,
            amount_usd,
            campaign_id,
        )
        if ok2:
            await message.answer(f"{msg}\n\n💳 لینک پرداخت:\n{invoice_url}")
        else:
            await message.answer(msg)
    else:
        await message.answer(msg)


async def repo_get_sponsor(session, user_id):
    from app.repositories import SponsorRepository
    return await SponsorRepository(session).get_by_user_id(user_id)


@router.message(F.text.startswith("/pause_campaign"))
async def pause_campaign(message: Message, session: AsyncSession):
    campaign_id = int(message.text.split()[1])
    svc = SponsorService(session)
    if await svc.pause_campaign(campaign_id, message.from_user.id):
        await message.answer(i18n.t("done"))
    else:
        await message.answer(i18n.t("error"))


@router.message(F.text.startswith("/resume_campaign"))
async def resume_campaign(message: Message, session: AsyncSession):
    campaign_id = int(message.text.split()[1])
    svc = SponsorService(session)
    if await svc.resume_campaign(campaign_id, message.from_user.id):
        await message.answer(i18n.t("done"))
    else:
        await message.answer(i18n.t("error"))


@router.message(F.text.startswith("/recharge_campaign"))
async def recharge_campaign(message: Message, session: AsyncSession):
    parts = message.text.split()
    campaign_id, amount = int(parts[1]), int(parts[2])
    svc = SponsorService(session)
    ok, msg = await svc.recharge_campaign(campaign_id, message.from_user.id, amount)
    await message.answer(msg)


@router.message(F.text == i18n.t("btn_deposit"))
async def deposit(message: Message, state: FSMContext):
    await message.answer("💳 مبلغ شارژ (دلار):")
    await state.set_state(SponsorStates.deposit_amount)


@router.message(SponsorStates.deposit_amount)
async def deposit_amount(message: Message, state: FSMContext, session: AsyncSession):
    amount = float(message.text)
    sponsor = await repo_get_sponsor(session, message.from_user.id)
    if not sponsor:
        await message.answer("اول اسپانسر شو")
        await state.clear()
        return
    plisio = PlisioService(session)
    ok, url, _ = await plisio.create_invoice(sponsor.id, amount)
    await state.clear()
    if ok:
        await message.answer(f"💳 لینک پرداخت:\n{url}")
    else:
        await message.answer(url)


@router.message(F.text == i18n.t("btn_sponsor_stats"))
async def sponsor_stats(message: Message, session: AsyncSession):
    svc = SponsorService(session)
    text = await svc.get_wallet_info(message.from_user.id)
    await message.answer(text)
