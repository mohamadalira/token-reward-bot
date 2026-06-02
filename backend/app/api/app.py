import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import async_session_factory, get_session
from app.models import Campaign, CampaignStatus, CampaignView, TokenTransaction
from app.repositories import (
    ChannelRepository,
    SettingsRepository,
    ShopRepository,
    SponsorRepository,
    UserRepository,
)
from app.services import PlisioService, ShopService, SponsorService, TaskService
from app.services.export_service import export_campaign_csv, export_campaign_pdf, export_campaign_xlsx
from app.utils.formatters import format_date, format_number

logger = logging.getLogger(__name__)
settings = get_settings()


def verify_telegram_webapp_data(init_data: str) -> Optional[dict]:
    try:
        parsed = dict(x.split("=", 1) for x in init_data.split("&") if "=" in x)
        received_hash = parsed.pop("hash", None)
        if not received_hash:
            return None
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
        secret_key = hmac.new(b"WebAppData", settings.bot_token.encode(), hashlib.sha256).digest()
        computed = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(computed, received_hash):
            return None
        user_data = json.loads(parsed.get("user", "{}"))
        return user_data
    except Exception:
        return None


async def get_current_user(
    x_telegram_init_data: str = Header(..., alias="X-Telegram-Init-Data"),
    session: AsyncSession = Depends(get_session),
):
    user_data = verify_telegram_webapp_data(x_telegram_init_data)
    if not user_data:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user_id = user_data.get("id")
    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_banned:
        raise HTTPException(status_code=403, detail="Banned")
    return user


