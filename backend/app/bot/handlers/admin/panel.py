from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters.admin import AdminFilter
from app.bot.keyboards.main import admin_menu_keyboard, main_menu_keyboard
from app.core.config import get_settings
from app.locales import get_i18n
from app.models import ConfigType, TokenActionType
from app.repositories import (
    ChannelRepository,
    SettingsRepository,
    ShopRepository,
    SponsorRepository,
    UserRepository,
)
from app.services import BroadcastService, ManualPaymentService, PlisioService

router = Router(name="admin")
router.message.filter(AdminFilter())
settings = get_settings()
i18n = get_i18n()


class AdminStates(StatesGroup):
    broadcast_text = State()
    add_tokens = State()
    remove_tokens = State()
    search_user = State()
    add_mandatory_channel = State()
    add_config_name = State()
    add_config_data = State()
    set_setting = State()


@router.message(F.text == i18n.t("admin_menu"))
async def admin_menu(message: Message):
    await message.answer(i18n.t("admin_menu"), reply_markup=admin_menu_keyboard())


@router.message(F.text == i18n.t("btn_dashboard"))
async def dashboard(message: Message, session: AsyncSession):
    users = UserRepository(session)
    sponsors = SponsorRepository(session)
    from app.models import TokenTransaction
    from sqlalchemy import func, select
    result = await session.execute(select(func.sum(TokenTransaction.amount)).where(TokenTransaction.amount > 0))
    tokens = result.scalar() or 0
    revenue = await sponsors.get_revenue_stats()
    await message.answer(
        i18n.t(
            "dashboard",
            total_users=await users.count_all(),
            active_users=await users.count_active(),
            total_sponsors=await sponsors.count_all(),
            active_campaigns=await sponsors.count_active_campaigns(),
            total_payments=await sponsors.count_payments(),
            tokens_distributed=tokens,
        )
    )


@router.message(F.text == i18n.t("btn_settings"))
async def show_settings(message: Message, session: AsyncSession):
    repo = SettingsRepository(session)
    all_settings = await repo.get_all()
    lines = ["⚙️ تنظیمات فعلی:\n"]
    for k, v in all_settings.items():
        lines.append(f"• {k}: {v}")
    lines.append("\nبرای تغییر: /set_setting کلید مقدار")
    await message.answer("\n".join(lines))


@router.message(F.text.startswith("/set_setting"))
async def set_setting(message: Message, session: AsyncSession):
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("فرمت: /set_setting کلید مقدار")
        return
    repo = SettingsRepository(session)
    await repo.set(parts[1], parts[2])
    await session.commit()
    await message.answer(i18n.t("done"))


@router.message(F.text == i18n.t("btn_users"))
async def users_menu(message: Message):
    await message.answer(
        "👥 مدیریت کاربران\n\n"
        "🔍 جستجو: /user ID یا username\n"
        "➕ افزودن توکن: /add_tokens USER_ID AMOUNT [دلیل]\n"
        "➖ کم کردن: /remove_tokens USER_ID AMOUNT [دلیل]\n"
        "🚫 بن: /ban USER_ID\n"
        "✅ آنبن: /unban USER_ID"
    )


@router.message(F.text.startswith("/user"))
async def search_user(message: Message, session: AsyncSession):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("فرمت: /user ID یا username")
        return
    repo = UserRepository(session)
    results = await repo.search(parts[1])
    if not results:
        await message.answer("کاربر پیدا نشد 😕")
        return
    for u in results:
        await message.answer(
            f"🆔 {u.id}\n👤 {u.first_name or u.username}\n"
            f"💰 {u.token_balance} توکن\n🚫 بن: {u.is_banned}"
        )


@router.message(F.text.startswith("/add_tokens"))
async def add_tokens(message: Message, session: AsyncSession):
    parts = message.text.split(maxsplit=3)
    if len(parts) < 3:
        await message.answer("فرمت: /add_tokens USER_ID AMOUNT")
        return
    user_id, amount = int(parts[1]), int(parts[2])
    reason = parts[3] if len(parts) > 3 else None
    repo = UserRepository(session)
    await repo.add_tokens(user_id, amount, TokenActionType.ADMIN_ADD, reason, message.from_user.id)
    await repo.log_admin_action(message.from_user.id, "add_tokens", "user", str(user_id), f"{amount}")
    await session.commit()
    await message.answer(i18n.t("tokens_added", amount=amount))


