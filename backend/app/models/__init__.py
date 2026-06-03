import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class BotMode(str, enum.Enum):
    REFERRAL = "referral"
    TASK = "task"
    COMBINED = "combined"


class ConfigType(str, enum.Enum):
    V2RAY = "v2ray"
    VLESS = "vless"
    VMESS = "vmess"
    TROJAN = "trojan"
    SHADOWSOCKS = "shadowsocks"
    WIREGUARD = "wireguard"
    OPENVPN = "openvpn"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    APPROVED = "approved"


class PaymentMethod(str, enum.Enum):
    PLISIO = "plisio"
    MANUAL_CARD = "manual_card"
    WALLET = "wallet"


class CampaignStatus(str, enum.Enum):
    PENDING_APPROVAL = "pending_approval"
    PAYMENT_PENDING = "payment_pending"
    ACTIVE = "active"
    PAUSED = "paused"
    EXHAUSTED = "exhausted"
    CANCELLED = "cancelled"


class SponsorStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    BANNED = "banned"


class TokenActionType(str, enum.Enum):
    REFERRAL_REWARD = "referral_reward"
    TASK_REWARD = "task_reward"
    PURCHASE = "purchase"
    ADMIN_ADD = "admin_add"
    ADMIN_REMOVE = "admin_remove"
    ADMIN_SET = "admin_set"
    CAMPAIGN_DEDUCT = "campaign_deduct"
    WALLET_PURCHASE = "wallet_purchase"
    WALLET_TRANSFER = "wallet_transfer"
    REFUND = "refund"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    language_code: Mapped[str] = mapped_column(String(10), default="fa")
    referral_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    referred_by_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=True
    )
    token_balance: Mapped[int] = mapped_column(Integer, default=0)
    total_earned: Mapped[int] = mapped_column(Integer, default=0)
    total_spent: Mapped[int] = mapped_column(Integer, default=0)
    referral_count: Mapped[int] = mapped_column(Integer, default=0)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    is_fake: Mapped[bool] = mapped_column(Boolean, default=False)
    is_sponsor: Mapped[bool] = mapped_column(Boolean, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    last_active: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    referrals: Mapped[list["Referral"]] = relationship(
        "Referral", back_populates="referrer", foreign_keys="Referral.referrer_id"
    )
    token_transactions: Mapped[list["TokenTransaction"]] = relationship(
        "TokenTransaction", back_populates="user"
    )
    purchases: Mapped[list["Purchase"]] = relationship("Purchase", back_populates="user")
    sponsor_profile: Mapped[Optional["Sponsor"]] = relationship(
        "Sponsor", back_populates="user", uselist=False
    )


class Referral(Base):
    __tablename__ = "referrals"
    __table_args__ = (UniqueConstraint("referred_id", name="uq_referral_referred"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    referrer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    referred_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    reward_amount: Mapped[int] = mapped_column(Integer, default=0)
    is_rewarded: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    referrer: Mapped["User"] = relationship(
        "User", back_populates="referrals", foreign_keys=[referrer_id]
    )


class TokenTransaction(Base):
    __tablename__ = "token_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    balance_after: Mapped[int] = mapped_column(Integer)
    action_type: Mapped[TokenActionType] = mapped_column(Enum(TokenActionType))
    reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    admin_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    reference_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship("User", back_populates="token_transactions")


class MandatoryChannel(Base):
    __tablename__ = "mandatory_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[str] = mapped_column(String(100), unique=True)
    channel_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    invite_link: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SponsorChannel(Base):
    __tablename__ = "sponsor_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[str] = mapped_column(String(100), unique=True)
    channel_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    invite_link: Mapped[str] = mapped_column(String(500))
    reward_amount: Mapped[int] = mapped_column(Integer, default=0)
    is_admin_managed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    campaign_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("campaigns.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    campaign: Mapped[Optional["Campaign"]] = relationship(
        "Campaign", back_populates="channel"
    )
    rewards: Mapped[list["CampaignReward"]] = relationship(
        "CampaignReward", back_populates="channel"
    )


class ConfigProduct(Base):
    __tablename__ = "config_products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    token_cost: Mapped[int] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String(100), default="general")
    config_type: Mapped[ConfigType] = mapped_column(Enum(ConfigType))
    config_data: Mapped[str] = mapped_column(Text)
    stock: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    purchases: Mapped[list["Purchase"]] = relationship("Purchase", back_populates="product")


class Purchase(Base):
    __tablename__ = "purchases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("config_products.id"))
    token_cost: Mapped[int] = mapped_column(Integer)
    config_data: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship("User", back_populates="purchases")
    product: Mapped["ConfigProduct"] = relationship("ConfigProduct", back_populates="purchases")


class Sponsor(Base):
    __tablename__ = "sponsors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), unique=True)
    status: Mapped[SponsorStatus] = mapped_column(
        Enum(SponsorStatus), default=SponsorStatus.PENDING
    )
    wallet_balance: Mapped[int] = mapped_column(Integer, default=0)
    total_purchased: Mapped[int] = mapped_column(Integer, default=0)
    total_consumed: Mapped[int] = mapped_column(Integer, default=0)
    is_frozen: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship("User", back_populates="sponsor_profile")
    campaigns: Mapped[list["Campaign"]] = relationship("Campaign", back_populates="sponsor")
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="sponsor")


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sponsor_id: Mapped[int] = mapped_column(ForeignKey("sponsors.id"), index=True)
    channel_id: Mapped[str] = mapped_column(String(100))
    channel_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    channel_title: Mapped[str] = mapped_column(String(255))
    invite_link: Mapped[str] = mapped_column(String(500))
    reward_per_join: Mapped[int] = mapped_column(Integer)
    total_budget: Mapped[int] = mapped_column(Integer)
    remaining_budget: Mapped[int] = mapped_column(Integer)
    distributed_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_joins: Mapped[int] = mapped_column(Integer, default=0)
    total_views: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[CampaignStatus] = mapped_column(
        Enum(CampaignStatus), default=CampaignStatus.PENDING_APPROVAL
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    sponsor: Mapped["Sponsor"] = relationship("Sponsor", back_populates="campaigns")
    channel: Mapped[Optional["SponsorChannel"]] = relationship(
        "SponsorChannel", back_populates="campaign", uselist=False
    )
    rewards: Mapped[list["CampaignReward"]] = relationship(
        "CampaignReward", back_populates="campaign"
    )
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="campaign")
    views: Mapped[list["CampaignView"]] = relationship("CampaignView", back_populates="campaign")


class CampaignReward(Base):
    __tablename__ = "campaign_rewards"
    __table_args__ = (
        UniqueConstraint("user_id", "channel_id", name="uq_campaign_reward_user_channel"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), index=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("sponsor_channels.id"))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    reward_amount: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="rewards")
    channel: Mapped["SponsorChannel"] = relationship(
        "SponsorChannel", back_populates="rewards"
    )


class CampaignView(Base):
    __tablename__ = "campaign_views"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="views")


class TaskReward(Base):
    __tablename__ = "task_rewards"
    __table_args__ = (
        UniqueConstraint("user_id", "channel_id", name="uq_task_reward_user_channel"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    channel_id: Mapped[int] = mapped_column(ForeignKey("sponsor_channels.id"))
    reward_amount: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sponsor_id: Mapped[int] = mapped_column(ForeignKey("sponsors.id"), index=True)
    campaign_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("campaigns.id"), nullable=True
    )
    amount_usd: Mapped[float] = mapped_column(Float)
    token_amount: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(20), default="USD")
    method: Mapped[PaymentMethod] = mapped_column(Enum(PaymentMethod))
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus), default=PaymentStatus.PENDING
    )
    plisio_invoice_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    plisio_txn_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    receipt_file_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    receipt_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    admin_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    sponsor: Mapped["Sponsor"] = relationship("Sponsor", back_populates="payments")
    campaign: Mapped[Optional["Campaign"]] = relationship(
        "Campaign", back_populates="payments"
    )


class Setting(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AdminLog(Base):
    __tablename__ = "admin_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_id: Mapped[int] = mapped_column(BigInteger, index=True)
    action: Mapped[str] = mapped_column(String(100))
    target_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    target_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
