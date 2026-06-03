from typing import Any, Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Setting


DEFAULT_SETTINGS: dict[str, str] = {
    "bot_mode": "combined",
    "referral_reward": "50",
    "token_price_usd": "0.01",
    "welcome_message": "به ربات خوش اومدی 👋",
    "support_username": "support",
    "rules_text": "قوانین استفاده از ربات",
    "force_join_enabled": "true",
    "use_persian_numbers": "true",
    "use_jalali_dates": "true",
    "min_campaign_tokens": "1000",
    "max_campaign_tokens": "1000000",
    "min_reward_per_join": "5",
    "max_reward_per_join": "500",
    "min_budget_enabled": "true",
    "campaign_expiration_days": "30",
    "plisio_enabled": "true",
    "manual_card_enabled": "false",
    "manual_card_number": "",
    "manual_card_holder": "",
    "manual_bank_name": "",
    "manual_payment_instructions": "بعد از پرداخت رسید رو بفرست",
    "referral_mode_enabled": "true",
    "task_mode_enabled": "true",
    "sponsor_mode_enabled": "true",
    "min_token_purchase": "1000",
    "max_token_purchase": "1000000",
    "plisio_api_key": "",
}


class SettingsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, key: str, default: Optional[str] = None) -> str:
        result = await self.session.execute(
            select(Setting).where(Setting.key == key)
        )
        setting = result.scalar_one_or_none()
        if setting:
            return setting.value
        return default if default is not None else DEFAULT_SETTINGS.get(key, "")

    async def get_bool(self, key: str, default: bool = False) -> bool:
        val = await self.get(key, str(default).lower())
        return val.lower() in ("true", "1", "yes")

    async def get_int(self, key: str, default: int = 0) -> int:
        val = await self.get(key, str(default))
        try:
            return int(val)
        except ValueError:
            return default

    async def get_float(self, key: str, default: float = 0.0) -> float:
        val = await self.get(key, str(default))
        try:
            return float(val)
        except ValueError:
            return default

    async def set(self, key: str, value: str) -> None:
        result = await self.session.execute(
            select(Setting).where(Setting.key == key)
        )
        setting = result.scalar_one_or_none()
        if setting:
            setting.value = value
        else:
            self.session.add(Setting(key=key, value=value))
        await self.session.flush()

    async def get_all(self) -> dict[str, str]:
        result = await self.session.execute(select(Setting))
        settings = {s.key: s.value for s in result.scalars().all()}
        merged = {**DEFAULT_SETTINGS, **settings}
        return merged

    async def init_defaults(self) -> None:
        from app.locales import fa

        merged = {**DEFAULT_SETTINGS, **fa.MESSAGES}
        for key, value in merged.items():
            result = await self.session.execute(
                select(Setting).where(Setting.key == key)
            )
            if not result.scalar_one_or_none():
                self.session.add(Setting(key=key, value=value))
        await self.session.flush()
