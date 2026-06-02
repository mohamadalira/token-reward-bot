import logging
from typing import Optional

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.locales import get_i18n
from app.models import CampaignStatus, SponsorStatus, TokenActionType
from app.repositories import (
    ChannelRepository,
    SettingsRepository,
    ShopRepository,
    SponsorRepository,
    UserRepository,
)
from app.utils.formatters import format_date, format_number
from app.utils.telegram_helpers import check_channel_membership

logger = logging.getLogger(__name__)
settings = get_settings()
i18n = get_i18n()


class TokenService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.users = UserRepository(session)
        self.settings = SettingsRepository(session)

    async def _format_settings(self) -> tuple[bool, bool]:
        use_persian = await self.settings.get_bool("use_persian_numbers", True)
        use_jalali = await self.settings.get_bool("use_jalali_dates", True)
        return use_persian, use_jalali

    async def get_profile_text(self, user_id: int) -> str:
        user = await self.users.get_by_id(user_id)
        if not user:
            return i18n.t("error")
        use_persian, use_jalali = await self._format_settings()
        rank = await self.users.get_user_rank(user_id)
        name = user.first_name or user.username or str(user.id)
        return i18n.t(
            "profile",
            id=format_number(user.id, use_persian),
            name=name,
            balance=format_number(user.token_balance, use_persian),
            earned=format_number(user.total_earned, use_persian),
            spent=format_number(user.total_spent, use_persian),
            referrals=format_number(user.referral_count, use_persian),
            join_date=format_date(user.created_at, use_jalali, use_persian),
            rank=format_number(rank, use_persian),
        )


class ReferralService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.users = UserRepository(session)
        self.settings = SettingsRepository(session)

    async def process_referral(
        self, bot: Bot, referrer_id: int, referred_id: int
    ) -> Optional[int]:
        if referrer_id == referred_id:
            return None

        mode = await self.settings.get("bot_mode", "combined")
        referral_enabled = await self.settings.get_bool("referral_mode_enabled", True)
        if mode == "task" or not referral_enabled:
            return None

        existing = await self.users.get_referral_by_referred(referred_id)
        if existing:
            return None

        referrer = await self.users.get_by_id(referrer_id)
        referred = await self.users.get_by_id(referred_id)
        if not referrer or not referred or referred.is_fake:
            return None

        reward = await self.settings.get_int("referral_reward", 50)
        await self.users.create_referral(referrer_id, referred_id, reward)
        referrer.referral_count += 1
        await self.users.add_tokens(
            referrer_id,
            reward,
            TokenActionType.REFERRAL_REWARD,
            reason=f"referral:{referred_id}",
        )
        await self.session.commit()

        try:
            await bot.send_message(
                referrer_id,
                i18n.t("referral_reward", amount=reward),
            )
        except Exception as e:
            logger.warning("Failed to notify referrer %s: %s", referrer_id, e)

        for admin_id in settings.admin_id_list:
            try:
                await bot.send_message(
                    admin_id,
                    i18n.t(
                        "referral_admin_notify",
                        referrer=referrer_id,
                        user=referred_id,
                    ),
                )
            except Exception:
                pass

        return reward

    async def get_referral_link(self, user_id: int) -> str:
        user = await self.users.get_by_id(user_id)
        if not user:
            return ""
        bot_username = await self.settings.get("bot_username", "")
        if not bot_username:
            return f"?start=ref_{user.referral_code}"
        return f"https://t.me/{bot_username}?start=ref_{user.referral_code}"


class TaskService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.channels = ChannelRepository(session)
        self.users = UserRepository(session)
        self.sponsors = SponsorRepository(session)
        self.settings = SettingsRepository(session)

    async def get_available_tasks(self):
        mode = await self.settings.get("bot_mode", "combined")
        task_enabled = await self.settings.get_bool("task_mode_enabled", True)
        if mode == "referral" or not task_enabled:
            return []
        return await self.channels.get_sponsor_channels(enabled_only=True)

    async def verify_task(
        self, bot: Bot, user_id: int, channel_db_id: int
    ) -> tuple[bool, str, int]:
        channel = await self.channels.get_sponsor_channel_by_id(channel_db_id)
        if not channel:
            return False, i18n.t("error"), 0

        if await self.channels.has_task_reward(user_id, channel_db_id):
            return False, i18n.t("task_already_done"), 0

        is_member = await check_channel_membership(bot, user_id, channel.channel_id)
        if not is_member:
            return False, i18n.t("membership_fail"), 0

        reward = channel.reward_amount

        if channel.campaign_id:
            campaign = await self.sponsors.get_campaign(channel.campaign_id)
            if campaign and campaign.status == CampaignStatus.ACTIVE:
                if await self.sponsors.has_campaign_reward(user_id, channel_db_id):
                    return False, i18n.t("task_already_done"), 0
                if campaign.remaining_budget < campaign.reward_per_join:
                    return False, i18n.t("error"), 0
                reward = campaign.reward_per_join
                campaign.remaining_budget -= reward
                campaign.distributed_tokens += reward
                campaign.total_joins += 1
                if campaign.remaining_budget < campaign.reward_per_join:
                    campaign.status = CampaignStatus.EXHAUSTED
                    channel.is_enabled = False
                await self.sponsors.create_campaign_reward(
                    campaign.id, channel_db_id, user_id, reward
                )
                sponsor = await self.sponsors.get_by_id(campaign.sponsor_id)
                if sponsor:
                    sponsor.total_consumed += reward
                    try:
                        await bot.send_message(
                            sponsor.user_id,
                            i18n.t(
                                "campaign_join_notify",
                                user_id=user_id,
                                username=user_id,
                                reward=reward,
                                balance=campaign.remaining_budget,
                            ),
                        )
                    except Exception:
                        pass
                    if campaign.status == CampaignStatus.EXHAUSTED:
                        try:
                            await bot.send_message(
                                sponsor.user_id,
                                i18n.t("campaign_exhausted"),
                            )
                        except Exception:
                            pass

        await self.channels.create_task_reward(user_id, channel_db_id, reward)
        await self.users.add_tokens(
            user_id, reward, TokenActionType.TASK_REWARD, reason=f"channel:{channel_db_id}"
        )
        await self.session.commit()
        return True, i18n.t("task_reward", amount=reward), reward


class ShopService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.shop = ShopRepository(session)
        self.users = UserRepository(session)

    async def purchase(self, user_id: int, product_id: int) -> tuple[bool, str, Optional[str]]:
        product = await self.shop.get_product(product_id)
        if not product or not product.is_active:
            return False, i18n.t("error"), None
        if product.stock <= 0:
            return False, i18n.t("out_of_stock"), None

        user = await self.users.get_by_id(user_id)
        if not user or user.token_balance < product.token_cost:
            return False, i18n.t("not_enough_tokens"), None

        await self.users.remove_tokens(
            user_id,
            product.token_cost,
            TokenActionType.PURCHASE,
            reason=f"product:{product_id}",
        )
        product.stock -= 1
        await self.shop.create_purchase(
            user_id, product_id, product.token_cost, product.config_data
        )
        await self.session.commit()
        return True, i18n.t("purchase_success"), product.config_data
