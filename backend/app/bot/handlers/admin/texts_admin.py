"""Admin: manage bot texts in database."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters.admin import AdminCallbackFilter, AdminFilter
from app.locales import fa, get_i18n
from app.services import TextService

router = Router(name="admin_texts")
router.message.filter(AdminFilter())
router.callback_query.filter(AdminCallbackFilter())
i18n = get_i18n()

PAGE = 12


class TextEditStates(StatesGroup):
    value = State()


def _text_list_kb(page: int) -> InlineKeyboardMarkup:
    keys = TextService.text_keys()
    start = page * PAGE
    chunk = keys[start : start + PAGE]
    rows = [[InlineKeyboardButton(text=k, callback_data=f"adm_txt:view:{k}")] for k in chunk]
    nav = []
    if start > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"adm_txt:page:{page - 1}"))
    if start + PAGE < len(keys):
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"adm_txt:page:{page + 1}"))
    if nav:
        rows.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(F.text == i18n.t("btn_texts_admin"))
async def texts_menu(message: Message):
    await message.answer(
        "📝 مدیریت متن‌ها\n\nیک کلید انتخاب کن 👇",
        reply_markup=_text_list_kb(0),
    )


@router.callback_query(F.data.startswith("adm_txt:page:"))
async def texts_page(callback: CallbackQuery):
    page = int(callback.data.split(":")[2])
    await callback.message.edit_reply_markup(reply_markup=_text_list_kb(page))
    await callback.answer()


@router.callback_query(F.data.startswith("adm_txt:view:"))
async def text_view(callback: CallbackQuery, session: AsyncSession):
    key = callback.data.split(":", 2)[2]
    texts = TextService(session)
    current = await texts.t(key)
    default = fa.MESSAGES.get(key, "")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ ویرایش", callback_data=f"adm_txt:edit:{key}")],
        [InlineKeyboardButton(text="↩️ پیش‌فرض", callback_data=f"adm_txt:reset:{key}")],
    ])
    await callback.message.edit_text(
        f"🔑 {key}\n\n📄 فعلی:\n{current}\n\n📋 پیش‌فرض:\n{default}",
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_txt:edit:"))
async def text_edit_start(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split(":", 2)[2]
    await state.update_data(text_key=key)
    await state.set_state(TextEditStates.value)
    await callback.message.answer(f"متن جدید برای `{key}` بفرست:")
    await callback.answer()


@router.message(TextEditStates.value)
async def text_edit_save(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    key = data["text_key"]
    texts = TextService(session)
    await texts.set(key, message.text)
    await session.commit()
    await state.clear()
    await message.answer(i18n.t("done"))


@router.callback_query(F.data.startswith("adm_txt:reset:"))
async def text_reset(callback: CallbackQuery, session: AsyncSession):
    key = callback.data.split(":", 2)[2]
    texts = TextService(session)
    await texts.reset(key)
    await session.commit()
    await callback.answer("بازگردانی شد ✅", show_alert=True)