@router.message(F.text.startswith("/remove_tokens"))
async def remove_tokens(message: Message, session: AsyncSession):
    parts = message.text.split(maxsplit=3)
    if len(parts) < 3:
        await message.answer("فرمت: /remove_tokens USER_ID AMOUNT")
        return
    user_id, amount = int(parts[1]), int(parts[2])
    repo = UserRepository(session)
    try:
        await repo.remove_tokens(user_id, amount, TokenActionType.ADMIN_REMOVE, admin_id=message.from_user.id)
        await repo.log_admin_action(message.from_user.id, "remove_tokens", "user", str(user_id), f"{amount}")
        await session.commit()
        await message.answer(i18n.t("tokens_removed", amount=amount))
    except ValueError as e:
        await message.answer(str(e))


@router.message(F.text.startswith("/ban"))
async def ban_user(message: Message, session: AsyncSession):
    user_id = int(message.text.split()[1])
    repo = UserRepository(session)
    await repo.ban(user_id, True)
    await repo.log_admin_action(message.from_user.id, "ban", "user", str(user_id))
    await session.commit()
    await message.answer(i18n.t("user_banned"))


@router.message(F.text.startswith("/unban"))
async def unban_user(message: Message, session: AsyncSession):
    user_id = int(message.text.split()[1])
    repo = UserRepository(session)
    await repo.ban(user_id, False)
    await repo.log_admin_action(message.from_user.id, "unban", "user", str(user_id))
    await session.commit()
    await message.answer(i18n.t("user_unbanned"))


@router.message(F.text == i18n.t("btn_broadcast"))
async def broadcast_menu(message: Message, state: FSMContext):
    await message.answer("📨 ارسال همگانی\n\nمتن پیام رو بفرست یا /broadcast_sponsors")
    await state.set_state(AdminStates.broadcast_text)


@router.message(AdminStates.broadcast_text)
async def do_broadcast(message: Message, state: FSMContext, session: AsyncSession, bot):
    svc = BroadcastService(session)
    await message.answer(i18n.t("broadcast_started"))
    success, failed = await svc.broadcast_text(bot, message.text)
    await state.clear()
    await message.answer(i18n.t("broadcast_done", success=success, failed=failed))


@router.message(F.text == i18n.t("btn_channels"))
async def channels_menu(message: Message):
    await message.answer(
        "📢 مدیریت کانال‌ها\n\n"
        "➕ اجباری: /add_mandatory CHANNEL_ID عنوان\n"
        "➖ حذف: /remove_mandatory ID"
    )


@router.message(F.text.startswith("/add_mandatory"))
async def add_mandatory(message: Message, session: AsyncSession):
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("فرمت: /add_mandatory CHANNEL_ID عنوان")
        return
    repo = ChannelRepository(session)
    ch = await repo.add_mandatory(parts[1], parts[2])
    await session.commit()
    await message.answer(f"✅ کانال اضافه شد (ID: {ch.id})")


@router.message(F.text.startswith("/remove_mandatory"))
async def remove_mandatory(message: Message, session: AsyncSession):
    ch_id = int(message.text.split()[1])
    repo = ChannelRepository(session)
    await repo.remove_mandatory(ch_id)
    await session.commit()
    await message.answer(i18n.t("done"))


@router.message(F.text == i18n.t("btn_configs"))
async def configs_menu(message: Message):
    await message.answer(
        "🛒 فروشگاه\n\n"
        "➕ /add_config نام|قیمت|نوع|دسته|موجودی\n"
        "سپس کانفیگ رو بفرست\n"
        "🗑 /delete_config ID"
    )


@router.message(F.text.startswith("/add_config"))
async def add_config_start(message: Message, state: FSMContext):
    parts = message.text.replace("/add_config ", "").split("|")
    if len(parts) < 5:
        await message.answer("فرمت: /add_config نام|قیمت|نوع|دسته|موجودی")
        return
    await state.update_data(
        name=parts[0], cost=int(parts[1]), ctype=parts[2], category=parts[3], stock=int(parts[4])
    )
    await state.set_state(AdminStates.add_config_data)
    await message.answer("حالا متن کانفیگ رو بفرست 👇")


