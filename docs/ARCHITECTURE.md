# Architecture

## Clean Architecture Layers

```
Handlers (Telegram) / Routes (FastAPI)
           │
           ▼
       Services (Business Logic)
           │
           ▼
      Repositories (Data Access)
           │
           ▼
    Models (SQLAlchemy ORM)
```

## Database Schema

### Core Tables
- **users** - User accounts, token balances, referral codes
- **referrals** - Referral tracking (one per referred user)
- **token_transactions** - All token movements with audit trail
- **mandatory_channels** - Required channels for bot access
- **sponsor_channels** - Task/reward channels
- **config_products** - VPN config shop items
- **purchases** - Purchase history

### Sponsor System
- **sponsors** - Sponsor profiles with wallet
- **campaigns** - Advertising campaigns with budget
- **campaign_rewards** - Per-user reward tracking (duplicate prevention)
- **campaign_views** - View analytics for conversion tracking
- **task_rewards** - Admin-managed channel rewards
- **payments** - Plisio and manual card payments

### System
- **settings** - Key-value bot configuration
- **admin_logs** - Admin action audit trail
- **notifications** - In-app notifications

## Bot Modes

| Mode | Referral | Tasks |
|------|----------|-------|
| referral | ✅ | ❌ |
| task | ❌ | ✅ |
| combined | ✅ | ✅ |

## Token Economy

```
User earns tokens ──▶ Referral / Task reward
User spends tokens ──▶ Config purchase
Sponsor buys tokens ──▶ Plisio / Manual card
Sponsor allocates ──▶ Campaign budget
Campaign deducts ──▶ Per-join user reward
```

## Security

- **Rate Limiting**: Redis-based, 30 req/min per user
- **Anti-Spam**: 2-second cooldown between actions
- **Duplicate Prevention**: Unique constraints on rewards
- **Webhook Validation**: HMAC-SHA1 Plisio signature
- **SQL Injection**: SQLAlchemy parameterized queries
- **Audit Logs**: All admin actions logged

## Scalability

- Async I/O throughout (aiogram, FastAPI, asyncpg)
- Redis for session storage, caching, rate limits
- Connection pool: 20 base + 40 overflow
- Broadcast throttling: 50ms delay between messages
- Indexed foreign keys and unique constraints

## Deployment

```
Internet ──▶ Nginx (SSL) ──▶ Mini App (Next.js :3000)
                          ──▶ Backend (FastAPI+Bot :8000)
                                    ├── PostgreSQL :5432
                                    └── Redis :6379
```

Systemd service ensures auto-restart on boot.
