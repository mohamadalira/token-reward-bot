"""Admin: add sponsor channel + campaign directly."""

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters.admin import AdminFilter
from app.core.config import get_settings
from app.locales import get_i18n
from app.models import CampaignStatus, SponsorStatus
from app.repositories import SponsorRepository, UserRepository
from app.services import SponsorService

router = Router(name="admin_sponsor_channels")
router.message.filter(AdminFilter())
i18n = get_i18n()
settings = get_settings()


class AdminSponsorChannelStates(StatesGroup):
    link = State()
    reward = State()
    description = State()
    budget = State()


@router.message(F.text == i18n.t("btn_add_sponsor_channel"))
async def add_sponsor_channel_start(message: Message, state: FSMContext):
    await state.set_state(AdminSponsorChannelStates.link)
    await message.answer("لینک یا @username کانال رو بفرست:")


@router.message(AdminSponsorChannelStates.link)
async def add_channel_link(message: Message, state: FSMContext):
    await state.update_data(channel_link=message.text.strip())
    await state.set_state(AdminSponsorChannelStates.reward)
    await message.answer("توکن پاداش برای هر عضو:")


@router.message(AdminSponsorChannelStates.reward)
async def add_channel_reward(message: Message, state: FSMContext):
    try:
        reward = int(message.text.strip())
    except ValueError:
        await message.answer("عدد بفرست")
        return
    await state.update_data(reward=reward)
    await state.set_state(AdminSponsorChannelStates.description)
    await message.answer("توضیح کانال (برای کاربران):")


@router.message(AdminSponsorChannelStates.description)
async def add_channel_desc(message: Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    await state.set_state(AdminSponsorChannelStates.budget)
    await message.answer("بودجه کمپین (توکن) — 0 برای نامحدود ادمینی:")


@router.message(AdminSponsorChannelStates.budget)
async def add_channel_budget(
    message: Message, state: FSMContext, session: AsyncSession, bot: Bot
):
    try:
        budget = int(message.text.strip())
    except ValueError:
        await message.answer("عدد بفرست")
        return
    data = await state.get_data()
    admin_id = settings.admin_id_list[0] if settings.admin_id_list else message.from_user.id
    users = UserRepository(session)
    sponsors = SponsorRepository(session)
    sponsor = await sponsors.get_by_user_id(admin_id)
    if not sponsor:
        sponsor = await sponsors.create(admin_id)
        user = await users.get_by_id(admin_id)
        if user:
            user.is_sponsor = True
        sponsor.status = SponsorStatus.APPROVED

    svc = SponsorService(session)
    channel_ref = data["channel_link"]
    if not channel_ref.startswith("@"):
        channel_ref = channel_ref if channel_ref.startswith("-") else f"@{channel_ref.lstrip('@')}"

    if budget > 0:
        ok, msg, cid = await svc.create_campaign(
            admin_id, channel_ref, data["reward"], budget, bot, use_wallet=False
        )
        if ok and cid:
            campaign = await sponsors.get_campaign(cid)
            if campaign and campaign.channel:
                campaign.channel.description = data["description"]
                campaign.channel.is_admin_managed = True
                campaign.status = CampaignStatus.ACTIVE
            await session.commit()
        await state.clear()
        await message.answer(msg if ok else f"❌ {msg}")
        return

    ok, error, info = await svc.validate_campaign_channel(bot, channel_ref)
    if not ok or not info:
        await message.answer(f"❌ {error}")
        return
    ch = await sponsors.create_sponsor_channel(
        channel_id=info["channel_id"],
        channel_username=info.get("username"),
        title=info["title"],
        invite_link=info["invite_link"],
        reward_amount=data["reward"],
        description=data["description"],
        is_admin_managed=True,
    )
    await session.commit()
    await state.clear()
    await message.answer(f"✅ کانال #{ch.id} اضافه شد — {data['reward']} توکن/عضو")