@router.message(AdminStates.add_config_data)
async def add_config_data(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    shop = ShopRepository(session)
    try:
        config_type = ConfigType(data["ctype"].lower())
    except ValueError:
        config_type = ConfigType.V2RAY
    await shop.create_product(
        name=data["name"],
        token_cost=data["cost"],
        config_type=config_type,
        category=data["category"],
        stock=data["stock"],
        config_data=message.text,
    )
    await session.commit()
    await state.clear()
    await message.answer(i18n.t("done"))


@router.message(F.text.startswith("/delete_config"))
async def delete_config(message: Message, session: AsyncSession):
    product_id = int(message.text.split()[1])
    shop = ShopRepository(session)
    await shop.delete_product(product_id)
    await session.commit()
    await message.answer(i18n.t("done"))


@router.message(F.text == i18n.t("btn_sponsors_admin"))
async def sponsors_admin(message: Message, session: AsyncSession):
    repo = SponsorRepository(session)
    pending = await repo.get_pending()
    if not pending:
        await message.answer("درخواست pending نیست")
        return
    for s in pending:
        await message.answer(
            f"📢 اسپانسر #{s.id}\n🆔 {s.user_id}\n\n/approve_sponsor {s.id}\n/reject_sponsor {s.id}"
        )


@router.message(F.text.startswith("/approve_sponsor"))
async def approve_sponsor(message: Message, session: AsyncSession):
    sponsor_id = int(message.text.split()[1])
    from app.services import SponsorService
    svc = SponsorService(session)
    await svc.approve_sponsor(sponsor_id, message.from_user.id)
    await message.answer(i18n.t("done"))


@router.message(F.text.startswith("/reject_sponsor"))
async def reject_sponsor(message: Message, session: AsyncSession):
    sponsor_id = int(message.text.split()[1])
    from app.models import SponsorStatus
    repo = SponsorRepository(session)
    sponsor = await repo.get_by_id(sponsor_id)
    if sponsor:
        sponsor.status = SponsorStatus.REJECTED
        await session.commit()
    await message.answer(i18n.t("done"))


@router.message(F.text == i18n.t("btn_finance"))
async def finance_dashboard(message: Message, session: AsyncSession):
    repo = SponsorRepository(session)
    stats = await repo.get_revenue_stats()
    await message.answer(
        f"💰 داشبورد مالی\n\n"
        f"📈 کل درآمد: ${stats['total_revenue']:.2f}\n"
        f"⏳ پرداخت معلق: {stats['pending_count']}"
    )


@router.message(F.text == i18n.t("btn_payments"))
async def payments_menu(message: Message, session: AsyncSession):
    repo = SponsorRepository(session)
    receipts = await repo.get_pending_receipts()
    if not receipts:
        await message.answer("رسید pending نیست")
        return
    for p in receipts:
        await message.answer(
            f"📸 رسید #{p.id}\n💰 ${p.amount_usd}\n\n/approve_payment {p.id}\n/reject_payment {p.id}"
        )


@router.message(F.text.startswith("/approve_payment"))
async def approve_payment(message: Message, session: AsyncSession):
    payment_id = int(message.text.split()[1])
    svc = ManualPaymentService(session)
    if await svc.approve_receipt(payment_id, message.from_user.id):
        await message.answer(i18n.t("payment_confirmed"))
    else:
        await message.answer(i18n.t("error"))


@router.message(F.text.startswith("/reject_payment"))
async def reject_payment(message: Message, session: AsyncSession):
    payment_id = int(message.text.split()[1])
    svc = ManualPaymentService(session)
    await svc.reject_receipt(payment_id, message.from_user.id)
    await message.answer(i18n.t("done"))


@router.message(F.text.startswith("/test_plisio"))
async def test_plisio(message: Message, session: AsyncSession):
    svc = PlisioService(session)
    ok, msg = await svc.test_connection()
    await message.answer(msg)


@router.message(F.text == i18n.t("btn_back"))
async def back_to_main(message: Message, session: AsyncSession):
    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(message.from_user.id)
    await message.answer(
        i18n.t("main_menu"),
        reply_markup=main_menu_keyboard(is_admin=True, is_sponsor=user.is_sponsor if user else False),
    )
