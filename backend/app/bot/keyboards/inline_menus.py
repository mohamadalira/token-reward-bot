from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from app.services.text_service import TextService


async def user_main_menu(
    texts: TextService,
    *,
    is_admin: bool = False,
    is_sponsor: bool = False,
    sponsor_enabled: bool = True,
    webapp_url: str = "",
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text=await texts.t("btn_profile"), callback_data="menu:profile"),
            InlineKeyboardButton(text=await texts.t("btn_earn"), callback_data="menu:earn"),
        ],
        [
            InlineKeyboardButton(text=await texts.t("btn_shop"), callback_data="menu:shop"),
            InlineKeyboardButton(text=await texts.t("btn_my_configs"), callback_data="menu:configs"),
        ],
    ]
    support_row = [InlineKeyboardButton(text=await texts.t("btn_support"), callback_data="menu:support")]
    if sponsor_enabled:
        rows.append([
            InlineKeyboardButton(text=await texts.t("btn_sponsor"), callback_data="spn:home"),
            InlineKeyboardButton(text=await texts.t("btn_support"), callback_data="menu:support"),
        ])
    else:
        rows.append(support_row)
    rows.append([InlineKeyboardButton(text=await texts.t("btn_rules"), callback_data="menu:rules")])
    if webapp_url.startswith("https://"):
        rows.append([
            InlineKeyboardButton(
                text=await texts.t("btn_mini_app"),
                web_app=WebAppInfo(url=webapp_url),
            )
        ])
    if is_admin:
        rows.append([
            InlineKeyboardButton(text=await texts.t("admin_menu"), callback_data="adm:home")
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_main_button(text: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=text, callback_data="menu:main")]]
    )


async def earn_mode_keyboard(texts: TextService) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=await texts.t("earn_menu_referral"), callback_data="earn:referral")],
        [InlineKeyboardButton(text=await texts.t("earn_menu_tasks"), callback_data="earn:tasks")],
        [InlineKeyboardButton(text=await texts.t("btn_back"), callback_data="menu:main")],
    ])


def task_channel_keyboard(
    channel_db_id: int,
    invite_link: str,
    view_label: str,
    joined_label: str,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=view_label, url=invite_link)],
        [InlineKeyboardButton(text=joined_label, callback_data=f"verify_task:{channel_db_id}")],
    ])


async def shop_categories_keyboard(
    texts: TextService,
    categories: list,
) -> InlineKeyboardMarkup:
    rows = []
    for cat in categories:
        rows.append([
            InlineKeyboardButton(
                text=f"📂 {cat.name} ({cat.default_token_cost} توکن)",
                callback_data=f"shop:cat:{cat.id}",
            )
        ])
    rows.append([InlineKeyboardButton(text=await texts.t("btn_back"), callback_data="menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def shop_products_keyboard(products: list, back_label: str, category_id: int) -> InlineKeyboardMarkup:
    rows = []
    for p in products:
        rows.append([
            InlineKeyboardButton(
                text=f"📦 {p.name} — {p.token_cost} توکن",
                callback_data=f"buy:{p.id}",
            )
        ])
    rows.append([
        InlineKeyboardButton(text=back_label, callback_data="menu:shop"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def confirm_purchase_keyboard(
    texts: TextService,
    product_id: int,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=await texts.t("btn_confirm"), callback_data=f"confirm_buy:{product_id}"),
            InlineKeyboardButton(text=await texts.t("cancelled"), callback_data="cancel"),
        ],
    ])


async def check_membership_keyboard(texts: TextService, channels: list) -> InlineKeyboardMarkup:
    buttons = []
    for ch in channels:
        link = ch.invite_link or f"https://t.me/{ch.channel_username}"
        buttons.append([InlineKeyboardButton(text=f"📢 {ch.title}", url=link)])
    buttons.append([
        InlineKeyboardButton(text=await texts.t("check_membership"), callback_data="check_membership")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def sponsor_intro_keyboard(texts: TextService) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=await texts.t("btn_become_sponsor"), callback_data="sponsor:apply")],
        [InlineKeyboardButton(text=await texts.t("btn_back"), callback_data="menu:main")],
    ])


async def payment_method_keyboard(texts: TextService) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=await texts.t("pay_manual_card"), callback_data="pay:manual")],
        [InlineKeyboardButton(text=await texts.t("pay_crypto"), callback_data="pay:crypto")],
        [InlineKeyboardButton(text=await texts.t("btn_back"), callback_data="menu:main")],
    ])
