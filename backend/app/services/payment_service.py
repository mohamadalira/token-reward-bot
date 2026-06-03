import hashlib
import hmac
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import verify_plisio_signature
from app.locales import get_i18n
from app.models import CampaignStatus, PaymentMethod, PaymentStatus
from app.repositories import SettingsRepository, SponsorRepository

logger = logging.getLogger(__name__)
settings = get_settings()
i18n = get_i18n()
PLISIO_API = "https://plisio.net/api/v1"


class PlisioService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.sponsors = SponsorRepository(session)
        self.settings = SettingsRepository(session)

    async def _get_api_key(self) -> str:
        key = await self.settings.get("plisio_api_key", settings.plisio_api_key)
        return key or settings.plisio_api_key

    async def _get_secret(self) -> str:
        """Plisio webhook secret — falls back to API key if no separate secret is set."""
        key = await self.settings.get("plisio_secret_key", settings.plisio_secret_key)
        if key:
            return key
        return await self._get_api_key()

    async def _callback_url(self) -> str:
        custom = await self.settings.get("plisio_callback_url")
        if custom:
            return custom
        if settings.webhook_url:
            return settings.webhook_url
        return f"{settings.webapp_url}{settings.webhook_path}"

    async def test_connection(self) -> tuple[bool, str]:
        api_key = await self._get_api_key()
        if not api_key:
            return False, "API Key تنظیم نشده"
        secret = await self._get_secret()
        callback = await self._callback_url()
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{PLISIO_API}/balances",
                    params={"api_key": api_key},
                )
                data = resp.json()
                if data.get("status") == "success":
                    msg = "اتصال API موفق ✅"
                    if not secret:
                        msg += "\n⚠️ Secret Key تنظیم نشده"
                    msg += f"\n🔗 Callback: {callback}"
                    return True, msg
                err = data.get("data", {}).get("message", "خطا در اتصال")
                if "secret" in err.lower() or "domain" in err.lower():
                    err += "\n\nSecret Key و Callback URL و Domain Verification را در پنل Plisio بررسی کن."
                return False, err
        except Exception as e:
            logger.exception("Plisio test_connection failed")
            return False, str(e)

    async def create_invoice(
        self,
        sponsor_id: int,
        amount_usd: float,
        campaign_id: Optional[int] = None,
        currency: str = "USD",
        psys_cid: str = "BTC",
        token_amount: Optional[int] = None,
    ) -> tuple[bool, str, Optional[dict]]:
        api_key = await self._get_api_key()
        if not api_key:
            return False, "API Key تنظیم نشده", None
        order_name = f"campaign_{campaign_id or 'wallet'}_{sponsor_id}"
        params = {
            "api_key": api_key,
            "order_name": order_name,
            "order_number": f"{sponsor_id}_{campaign_id or 0}_{int(datetime.now().timestamp())}",
            "source_currency": currency,
            "source_amount": amount_usd,
            "currency": psys_cid,
            "callback_url": await self._callback_url(),
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(f"{PLISIO_API}/invoices/new", params=params)
                data = resp.json()
                if data.get("status") != "success":
                    err = data.get("data", {}).get("message", "خطا")
                    logger.warning("Plisio invoice error: %s", err)
                    return False, err, None
                invoice = data["data"]
                if token_amount is None:
                    token_price = await self.settings.get_float("token_price_usd", 0.01)
                    token_amount = int(amount_usd / token_price) if token_price else 0
                payment = await self.sponsors.create_payment(
                    sponsor_id=sponsor_id,
                    campaign_id=campaign_id,
                    amount_usd=amount_usd,
                    token_amount=token_amount,
                    currency=psys_cid,
                    method=PaymentMethod.PLISIO,
                    status=PaymentStatus.PENDING,
                    plisio_invoice_id=invoice.get("txn_id"),
                )
                await self.session.commit()
                return True, invoice.get("invoice_url", ""), {
                    "payment_id": payment.id,
                    "invoice_url": invoice.get("invoice_url"),
                    "txn_id": invoice.get("txn_id"),
                }
        except Exception as e:
            logger.exception("Plisio invoice creation failed")
            return False, str(e), None

    async def handle_webhook(self, data: dict) -> bool:
        secret = await self._get_secret()
        data_copy = dict(data)
        if not verify_plisio_signature(data_copy, secret):
            logger.warning("Invalid Plisio webhook signature")
            return False

        txn_id = data.get("txn_id")
        status = data.get("status")
        payment = await self.sponsors.get_payment_by_invoice(txn_id)
        if not payment:
            logger.warning("Payment not found for txn %s", txn_id)
            return False

        if status in ("completed", "confirmed", "mismatch"):
            payment.status = PaymentStatus.CONFIRMED
            payment.confirmed_at = datetime.now(timezone.utc)
            payment.plisio_txn_id = txn_id
            sponsor = await self.sponsors.get_by_id(payment.sponsor_id)
            if sponsor:
                sponsor.wallet_balance += payment.token_amount
                sponsor.total_purchased += payment.token_amount
                if payment.campaign_id:
                    campaign = await self.sponsors.get_campaign(payment.campaign_id)
                    if campaign:
                        campaign.status = CampaignStatus.ACTIVE
                        if campaign.channel:
                            campaign.channel.is_enabled = True
            await self.session.commit()
            return True
        elif status in ("expired", "cancelled", "error"):
            payment.status = PaymentStatus.EXPIRED if status == "expired" else PaymentStatus.CANCELLED
            await self.session.commit()
        return True


class ManualPaymentService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.sponsors = SponsorRepository(session)
        self.settings = SettingsRepository(session)

    async def get_payment_info(self) -> str:
        return i18n.t(
            "manual_payment_info",
            bank=await self.settings.get("manual_bank_name", ""),
            card=await self.settings.get("manual_card_number", ""),
            holder=await self.settings.get("manual_card_holder", ""),
            instructions=await self.settings.get("manual_payment_instructions", ""),
        )

    async def submit_wallet_deposit(
        self,
        sponsor_id: int,
        token_amount: int,
        amount_toman: int,
        file_id: str,
        note: Optional[str] = None,
    ) -> int:
        payment = await self.sponsors.create_payment(
            sponsor_id=sponsor_id,
            campaign_id=None,
            amount_usd=0.0,
            token_amount=token_amount,
            method=PaymentMethod.MANUAL_CARD,
            status=PaymentStatus.PENDING,
            receipt_file_id=file_id,
            receipt_note=note or f"{amount_toman:,} تومان",
        )
        await self.session.commit()
        return payment.id

    async def submit_receipt(
        self,
        sponsor_id: int,
        campaign_id: Optional[int],
        amount_usd: float,
        file_id: str,
        note: Optional[str] = None,
    ) -> int:
        token_price = await self.settings.get_float("token_price_usd", 0.01)
        token_amount = int(amount_usd / token_price) if token_price else 0
        payment = await self.sponsors.create_payment(
            sponsor_id=sponsor_id,
            campaign_id=campaign_id,
            amount_usd=amount_usd,
            token_amount=token_amount,
            method=PaymentMethod.MANUAL_CARD,
            status=PaymentStatus.PENDING,
            receipt_file_id=file_id,
            receipt_note=note,
        )
        await self.session.commit()
        return payment.id

    async def approve_receipt(self, payment_id: int, admin_id: int) -> bool:
        payment = await self.sponsors.get_payment(payment_id)
        if not payment or not payment.receipt_file_id:
            return False
        payment.status = PaymentStatus.APPROVED
        payment.confirmed_at = datetime.now(timezone.utc)
        sponsor = await self.sponsors.get_by_id(payment.sponsor_id)
        if sponsor:
            sponsor.wallet_balance += payment.token_amount
            sponsor.total_purchased += payment.token_amount
            if payment.campaign_id:
                campaign = await self.sponsors.get_campaign(payment.campaign_id)
                if campaign:
                    campaign.status = CampaignStatus.ACTIVE
                    if campaign.channel:
                        campaign.channel.is_enabled = True
        from app.repositories import UserRepository
        await UserRepository(self.session).log_admin_action(
            admin_id, "approve_payment", "payment", str(payment_id)
        )
        await self.session.commit()
        return True

    async def reject_receipt(self, payment_id: int, admin_id: int, note: str = "") -> bool:
        payment = await self.sponsors.get_payment(payment_id)
        if not payment:
            return False
        payment.status = PaymentStatus.REJECTED
        payment.admin_note = note
        from app.repositories import UserRepository
        await UserRepository(self.session).log_admin_action(
            admin_id, "reject_payment", "payment", str(payment_id)
        )
        await self.session.commit()
        return True
