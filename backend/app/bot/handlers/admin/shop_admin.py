"""Admin: shop categories + interactive config upload."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters.admin import AdminCallbackFilter, AdminFilter
from app.locales import get_i18n
from app.repositories import CategoryRepository, ShopRepository
from app.services import TextService

router = Router(name="admin_shop")
router.message.filter(AdminFilter())
router.callback_query.filter(AdminCallbackFilter())
i18n = get_i18n()


class CategoryStates(StatesGroup):
    name = State()
    description = State()
    price = State()


class ConfigAddStates(StatesGroup):
    pick_category = State()
    pick_mode = State()
    configs = State()
    confirm = State()


@router.message(F.text == i18n.t("btn_categories"))
async def categories_menu(message: Message, session: AsyncSession):
    cats = CategoryRepository(session)
    items = await cats.list_all()
    lines = ["📂 دسته‌بندی‌های فروشگاه:\n"]
    for c in items:
        status = "✅" if c.is_active else "❌"
        lines.append(f"{status} #{c.id} {c.name} — {c.default_token_cost} توکن")
    lines.append("\n➕ /add_category برای افزودن دسته")
    lines.append("✏️ /edit_category ID|نام|قیمت|توضیح")
    lines.append("🗑 /del_category ID")
    await message.answer("\n".join(lines))


@router.message(F.text.startswith("/add_category"))
async def add_category_start(message: Message, state: FSMContext):
    await state.set_state(CategoryStates.name)
    await message.answer("نام دسته رو بفرست (مثلاً 10GB):")


@router.message(CategoryStates.name)
async def add_category_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(CategoryStates.description)
    await message.answer("توضیح دسته (یا - برای رد):")


@router.message(CategoryStates.description)
async def add_category_desc(message: Message, state: FSMContext):
    desc = message.text.strip()
    await state.update_data(description=None if desc == "-" else desc)
    await state.set_state(CategoryStates.price)
    await message.answer("قیمت پیش‌فرض (توکن):")


@router.message(CategoryStates.price)
async def add_category_price(message: Message, state: FSMContext, session: AsyncSession):
    try:
        price = int(message.text.strip())
    except ValueError:
        await message.answer("عدد معتبر بفرست")
        return
    data = await state.get_data()
    cats = CategoryRepository(session)
    cat = await cats.create(
        name=data["name"],
        description=data.get("description"),
        default_token_cost=price,
    )
    await session.commit()
    await state.clear()
    await message.answer(f"✅ دسته #{cat.id} {cat.name} ساخته شد")


@router.message(F.text.startswith("/del_category"))
async def del_category(message: Message, session: AsyncSession):
    cat_id = int(message.text.split()[1])
    cats = CategoryRepository(session)
    if await cats.delete(cat_id):
        await session.commit()
        await message.answer(i18n.t("done"))
    else:
        await message.answer("پیدا نشد")


@router.message(F.text == i18n.t("btn_add_config_interactive"))
async def add_config_start(message: Message, session: AsyncSession, state: FSMContext):
    cats = CategoryRepository(session)
    categories = await cats.list_active()
    if not categories:
        await message.answer("اول یه دسته بساز (/add_category)")
        return
    rows = [
        [InlineKeyboardButton(text=c.name, callback_data=f"adm_cfg:cat:{c.id}")]
        for c in categories
    ]
    await state.set_state(ConfigAddStates.pick_category)
    await message.answer("دسته رو انتخاب کن 👇", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(F.data.startswith("adm_cfg:cat:"))
async def pick_category(callback: CallbackQuery, state: FSMContext):
    cat_id = int(callback.data.split(":")[2])
    await state.update_data(category_id=cat_id)
    await state.set_state(ConfigAddStates.pick_mode)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="تکی", callback_data="adm_cfg:mode:single")],
        [InlineKeyboardButton(text="انبوه (هر خط یک کانفیگ)", callback_data="adm_cfg:mode:bulk")],
    ])
    await callback.message.edit_text("تکی یا انبوه؟", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("adm_cfg:mode:"))
async def pick_mode(callback: CallbackQuery, state: FSMContext):
    mode = callback.data.split(":")[2]
    await state.update_data(mode=mode)
    await state.set_state(ConfigAddStates.configs)
    hint = "کانفیگ رو بفرست 👇" if mode == "single" else "هر خط یک کانفیگ (چندخطی) 👇"
    await callback.message.edit_text(hint)
    await callback.answer()


@router.message(ConfigAddStates.configs)
async def receive_configs(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    mode = data.get("mode", "single")
    lines = [message.text.strip()] if mode == "single" else message.text.splitlines()
    lines = [ln for ln in lines if ln.strip()]
    if not lines:
        await message.answer("خالی بود — دوباره بفرست")
        return
    await state.update_data(config_lines=lines, pending_count=len(lines))
    await state.set_state(ConfigAddStates.confirm)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ تایید", callback_data="adm_cfg:confirm:yes"),
            InlineKeyboardButton(text="❌ لغو", callback_data="adm_cfg:confirm:no"),
        ],
    ])
    await message.answer(f"تعداد {len(lines)} کانفیگ — تایید می‌کنی؟", reply_markup=kb)


@router.callback_query(F.data == "adm_cfg:confirm:yes")
async def confirm_configs(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    cats = CategoryRepository(session)
    cat = await cats.get_by_id(data["category_id"])
    if not cat:
        await callback.answer("دسته پیدا نشد", show_alert=True)
        await state.clear()
        return
    shop = ShopRepository(session)
    created = await shop.bulk_create_from_lines(
        category_id=cat.id,
        category_name=cat.name,
        token_cost=cat.default_token_cost,
        lines=data.get("config_lines", []),
    )
    await session.commit()
    await state.clear()
    await callback.message.edit_text(f"✅ {len(created)} کانفیگ اضافه شد")
    await callback.answer()


@router.callback_query(F.data == "adm_cfg:confirm:no")
async def cancel_configs(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(i18n.t("cancelled"))
    await callback.answer()
