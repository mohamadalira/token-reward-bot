# API Documentation

## Authentication

All user/sponsor/admin endpoints require Telegram WebApp init data:

```
X-Telegram-Init-Data: query_id=...&user=...&auth_date=...&hash=...
```

## User API

### GET /api/user/profile

Returns user profile with token balance, stats, referral link.

**Response:**
```json
{
  "id": 123456789,
  "username": "user",
  "first_name": "Ali",
  "token_balance": 1250,
  "total_earned": 2000,
  "total_spent": 750,
  "referral_count": 5,
  "rank": 12,
  "referral_link": "https://t.me/bot?start=ref_abc123",
  "join_date": "۱۴۰۵/۰۳/۱۲"
}
```

### GET /api/user/tasks

Returns available sponsor channel tasks.

### POST /api/user/tasks/{channel_id}/verify

Verifies channel membership and grants reward.

### GET /api/user/shop

Returns available config products.

### POST /api/user/shop/{product_id}/purchase

Purchases a config product. Deducts tokens and returns config data.

## Sponsor API

### GET /api/sponsor/dashboard

Returns wallet info and campaign list with analytics.

### GET /api/sponsor/campaigns/{id}/analytics

Returns hourly view distribution and conversion metrics.

### POST /api/sponsor/campaigns/{id}/pause

Pauses an active campaign.

### POST /api/sponsor/campaigns/{id}/resume

Resumes a paused campaign.

## Admin API

Requires admin Telegram ID.

### GET /api/admin/dashboard

Returns platform-wide statistics and revenue.

### GET /api/admin/settings

Returns all bot settings.

### PUT /api/admin/settings

```json
{ "key": "bot_mode", "value": "combined" }
```

### POST /api/admin/plisio/test

Tests Plisio API connection and credentials.

## Webhook

### POST /webhook/plisio

Plisio payment callback. Validates HMAC-SHA1 signature.

**Form fields:** status, txn_id, amount, verify_hash, etc.

## Error Codes

| Code | Description |
|------|-------------|
| 401 | Invalid init data |
| 403 | Banned / Not admin |
| 404 | Resource not found |
| 400 | Invalid webhook signature |
