# Token Reward Bot

ربات تلگرامی enterprise-grade برای کسب توکن، خرید کانفیگ VPN، سیستم اسپانسر و Mini App.

## ویژگی‌ها

- **۳ حالت عملکرد**: Referral، Task (کانال اسپانسر)، Combined
- **پنل ادمین کامل** داخل تلگرام (بدون نیاز به SSH)
- **سیستم اسپانسر** با کیف پول، کمپین، آنalytics
- **درگاه Plisio** (BTC, ETH, USDT و...) + پرداخت کارت به کارت
- **فروشگاه کانفیگ** (V2Ray, VLESS, VMESS, Trojan, Shadowsocks, WireGuard, OpenVPN)
- **Mini App** با Next.js (RTL، فارسی، Dark Mode)
- **امنیت**: Rate limiting، Anti-spam، Audit logs، Webhook signature
- **مقیاس‌پذیری**: Redis cache، Connection pooling، Async

## معماری

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Telegram   │────▶│   Backend    │────▶│ PostgreSQL  │
│  Bot/API    │     │  (Aiogram +  │     └─────────────┘
└─────────────┘     │   FastAPI)   │     ┌─────────────┐
       │            └──────────────┘────▶│    Redis    │
       │                    │           └─────────────┘
       ▼                    ▼
┌─────────────┐     ┌──────────────┐
│  Mini App   │────▶│    Nginx     │
│  (Next.js)  │     │  + SSL       │
└─────────────┘     └──────────────┘
```

## نصب سریع (Ubuntu 22.04+)

```bash
curl -sSL https://raw.githubusercontent.com/mohamadalira/token-reward-bot/main/install.sh | bash
```

اسکریپت از شما می‌پرسد:
- Telegram Bot Token
- Admin Telegram ID
- PostgreSQL / Redis Password (خودکار تولید می‌شود اگر خالی بگذارید)
- Domain + SSL Email
- Plisio API Token (فقط یک توکن — Secret جدا لازم نیست)

Webhook و WebApp URL خودکار از دامنه ساخته می‌شوند. SSL با Certbot خودکار گرفته می‌شود.

## نصب دستی (Docker)

```bash
# 1. Clone
git clone https://github.com/YOUR_REPO/token-reward-bot.git
cd token-reward-bot

# 2. Configure
cp .env.example .env
# Edit .env with your values

# 3. Start
docker compose up -d --build

# 4. Check logs
docker compose logs -f backend
```

## متغیرهای محیطی

| Variable | Description |
|----------|-------------|
| `BOT_TOKEN` | توکن ربات تلگرام |
| `ADMIN_IDS` | آیدی ادمین‌ها (comma-separated) |
| `POSTGRES_PASSWORD` | رمز PostgreSQL |
| `REDIS_PASSWORD` | رمز Redis |
| `WEBAPP_URL` | آدرس Mini App |
| `PLISIO_API_KEY` | API Token پلیسیو (فقط همین کافیه) |
| `PLISIO_SECRET_KEY` | اختیاری — اگر خالی باشد همان API Token استفاده می‌شود |
| `WEBHOOK_URL` | URL webhook پرداخت |

## دستورات ادمین (تلگرام)

| Command | Description |
|---------|-------------|
| `/set_setting bot_mode combined` | تغییر حالت ربات |
| `/set_setting referral_reward 50` | پاداش دعوت |
| `/add_mandatory CHANNEL_ID عنوان` | کانال اجباری |
| `/add_config نام\|قیمت\|نوع\|دسته\|موجودی` | افزودن کانفیگ |
| `/add_tokens USER_ID AMOUNT` | افزودن توکن |
| `/ban USER_ID` | بن کاربر |
| `/approve_sponsor ID` | تایید اسپانسر |
| `/approve_payment ID` | تایید رسید |

## API Endpoints

Base URL: `https://yourdomain.com/api`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/user/profile` | پروفایل کاربر |
| GET | `/user/tasks` | تسک‌های موجود |
| POST | `/user/tasks/{id}/verify` | تایید عضویت |
| GET | `/user/shop` | محصولات فروشگاه |
| POST | `/user/shop/{id}/purchase` | خرید |
| GET | `/sponsor/dashboard` | داشبورد اسپانسر |
| GET | `/admin/dashboard` | داشبورد ادمین |
| POST | `/webhook/plisio` | Webhook پرداخت |

Authentication: Header `X-Telegram-Init-Data`

## تست

```bash
cd backend
pip install -r requirements.txt
pytest -v
```

## ساختار پروژه

```
├── backend/           # Python (Aiogram + FastAPI)
│   ├── app/
│   │   ├── bot/       # Handlers, Keyboards, Middlewares
│   │   ├── api/       # REST API for Mini App
│   │   ├── core/      # Config, DB, Redis, Security
│   │   ├── models/    # SQLAlchemy models
│   │   ├── repositories/
│   │   ├── services/
│   │   └── locales/   # Persian i18n
│   ├── alembic/       # DB migrations
│   └── tests/
├── mini-app/          # Next.js Telegram Mini App
├── nginx/             # Reverse proxy config
├── install.sh         # Ubuntu one-command installer
└── docker-compose.yml
```

## زبان

تمام رابط کاربری به **فارسی** است. متن‌ها در `backend/app/locales/fa.py` ذخیره شده‌اند.

## License

MIT