def create_api_app() -> FastAPI:
    app = FastAPI(title="Token Reward Bot API", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    @app.get("/api/user/profile")
    async def user_profile(user=Depends(get_current_user), session: AsyncSession = Depends(get_session)):
        settings_repo = SettingsRepository(session)
        use_persian = await settings_repo.get_bool("use_persian_numbers", True)
        use_jalali = await settings_repo.get_bool("use_jalali_dates", True)
        repo = UserRepository(session)
        rank = await repo.get_user_rank(user.id)
        settings_repo = SettingsRepository(session)
        bot_username = await settings_repo.get("bot_username", "")
        return {
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "token_balance": user.token_balance,
            "total_earned": user.total_earned,
            "total_spent": user.total_spent,
            "referral_count": user.referral_count,
            "rank": rank,
            "referral_link": f"https://t.me/{bot_username}?start=ref_{user.referral_code}" if bot_username else "",
            "join_date": format_date(user.created_at, use_jalali, use_persian),
        }

    @app.get("/api/user/tasks")
    async def user_tasks(user=Depends(get_current_user), session: AsyncSession = Depends(get_session)):
        task_svc = TaskService(session)
        tasks = await task_svc.get_available_tasks()
        return [
            {
                "id": t.id,
                "title": t.title,
                "reward": t.reward_amount,
                "invite_link": t.invite_link,
            }
            for t in tasks
        ]

    @app.post("/api/user/tasks/{channel_id}/verify")
    async def verify_task(channel_id: int, user=Depends(get_current_user), session: AsyncSession = Depends(get_session)):
        from aiogram import Bot
        bot = Bot(token=settings.bot_token)
        task_svc = TaskService(session)
        ok, msg, amount = await task_svc.verify_task(bot, user.id, channel_id)
        await bot.session.close()
        return {"success": ok, "message": msg, "amount": amount}

    @app.get("/api/user/shop")
    async def shop_products(user=Depends(get_current_user), session: AsyncSession = Depends(get_session)):
        shop = ShopRepository(session)
        products = await shop.get_products()
        return [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "token_cost": p.token_cost,
                "category": p.category,
                "config_type": p.config_type.value,
                "stock": p.stock,
            }
            for p in products
        ]

    @app.post("/api/user/shop/{product_id}/purchase")
    async def purchase(product_id: int, user=Depends(get_current_user), session: AsyncSession = Depends(get_session)):
        shop_svc = ShopService(session)
        ok, msg, config = await shop_svc.purchase(user.id, product_id)
        return {"success": ok, "message": msg, "config": config}

    @app.get("/api/user/purchases")
    async def purchases(user=Depends(get_current_user), session: AsyncSession = Depends(get_session)):
        shop = ShopRepository(session)
        items = await shop.get_user_purchases(user.id)
        return [
            {
                "id": p.id,
                "product_name": p.product.name if p.product else "",
                "token_cost": p.token_cost,
                "created_at": p.created_at.isoformat(),
            }
            for p in items
        ]

    @app.get("/api/user/transactions")
    async def transactions(user=Depends(get_current_user), session: AsyncSession = Depends(get_session)):
        result = await session.execute(
            select(TokenTransaction)
            .where(TokenTransaction.user_id == user.id)
            .order_by(TokenTransaction.created_at.desc())
            .limit(50)
        )
        return [
            {
                "amount": t.amount,
                "action_type": t.action_type.value,
                "reason": t.reason,
                "created_at": t.created_at.isoformat(),
            }
            for t in result.scalars().all()
        ]

    @app.get("/api/sponsor/dashboard")
    async def sponsor_dashboard(user=Depends(get_current_user), session: AsyncSession = Depends(get_session)):
        repo = SponsorRepository(session)
        sponsor = await repo.get_by_user_id(user.id)
        if not sponsor:
            raise HTTPException(status_code=404, detail="Not a sponsor")
        allocated = sum(
            c.remaining_budget for c in sponsor.campaigns
            if c.status in (CampaignStatus.ACTIVE, CampaignStatus.PAUSED)
        )
        campaigns = []
        for c in sponsor.campaigns:
            conv = (c.total_joins / c.total_views * 100) if c.total_views else 0
            campaigns.append({
                "id": c.id,
                "title": c.channel_title,
                "reward_per_join": c.reward_per_join,
                "total_budget": c.total_budget,
                "remaining_budget": c.remaining_budget,
                "distributed_tokens": c.distributed_tokens,
                "total_joins": c.total_joins,
                "total_views": c.total_views,
                "conversion_rate": round(conv, 2),
                "estimated_remaining_joins": c.remaining_budget // c.reward_per_join if c.reward_per_join else 0,
                "status": c.status.value,
            })
        return {
            "wallet_balance": sponsor.wallet_balance,
            "total_purchased": sponsor.total_purchased,
            "total_consumed": sponsor.total_consumed,
            "allocated": allocated,
            "available": max(0, sponsor.wallet_balance - allocated),
            "campaigns": campaigns,
        }

    @app.get("/api/sponsor/campaigns/{campaign_id}/analytics")
    async def campaign_analytics(campaign_id: int, user=Depends(get_current_user), session: AsyncSession = Depends(get_session)):
        repo = SponsorRepository(session)
        sponsor = await repo.get_by_user_id(user.id)
        campaign = await repo.get_campaign(campaign_id)
        if not campaign or not sponsor or campaign.sponsor_id != sponsor.id:
            raise HTTPException(status_code=404)
        await SponsorService(session).record_campaign_view(campaign_id, user.id)
        hourly = await session.execute(
            select(
                func.extract("hour", CampaignView.created_at).label("hour"),
                func.count(CampaignView.id),
            )
            .where(CampaignView.campaign_id == campaign_id)
            .group_by("hour")
        )
        return {
            "campaign_id": campaign_id,
            "hourly_views": {int(h): c for h, c in hourly.all()},
            "total_views": campaign.total_views,
            "total_joins": campaign.total_joins,
            "conversion_rate": round(campaign.total_joins / campaign.total_views * 100, 2) if campaign.total_views else 0,
        }

    @app.post("/api/sponsor/campaigns/{campaign_id}/pause")
    async def pause_campaign(campaign_id: int, user=Depends(get_current_user), session: AsyncSession = Depends(get_session)):
        ok = await SponsorService(session).pause_campaign(campaign_id, user.id)
        return {"success": ok}

    @app.post("/api/sponsor/campaigns/{campaign_id}/resume")
    async def resume_campaign(campaign_id: int, user=Depends(get_current_user), session: AsyncSession = Depends(get_session)):
        ok = await SponsorService(session).resume_campaign(campaign_id, user.id)
        return {"success": ok}

    @app.get("/api/admin/dashboard")
    async def admin_dashboard(
        user=Depends(get_current_user),
        session: AsyncSession = Depends(get_session),
    ):
        if user.id not in settings.admin_id_list and not user.is_admin:
            raise HTTPException(status_code=403)
        users = UserRepository(session)
        sponsors = SponsorRepository(session)
        result = await session.execute(
            select(func.sum(TokenTransaction.amount)).where(TokenTransaction.amount > 0)
        )
        revenue = await sponsors.get_revenue_stats()
        return {
            "total_users": await users.count_all(),
            "active_users": await users.count_active(),
            "total_sponsors": await sponsors.count_all(),
            "active_campaigns": await sponsors.count_active_campaigns(),
            "total_payments": await sponsors.count_payments(),
            "tokens_distributed": result.scalar() or 0,
            "total_revenue": revenue["total_revenue"],
            "pending_payments": revenue["pending_count"],
        }

    @app.get("/api/admin/settings")
    async def admin_settings(user=Depends(get_current_user), session: AsyncSession = Depends(get_session)):
        if user.id not in settings.admin_id_list:
            raise HTTPException(status_code=403)
        repo = SettingsRepository(session)
        return await repo.get_all()

    class SettingUpdate(BaseModel):
        key: str
        value: str

    @app.put("/api/admin/settings")
    async def update_setting(body: SettingUpdate, user=Depends(get_current_user), session: AsyncSession = Depends(get_session)):
        if user.id not in settings.admin_id_list:
            raise HTTPException(status_code=403)
        repo = SettingsRepository(session)
        await repo.set(body.key, body.value)
        await UserRepository(session).log_admin_action(user.id, "update_setting", "setting", body.key, body.value)
        await session.commit()
        return {"success": True}

    @app.get("/api/sponsor/campaigns/{campaign_id}/export/{fmt}")
    async def export_campaign(
        campaign_id: int,
        fmt: str,
        user=Depends(get_current_user),
        session: AsyncSession = Depends(get_session),
    ):
        if fmt == "csv":
            content = await export_campaign_csv(session, campaign_id, user.id)
            return Response(content, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=campaign_{campaign_id}.csv"})
        elif fmt == "xlsx":
            content = await export_campaign_xlsx(session, campaign_id, user.id)
            return Response(content, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        elif fmt == "pdf":
            content = await export_campaign_pdf(session, campaign_id, user.id)
            return Response(content, media_type="application/pdf")
        raise HTTPException(status_code=400, detail="Invalid format")

    @app.post("/api/admin/plisio/test")
    async def test_plisio(user=Depends(get_current_user), session: AsyncSession = Depends(get_session)):
        if user.id not in settings.admin_id_list:
            raise HTTPException(status_code=403)
        ok, msg = await PlisioService(session).test_connection()
        return {"success": ok, "message": msg}

    @app.post(settings.webhook_path)
    async def plisio_webhook(request: Request, session: AsyncSession = Depends(get_session)):
        data = dict(await request.form())
        svc = PlisioService(session)
        ok = await svc.handle_webhook(data)
        if not ok:
            raise HTTPException(status_code=400)
        return {"status": "ok"}

    return app
