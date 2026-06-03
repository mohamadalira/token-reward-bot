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
# روش پایدار (پیشنهادی — ورودی Token درست خوانده می‌شود)
curl -fsSL https://raw.githubusercontent.com/mohamadalira/token-reward-bot/main/install.sh -o install.sh
chmod +x install.sh
sudo bash install.sh
```

نصب کامل بدون هیچ سوالی (پیشنهادی):

```bash
curl -fsSL https://raw.githubusercontent.com/mohamadalira/token-reward-bot/main/install.sh -o install.sh
chmod +x install.sh
sudo BOT_TOKEN="YOUR_TOKEN" ADMIN_IDS="123456789" SKIP_SWAP=1 bash install.sh
```

برای ساخت Mini App: `BUILD_MINIAPP=1` اضافه کنید.

`curl ... | sudo bash` گاهی ورودی را خالی می‌خواند — از روش بالا استفاده کنید.

### هم‌زیستی با ربات‌های دیگر

- **هیچ سرویس دیگری متوقف نمی‌شود** (Apache، Nginx سیستم، کانتینرهای دیگر دست نخورده می‌مانند).
- فقط کانتینرهای `tokenbot_*` قبلی پاک می‌شوند.
- پورت پیش‌فرض **8080** است (نه 80/443) تا با ربات‌های روی 80 تداخل نداشته باشد.
- اگر 80/443 آزاد باشد و دامنه بدهید، می‌توانید همان پورت‌ها را انتخاب کنید.

### نصب بدون دامنه

در پرامپت Domain **Enter** بزنید. ربات با polling کار می‌کند؛ وب و Mini App روی:

`http://IP_SERVER:8080`

دامنه و SSL بعداً:

```bash
cd /opt/tokenbot && sudo bash scripts/add-domain.sh
```

### ورودی‌های نصب

- Telegram Bot Token
- Admin Telegram ID
- **Domain** (اختیاری — خالی = فقط IP:PORT)
- Plisio API Token (اختیاری)
- ساخت Mini App (اختیاری در حالت بدون دامنه)

> **SSL:** برای Let's Encrypt معمولاً پورت **80** باید به چالش ACME برسد. اگر Apache روی 80 است، اول بدون دامنه نصب کنید یا `/.well-known` را در Apache به این ربات پروکسی کنید.

Webhook و WebApp URL خودکار ساخته می‌شوند.

## آپدیت روی سرور (بعد از fix باگ)

روی ویندوز: تغییر کد → `git push`  
روی سرور:

```bash
cd /opt/tokenbot
bash scripts/update-server.sh          # فقط backend (پیش‌فرض)
bash scripts/update-server.sh miniapp  # Mini App
bash scripts/update-server.sh all      # همه سرویس‌ها
```

`.env` و دیتابیس دست نخورده می‌مانند.

```bash
NO_CACHE=1 bash scripts/update-server.sh backend   # build از صفر
SKIP_BUILD=1 bash scripts/update-server.sh backend # فقط restart
```

## نصب دستی (Docker)

```bash
# 1. Clone
git clone https://github.com/mohamadalira/token-reward-bot.git
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
| `TOKENBOT_HTTP_PORT` | پورت HTTP روی سرور (پیش‌فرض 8080) |
| `TOKENBOT_HTTPS_PORT` | پورت HTTPS (پیش‌فرض 8443 یا 443) |
| `DOMAIN` | دامنه (اختیاری) |
| `SSL_ENABLED` | true/false |
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
