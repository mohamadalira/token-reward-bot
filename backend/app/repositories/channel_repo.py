from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Campaign,
    CampaignReward,
    CampaignStatus,
    CampaignView,
    ConfigProduct,
    ConfigType,
    MandatoryChannel,
    Payment,
    PaymentStatus,
    Purchase,
    Sponsor,
    SponsorChannel,
    SponsorStatus,
    TaskReward,
)


class ChannelRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_mandatory_channels(self, enabled_only: bool = True) -> list[MandatoryChannel]:
        stmt = select(MandatoryChannel)
        if enabled_only:
            stmt = stmt.where(MandatoryChannel.is_enabled == True)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def add_mandatory(
        self, channel_id: str, title: str, username: Optional[str] = None, invite_link: Optional[str] = None
    ) -> MandatoryChannel:
        ch = MandatoryChannel(
            channel_id=channel_id,
            channel_username=username,
            title=title,
            invite_link=invite_link,
        )
        self.session.add(ch)
        await self.session.flush()
        return ch

    async def remove_mandatory(self, channel_db_id: int) -> None:
        result = await self.session.execute(
            select(MandatoryChannel).where(MandatoryChannel.id == channel_db_id)
        )
        ch = result.scalar_one_or_none()
        if ch:
            await self.session.delete(ch)

    async def clear_all_mandatory(self) -> int:
        result = await self.session.execute(select(MandatoryChannel))
        channels = list(result.scalars().all())
        for ch in channels:
            await self.session.delete(ch)
        return len(channels)

    async def disable_mandatory(self, channel_db_id: int) -> None:
        result = await self.session.execute(
            select(MandatoryChannel).where(MandatoryChannel.id == channel_db_id)
        )
        ch = result.scalar_one_or_none()
        if ch:
            ch.is_enabled = False

    async def get_sponsor_channels(self, enabled_only: bool = True) -> list[SponsorChannel]:
        stmt = select(SponsorChannel).options(selectinload(SponsorChannel.campaign))
        if enabled_only:
            stmt = stmt.where(SponsorChannel.is_enabled == True)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_sponsor_channel_by_id(self, channel_id: int) -> Optional[SponsorChannel]:
        result = await self.session.execute(
            select(SponsorChannel).where(SponsorChannel.id == channel_id)
        )
        return result.scalar_one_or_none()

    async def has_task_reward(self, user_id: int, channel_id: int) -> bool:
        result = await self.session.execute(
            select(TaskReward).where(
                TaskReward.user_id == user_id,
                TaskReward.channel_id == channel_id,
            )
        )
        return result.scalar_one_or_none() is not None

    async def create_task_reward(self, user_id: int, channel_id: int, amount: int) -> TaskReward:
        reward = TaskReward(user_id=user_id, channel_id=channel_id, reward_amount=amount)
        self.session.add(reward)
        await self.session.flush()
        return reward


class ShopRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_products(
        self, active_only: bool = True, category_id: Optional[int] = None
    ) -> list[ConfigProduct]:
        stmt = select(ConfigProduct)
        if category_id is not None:
            stmt = stmt.where(ConfigProduct.category_id == category_id)
        if active_only:
            stmt = stmt.where(ConfigProduct.is_active == True, ConfigProduct.stock > 0)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def bulk_create_from_lines(
        self,
        category_id: int,
        category_name: str,
        token_cost: int,
        lines: list[str],
        config_type: ConfigType = ConfigType.V2RAY,
    ) -> list[ConfigProduct]:
        created = []
        idx = 0
        for line in lines:
            line = line.strip()
            if not line:
                continue
            idx += 1
            product = ConfigProduct(
                name=f"{category_name} #{idx}",
                token_cost=token_cost,
                category=category_name,
                category_id=category_id,
                config_type=config_type,
                config_data=line,
                stock=1,
            )
            self.session.add(product)
            created.append(product)
        await self.session.flush()
        return created

    async def get_product(self, product_id: int) -> Optional[ConfigProduct]:
        result = await self.session.execute(
            select(ConfigProduct).where(ConfigProduct.id == product_id)
        )
        return result.scalar_one_or_none()

    async def create_product(self, **kwargs) -> ConfigProduct:
        product = ConfigProduct(**kwargs)
        self.session.add(product)
        await self.session.flush()
        return product

    async def update_product(self, product_id: int, **kwargs) -> Optional[ConfigProduct]:
        product = await self.get_product(product_id)
        if not product:
            return None
        for k, v in kwargs.items():
            if v is not None:
                setattr(product, k, v)
        await self.session.flush()
        return product

    async def delete_product(self, product_id: int) -> None:
        product = await self.get_product(product_id)
        if product:
            await self.session.delete(product)

    async def create_purchase(
        self, user_id: int, product_id: int, token_cost: int, config_data: str
    ) -> Purchase:
        purchase = Purchase(
            user_id=user_id,
            product_id=product_id,
            token_cost=token_cost,
            config_data=config_data,
        )
        self.session.add(purchase)
        await self.session.flush()
        return purchase

    async def get_user_purchases(self, user_id: int, limit: int = 20) -> list[Purchase]:
        result = await self.session.execute(
            select(Purchase)
            .options(selectinload(Purchase.product))
            .where(Purchase.user_id == user_id)
            .order_by(Purchase.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


class SponsorRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_user_id(self, user_id: int) -> Optional[Sponsor]:
        result = await self.session.execute(
            select(Sponsor)
            .options(selectinload(Sponsor.campaigns))
            .where(Sponsor.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, sponsor_id: int) -> Optional[Sponsor]:
        result = await self.session.execute(
            select(Sponsor)
            .options(selectinload(Sponsor.campaigns), selectinload(Sponsor.user))
            .where(Sponsor.id == sponsor_id)
        )
        return result.scalar_one_or_none()

    async def create(self, user_id: int) -> Sponsor:
        sponsor = Sponsor(user_id=user_id)
        self.session.add(sponsor)
        await self.session.flush()
        return sponsor

    async def count_all(self) -> int:
        result = await self.session.execute(
            select(func.count(Sponsor.id)).where(Sponsor.status == SponsorStatus.APPROVED)
        )
        return result.scalar() or 0

    async def get_pending(self) -> list[Sponsor]:
        result = await self.session.execute(
            select(Sponsor)
            .options(selectinload(Sponsor.user))
            .where(Sponsor.status == SponsorStatus.PENDING)
        )
        return list(result.scalars().all())

    async def create_campaign(self, **kwargs) -> Campaign:
        campaign = Campaign(**kwargs)
        self.session.add(campaign)
        await self.session.flush()
        return campaign

    async def get_campaign(self, campaign_id: int) -> Optional[Campaign]:
        result = await self.session.execute(
            select(Campaign)
            .options(
                selectinload(Campaign.sponsor).selectinload(Sponsor.user),
                selectinload(Campaign.channel),
            )
            .where(Campaign.id == campaign_id)
        )
        return result.scalar_one_or_none()

    async def get_active_campaigns(self) -> list[Campaign]:
        result = await self.session.execute(
            select(Campaign).where(Campaign.status == CampaignStatus.ACTIVE)
        )
        return list(result.scalars().all())

    async def count_active_campaigns(self) -> int:
        result = await self.session.execute(
            select(func.count(Campaign.id)).where(Campaign.status == CampaignStatus.ACTIVE)
        )
        return result.scalar() or 0

    async def has_campaign_reward(self, user_id: int, channel_db_id: int) -> bool:
        result = await self.session.execute(
            select(CampaignReward).where(
                CampaignReward.user_id == user_id,
                CampaignReward.channel_id == channel_db_id,
            )
        )
        return result.scalar_one_or_none() is not None

    async def create_campaign_reward(
        self, campaign_id: int, channel_id: int, user_id: int, amount: int
    ) -> CampaignReward:
        reward = CampaignReward(
            campaign_id=campaign_id,
            channel_id=channel_id,
            user_id=user_id,
            reward_amount=amount,
        )
        self.session.add(reward)
        await self.session.flush()
        return reward

    async def record_view(self, campaign_id: int, user_id: int) -> None:
        self.session.add(CampaignView(campaign_id=campaign_id, user_id=user_id))

    async def create_sponsor_channel(self, **kwargs) -> SponsorChannel:
        ch = SponsorChannel(**kwargs)
        self.session.add(ch)
        await self.session.flush()
        return ch

    async def create_payment(self, **kwargs) -> Payment:
        payment = Payment(**kwargs)
        self.session.add(payment)
        await self.session.flush()
        return payment

    async def get_payment(self, payment_id: int) -> Optional[Payment]:
        result = await self.session.execute(
            select(Payment)
            .options(selectinload(Payment.sponsor).selectinload(Sponsor.user))
            .where(Payment.id == payment_id)
        )
        return result.scalar_one_or_none()

    async def get_payment_by_invoice(self, invoice_id: str) -> Optional[Payment]:
        result = await self.session.execute(
            select(Payment).where(Payment.plisio_invoice_id == invoice_id)
        )
        return result.scalar_one_or_none()

    async def get_pending_receipts(self) -> list[Payment]:
        result = await self.session.execute(
            select(Payment)
            .options(selectinload(Payment.sponsor).selectinload(Sponsor.user))
            .where(Payment.status == PaymentStatus.PENDING, Payment.receipt_file_id.isnot(None))
        )
        return list(result.scalars().all())

    async def count_payments(self) -> int:
        result = await self.session.execute(select(func.count(Payment.id)))
        return result.scalar() or 0

    async def get_revenue_stats(self) -> dict:
        confirmed = await self.session.execute(
            select(func.sum(Payment.amount_usd)).where(
                Payment.status.in_([PaymentStatus.CONFIRMED, PaymentStatus.APPROVED])
            )
        )
        pending = await self.session.execute(
            select(func.count(Payment.id)).where(Payment.status == PaymentStatus.PENDING)
        )
        return {
            "total_revenue": confirmed.scalar() or 0,
            "pending_count": pending.scalar() or 0,
        }
