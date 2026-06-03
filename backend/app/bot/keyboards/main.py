from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo

from app.core.config import get_settings
from app.locales import get_i18n

i18n = get_i18n()
settings = get_settings()


def main_menu_keyboard(is_admin: bool = False, is_sponsor: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=i18n.t("btn_profile")), KeyboardButton(text=i18n.t("btn_earn"))],
        [KeyboardButton(text=i18n.t("btn_shop")), KeyboardButton(text=i18n.t("btn_my_configs"))],
        [KeyboardButton(text=i18n.t("btn_leaderboard")), KeyboardButton(text=i18n.t("btn_support"))],
        [KeyboardButton(text=i18n.t("btn_rules"))],
    ]
    # Telegram WebApp buttons require HTTPS — skip on IP-only http installs
    if settings.webapp_url.startswith("https://"):
        rows.append(
            [KeyboardButton(text=i18n.t("btn_mini_app"), web_app=WebAppInfo(url=settings.webapp_url))]
        )
    if is_sponsor:
        rows.append([KeyboardButton(text=i18n.t("sponsor_menu"))])
    if is_admin:
        rows.append([KeyboardButton(text=i18n.t("admin_menu"))])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def back_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=i18n.t("btn_back"))]],
        resize_keyboard=True,
    )


def check_membership_keyboard(channels: list) -> InlineKeyboardMarkup:
    buttons = []
    for ch in channels:
        link = ch.invite_link or f"https://t.me/{ch.channel_username}"
        buttons.append([InlineKeyboardButton(text=f"📢 {ch.title}", url=link)])
    buttons.append([InlineKeyboardButton(text=i18n.t("check_membership"), callback_data="check_membership")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def earn_mode_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=i18n.t("earn_menu_referral"), callback_data="earn:referral")],
        [InlineKeyboardButton(text=i18n.t("earn_menu_tasks"), callback_data="earn:tasks")],
    ])


def task_keyboard(channel_id: int, invite_link: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=i18n.t("btn_join_channel"), url=invite_link)],
        [InlineKeyboardButton(text=i18n.t("btn_verify"), callback_data=f"verify_task:{channel_id}")],
    ])


def shop_product_keyboard(product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=i18n.t("btn_buy"), callback_data=f"buy:{product_id}")],
    ])


def confirm_purchase_keyboard(product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=i18n.t("btn_confirm"), callback_data=f"confirm_buy:{product_id}"),
            InlineKeyboardButton(text=i18n.t("cancelled"), callback_data="cancel"),
        ],
    ])


def admin_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=i18n.t("btn_dashboard")), KeyboardButton(text=i18n.t("btn_settings"))],
            [KeyboardButton(text=i18n.t("btn_texts_admin")), KeyboardButton(text=i18n.t("btn_payment_settings"))],
            [KeyboardButton(text=i18n.t("btn_categories")), KeyboardButton(text=i18n.t("btn_add_config_interactive"))],
            [KeyboardButton(text=i18n.t("btn_channels")), KeyboardButton(text=i18n.t("btn_add_sponsor_channel"))],
            [KeyboardButton(text=i18n.t("btn_sponsors_admin")), KeyboardButton(text=i18n.t("btn_users"))],
            [KeyboardButton(text=i18n.t("btn_broadcast")), KeyboardButton(text=i18n.t("btn_finance"))],
            [KeyboardButton(text=i18n.t("btn_payments"))],
            [KeyboardButton(text=i18n.t("btn_back"))],
        ],
        resize_keyboard=True,
    )


def sponsor_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=i18n.t("btn_become_sponsor"))],
            [KeyboardButton(text=i18n.t("btn_my_campaigns")), KeyboardButton(text=i18n.t("btn_deposit"))],
            [KeyboardButton(text=i18n.t("btn_sponsor_stats"))],
            [KeyboardButton(text=i18n.t("btn_back"))],
        ],
        resize_keyboard=True,
    )
