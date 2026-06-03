"""Persian (Farsi) localization strings."""

MESSAGES = {
    # General
    "welcome": "سلام {name} 👋\n\nبه ربات توکن خوش اومدی!",
    "main_menu": "منوی اصلی 👇",
    "done": "انجام شد ✅",
    "error": "یه مشکلی پیش اومد 😕\nدوباره امتحان کن.",
    "cancelled": "لغو شد ❌",
    "not_enough_tokens": "توکن کافی نداری 😕",
    "banned": "دسترسی‌ات محدود شده 🚫",
    "rate_limited": "خیلی سریع داری کلیک می‌کنی ⏳\nچند ثانیه صبر کن.",
    # Mandatory channels
    "join_channels_first": "اول عضو کانال‌های زیر شو 👇",
    "check_membership": "✅ بررسی عضویت",
    "membership_ok": "عضویتت تایید شد ✅",
    "membership_fail": "هنوز عضو نشدی 😕\nاول عضو کانال‌ها شو.",
    # Menu
    "btn_profile": "👤 پروفایل من",
    "btn_earn": "💰 کسب توکن",
    "btn_shop": "🛒 خرید کانفیگ",
    "btn_my_configs": "📦 کانفیگ‌های من",
    "btn_sponsor": "💎 اسپانسر شدن",
    "btn_support": "💬 پشتیبانی",
    "btn_rules": "📋 قوانین",
    "btn_back": "🔙 بازگشت",
    "btn_mini_app": "📱 باز کردن اپ",
    # Profile
    "profile": (
        "👤 پروفایل\n\n"
        "🆔 آیدی: {id}\n"
        "👤 نام: {name}\n"
        "💰 موجودی: {balance} توکن\n"
        "📈 کل درآمد: {earned} توکن\n"
        "📉 کل خرج: {spent} توکن\n"
        "👥 دعوت‌ها: {referrals}\n"
        "📅 عضویت: {join_date}\n"
        "🏅 رتبه: #{rank}"
    ),
    "referral_link": "🔗 لینک دعوت:\n{link}",
    # Earn tokens
    "earn_menu_referral": "👥 دعوت دوستان",
    "earn_menu_tasks": "📢 تسک‌های اسپانسر",
    "earn_choose_mode": "چطور می‌خوای توکن بگیری؟ 👇",
    "no_tasks": "فعلاً تسکی نیست 😕\nبعداً سر بزن.",
    "task_channel_card": (
        "📢 {title}\n\n"
        "{description}\n\n"
        "💰 توکن دریافتی: +{reward} توکن"
    ),
    "task_no_description": "برای عضویت در این کانال توکن بگیر 🎁",
    "btn_view_channel": "🔗 مشاهده کانال",
    "btn_joined": "✅ عضو شدم",
    "task_card": "📢 {title}\n💰 پاداش: {reward} توکن",
    "btn_join_channel": "🔗 عضویت",
    "btn_verify": "✅ تایید",
    "task_reward": "✅ عضویتت تایید شد\n🎁 {amount} توکن به حسابت اضافه شد",
    "task_already_done": "قبلاً پاداش این کانال رو گرفتی ✅",
    # Referral
    "referral_reward": "🎉 یه نفر با لینک دعوتت عضو شد\n💰 {amount} توکن گرفتی",
    "referral_admin_notify": "👥 دعوت جدید ثبت شد\n\nدعوت‌کننده: {referrer}\nکاربر جدید: {user}",
    "referral_info": (
        "👥 سیستم دعوت\n\n"
        "💰 پاداش هر دعوت: {reward} توکن\n"
        "👥 تعداد دعوت‌ها: {count}\n\n"
        "🔗 لینک دعوت:\n{link}"
    ),
    # Shop
    "shop_empty": "فعلاً محصولی نیست 😕",
    "shop_pick_category": "📂 یه دسته انتخاب کن 👇",
    "shop_pick_product": "🛒 محصولات موجود:",
    "shop_category_header": "📂 {name}\n\n{description}\n\nمحصول رو انتخاب کن 👇",
    "shop_product": (
        "📦 {name}\n\n"
        "{description}\n\n"
        "💰 قیمت: {price} توکن\n"
        "📂 دسته: {category}\n"
        "📊 موجودی: {stock}"
    ),
    "purchase_success": "🎉 خریدت با موفقیت انجام شد\n📦 کانفیگ برات ارسال شد",
    "purchase_confirm": "مطمئنی می‌خوای {name} رو با {price} توکن بخری؟",
    "out_of_stock": "موجودی تموم شده 😕",
    "no_purchases": "هنوز خریدی نداری 😕",
    "my_configs_header": "📦 کانفیگ‌های خریداری‌شده:",
    "btn_buy": "🛒 خرید",
    "btn_confirm": "✅ تایید",
    # Leaderboard
    "leaderboard": "🏆 لیدربورد\n\n{entries}",
    "leaderboard_entry": "{rank}. {name} — {tokens} توکن",
    # Support & Rules
    "support": "💬 پشتیبانی:\n@{username}",
    "rules": "📋 قوانین:\n{rules}",
    # Sponsor
    # Sponsor intro
    "sponsor_intro": (
        "💎 اسپانسر شدن\n\n"
        "با اسپانسر شدن می‌تونی کانال خودت رو تبلیغ کنی و "
        "با هر عضو جدید توکن هدیه بدی 🚀"
    ),
    "sponsor_menu": "📢 پنل اسپانسر 👇",
    "btn_become_sponsor": "🚀 اسپانسر شو",
    "btn_my_campaigns": "📊 کمپین‌های من",
    "btn_deposit": "💳 شارژ توکن",
    "btn_sponsor_stats": "📈 آمار",
    "sponsor_pending": "درخواستت ثبت شد ⏳\nمنتظر تایید ادمین باش.",
    "sponsor_approved": "تبریک! اسپانسریت تایید شد ✅",
    "sponsor_rejected": "درخواست اسپانسری رد شد ❌",
    "campaign_created": "کمپین ساخته شد ✅\nبرای فعال‌سازی پرداخت کن.",
    "campaign_exhausted": "⚠️ موجودی کمپینت تموم شد\nبرای ادامه تبلیغ کمپین رو شارژ کن.",
    "campaign_join_notify": (
        "👤 عضو جدید جذب شد\n\n"
        "🆔 شناسه کاربر: {user_id}\n"
        "🕐 زمان عضویت: {joined_at}\n"
        "💰 توکن پرداخت شده: {reward}\n"
        "💳 موجودی باقی‌مانده: {balance} توکن"
    ),
    "payment_confirmed": "✅ پرداخت تایید شد\nکمپینت فعال شد و تبلیغت از الان نمایش داده میشه.",
    "wallet_info": (
        "💳 کیف پول\n\n"
        "💰 موجودی: {balance} توکن\n"
        "📥 خریداری شده: {purchased} توکن\n"
        "📤 مصرف شده: {consumed} توکن\n"
        "🔒 تخصیص فعال: {allocated} توکن\n"
        "✅ قابل استفاده: {available} توکن"
    ),
    "min_budget_error": "حداقل بودجه کمپین {min} توکنه 😕",
    "campaign_validation_fail": "❌ خطا در تایید کانال:\n{error}",
    # Admin
    "admin_menu": "⚙️ پنل ادمین 👇",
    "btn_dashboard": "📊 آمار کلی",
    "btn_settings": "⚙️ تنظیمات",
    "btn_channels": "📢 مدیریت کانال‌ها",
    "btn_configs": "🛒 فروشگاه کانفیگ",
    "btn_sponsors_admin": "📢 اسپانسرها",
    "btn_users": "👥 کاربران",
    "btn_broadcast": "📨 ارسال همگانی",
    "btn_finance": "💰 مالی",
    "btn_payments": "💳 پرداخت‌ها",
    "btn_texts_admin": "📝 مدیریت متن‌ها",
    "btn_categories": "📂 دسته‌بندی فروشگاه",
    "btn_add_config_interactive": "➕ افزودن کانفیگ",
    "btn_payment_settings": "💳 مدیریت پرداخت‌ها",
    "btn_add_sponsor_channel": "➕ کانال اسپانسری",
    "pay_manual_card": "💳 کارت به کارت",
    "pay_crypto": "₿ کریپتو",
    "dashboard": (
        "📊 آمار کلی\n\n"
        "👥 کل کاربران: {total_users}\n"
        "🟢 فعال: {active_users}\n"
        "📢 اسپانسرها: {total_sponsors}\n"
        "🚀 کمپین فعال: {active_campaigns}\n"
        "💳 پرداخت‌ها: {total_payments}\n"
        "🎁 توکن توزیع شده: {tokens_distributed}"
    ),
    "admin_only": "فقط ادمین‌ها دسترسی دارن 🚫",
    "user_banned": "کاربر بن شد ✅",
    "user_unbanned": "بن کاربر برداشته شد ✅",
    "tokens_added": "{amount} توکن اضافه شد ✅",
    "tokens_removed": "{amount} توکن کم شد ✅",
    "broadcast_started": "ارسال همگانی شروع شد 📨",
    "broadcast_done": "ارسال تموم شد ✅\n✅ موفق: {success}\n❌ ناموفق: {failed}",
    # Payment manual
    "manual_payment_info": (
        "💳 پرداخت کارت به کارت\n\n"
        "🏦 بانک: {bank}\n"
        "💳 شماره کارت: {card}\n"
        "👤 صاحب حساب: {holder}\n\n"
        "{instructions}\n\n"
        "بعد از پرداخت، رسید رو بفرست 📸"
    ),
    "receipt_uploaded": "رسیدت ثبت شد ⏳\nمنتظر تایید ادمین باش.",
    "receipt_admin_notify": "📸 رسید جدید!\n\nاسپانسر: {sponsor}\nمبلغ: {amount}",
    # Notifications
    "notification_tokens": "💰 {amount} توکن به حسابت اضافه شد",
}


def get_message(key: str, **kwargs) -> str:
    template = MESSAGES.get(key, key)
    if kwargs:
        return template.format(**kwargs)
    return template
