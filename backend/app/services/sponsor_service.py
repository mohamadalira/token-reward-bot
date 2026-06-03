import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.locales import get_i18n
from app.models import CampaignStatus, PaymentMethod, PaymentStatus, SponsorStatus
from app.repositories import SettingsRepository, SponsorRepository, UserRepository
from app.utils.channel_resolver import validate_channel_for_bot

logger = logging.getLogger(__name__)
settings = get_settings()
i18n = get_i18n()


class SponsorService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.sponsors = SponsorRepository(session)
        self.users = UserRepository(session)
        self.settings_repo = SettingsRepository(session)

    async def ensure_sponsor(self, user_id: int) -> tuple[bool, str]:
        """Auto-approve sponsor — no admin approval required."""
        existing = await self.sponsors.get_by_user_id(user_id)
        if existing:
            if existing.status == SponsorStatus.BANNED or existing.is_frozen:
                return False, i18n.t("banned")
            if existing.status != SponsorStatus.APPROVED:
                existing.status = SponsorStatus.APPROVED
        else:
            existing = await self.sponsors.create(user_id)
            existing.status = SponsorStatus.APPROVED
        user = await self.users.get_by_id(user_id)
        if user:
            user.is_sponsor = True
        await self.session.commit()
        return True, i18n.t("sponsor_approved")

    async def request_sponsor(self, user_id: int) -> tuple[bool, str]:
        return await self.ensure_sponsor(user_id)

    async def approve_sponsor(self, sponsor_id: int, admin_id: int) -> None:
        sponsor = await self.sponsors.get_by_id(sponsor_id)
        if sponsor:
            sponsor.status = SponsorStatus.APPROVED
            await self.users.log_admin_action(admin_id, "approve_sponsor", "sponsor", str(sponsor_id))
            await self.session.commit()

    async def get_wallet_info(self, user_id: int) -> str:
        sponsor = await self.sponsors.get_by_user_id(user_id)
        if not sponsor:
            return i18n.t("error")
        allocated = sum(
            c.remaining_budget for c in sponsor.campaigns
            if c.status in (CampaignStatus.ACTIVE, CampaignStatus.PAUSED)
        )
        available = sponsor.wallet_balance - allocated
        return i18n.t(
            "wallet_info",
            balance=sponsor.wallet_balance,
            purchased=sponsor.total_purchased,
            consumed=sponsor.total_consumed,
            allocated=allocated,
            available=max(0, available),
        )

    async def get_dashboard_text(self, user_id: int) -> str:
        sponsor = await self.sponsors.get_by_user_id(user_id)
        if not sponsor:
            return i18n.t("error")
        active = [
            c for c in sponsor.campaigns
            if c.status == CampaignStatus.ACTIVE
        ]
        total_joins = sum(c.total_joins for c in sponsor.campaigns)
        total_views = sum(c.total_views for c in sponsor.campaigns)
        conv = (total_joins / total_views * 100) if total_views else 0
        remaining = sum(c.remaining_budget for c in active)
        wallet = await self.get_wallet_info(user_id)
        return i18n.t(
            "sponsor_dashboard",
            wallet=wallet,
            joins=total_joins,
            conversion=f"{conv:.1f}",
            remaining=remaining,
            active_campaigns=len(active),
        )

    async def validate_campaign_channel(
        self, bot: Bot, channel_id: str
    ) -> tuple[bool, Optional[str], Optional[dict]]:
        ok, error, info = await validate_channel_for_bot(bot, channel_id)
        if not ok:
            logger.warning("validate_campaign_channel failed: %s", error)
        return ok, error, info

    async def create_campaign_from_info(
        self,
        user_id: int,
        channel_info: dict,
        reward_per_join: int,
        total_budget: int,
        bot: Bot,
        use_wallet: bool = True,
    ) -> tuple[bool, str, Optional[int]]:
        return await self.create_campaign(
            user_id,
            channel_info.get("channel_id", ""),
            reward_per_join,
            total_budget,
            bot,
            use_wallet=use_wallet,
            channel_info=channel_info,
        )

    async def create_campaign(
        self,
        user_id: int,
        channel_id: str,
        reward_per_join: int,
        total_budget: int,
        bot: Bot,
        use_wallet: bool = False,
        channel_info: Optional[dict] = None,
    ) -> tuple[bool, str, Optional[int]]:
        await self.ensure_sponsor(user_id)
        sponsor = await self.sponsors.get_by_user_id(user_id)
        if not sponsor or sponsor.status != SponsorStatus.APPROVED:
            return False, i18n.t("error"), None
        if sponsor.is_frozen:
            return False, i18n.t("banned"), None

        min_enabled = await self.settings_repo.get_bool("min_budget_enabled", True)
        if min_enabled:
            min_budget = await self.settings_repo.get_int("min_campaign_tokens", 1000)
            if total_budget < min_budget:
                return False, i18n.t("min_budget_error", min=min_budget), None

        max_budget = await self.settings_repo.get_int("max_campaign_tokens", 1000000)
        if total_budget > max_budget:
            return False, f"حداکثر بودجه {max_budget} توکنه", None

        min_reward = await self.settings_repo.get_int("min_reward_per_join", 5)
        max_reward = await self.settings_repo.get_int("max_reward_per_join", 500)
        if reward_per_join < min_reward or reward_per_join > max_reward:
            return False, f"پاداش باید بین {min_reward} تا {max_reward} باشه", None

        if not channel_info:
            ok, error, channel_info = await self.validate_campaign_channel(bot, channel_id)
            if not ok:
                return False, i18n.t("campaign_validation_fail", error=error), None

        exp_days = await self.settings_repo.get_int("campaign_expiration_days", 30)
        expires_at = datetime.now(timezone.utc) + timedelta(days=exp_days)

        if use_wallet:
            allocated = sum(
                c.remaining_budget for c in sponsor.campaigns
                if c.status in (CampaignStatus.ACTIVE, CampaignStatus.PAUSED)
            )
            available = sponsor.wallet_balance - allocated
            if available < total_budget:
                return False, i18n.t("not_enough_tokens"), None

        status = CampaignStatus.ACTIVE if use_wallet else CampaignStatus.PAYMENT_PENDING
        campaign = await self.sponsors.create_campaign(
            sponsor_id=sponsor.id,
            channel_id=channel_info["channel_id"],
            channel_username=channel_info.get("username"),
            channel_title=channel_info["title"],
            invite_link=channel_info["invite_link"],
            reward_per_join=reward_per_join,
            total_budget=total_budget,
            remaining_budget=total_budget,
            status=status,
            expires_at=expires_at,
        )

        await self.sponsors.create_sponsor_channel(
            channel_id=channel_info["channel_id"],
            channel_username=channel_info.get("username"),
            title=channel_info["title"],
            invite_link=channel_info["invite_link"],
            reward_amount=reward_per_join,
            campaign_id=campaign.id,
            is_admin_managed=False,
        )

        if use_wallet:
            sponsor.total_consumed += total_budget
        await self.session.commit()

        for admin_id in settings.admin_id_list:
            try:
                notify_bot = Bot(token=settings.bot_token)
                await notify_bot.send_message(
                    admin_id,
                    f"🚀 کمپین جدید #{campaign.id}\n"
                    f"👤 {user_id}\n📣 {channel_info['title']}",
                )
                await notify_bot.session.close()
            except Exception:
                logger.exception("admin campaign notify failed")

        return True, i18n.t("campaign_created"), campaign.id

    async def pause_campaign(self, campaign_id: int, user_id: int) -> bool:
        campaign = await self.sponsors.get_campaign(campaign_id)
        sponsor = await self.sponsors.get_by_user_id(user_id)
        if not campaign or not sponsor or campaign.sponsor_id != sponsor.id:
            return False
        campaign.status = CampaignStatus.PAUSED
        if campaign.channel:
            campaign.channel.is_enabled = False
        await self.session.commit()
        return True

    async def resume_campaign(self, campaign_id: int, user_id: int) -> bool:
        campaign = await self.sponsors.get_campaign(campaign_id)
        sponsor = await self.sponsors.get_by_user_id(user_id)
        if not campaign or not sponsor or campaign.sponsor_id != sponsor.id:
            return False
        if campaign.remaining_budget < campaign.reward_per_join:
            return False
        campaign.status = CampaignStatus.ACTIVE
        if campaign.channel:
            campaign.channel.is_enabled = True
        await self.session.commit()
        return True

    async def recharge_campaign(
        self, campaign_id: int, user_id: int, amount: int
    ) -> tuple[bool, str]:
        campaign = await self.sponsors.get_campaign(campaign_id)
        sponsor = await self.sponsors.get_by_user_id(user_id)
        if not campaign or not sponsor or campaign.sponsor_id != sponsor.id:
            return False, i18n.t("error")
        if sponsor.wallet_balance < amount:
            return False, i18n.t("not_enough_tokens")
        sponsor.wallet_balance -= amount
        sponsor.total_consumed += amount
        campaign.remaining_budget += amount
        campaign.total_budget += amount
        if campaign.status == CampaignStatus.EXHAUSTED:
            campaign.status = CampaignStatus.ACTIVE
            if campaign.channel:
                campaign.channel.is_enabled = True
        await self.session.commit()
        return True, i18n.t("done")

    async def record_campaign_view(self, campaign_id: int, user_id: int) -> None:
        await self.sponsors.record_view(campaign_id, user_id)
        campaign = await self.sponsors.get_campaign(campaign_id)
        if campaign:
            campaign.total_views += 1
        await self.session.commit()
