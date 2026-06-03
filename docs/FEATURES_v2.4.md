# Feature update changelog — see README

## v2.4.0 Highlights

- Shop categories (`shop_categories` table) + bulk config upload
- All bot texts stored in DB (`settings` + `TextService`)
- User menus → Inline Keyboard (leaderboard removed, sponsor promoted)
- Enhanced sponsor task cards (description + join buttons)
- Admin: text manager, payment settings, sponsor channel wizard
- Alembic migration `002_feature_update`
- API: `GET /api/user/shop/categories`

Deploy on server:
```bash
cd /opt/tokenbot && bash scripts/update-server.sh backend
docker compose exec backend alembic upgrade head
```
