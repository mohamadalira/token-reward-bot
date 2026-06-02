#!/usr/bin/env bash
# Quick diagnostics when bot does not reply to /start
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/tokenbot}"
cd "$INSTALL_DIR" 2>/dev/null || { echo "Not found: $INSTALL_DIR"; exit 1; }

echo "=== Containers ==="
docker ps -a --filter name=tokenbot_ --format 'table {{.Names}}\t{{.Status}}'

echo ""
echo "=== Backend logs (last 40 lines) ==="
docker logs tokenbot_backend --tail 40 2>&1 || echo "tokenbot_backend not running"

echo ""
echo "=== .env BOT_TOKEN (masked) ==="
if [[ -f .env ]]; then
  tok=$(grep '^BOT_TOKEN=' .env | cut -d= -f2- || true)
  if [[ -n "$tok" ]]; then
    echo "BOT_TOKEN length: ${#tok} chars"
  else
    echo "BOT_TOKEN missing in .env!"
  fi
  grep '^ADMIN_IDS=' .env || true
else
  echo ".env not found"
fi

echo ""
echo "=== Telegram API (getMe) ==="
if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  source .env
  if [[ -n "${BOT_TOKEN:-}" ]]; then
    resp=$(curl -fsS --max-time 15 "https://api.telegram.org/bot${BOT_TOKEN}/getMe" 2>&1) || resp="FAILED: $resp"
    echo "$resp"
    echo ""
    echo "=== Webhook (must be empty url for polling) ==="
    curl -fsS --max-time 15 "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo" 2>&1 || true
  fi
fi

echo ""
echo "=== API health via nginx ==="
port=$(grep '^TOKENBOT_HTTP_PORT=' .env 2>/dev/null | cut -d= -f2 || echo 8080)
curl -fsS --max-time 5 "http://127.0.0.1:${port}/api/health" 2>&1 || echo "health check failed on port ${port}"

echo ""
echo "=== Common fixes ==="
echo "  DB password mismatch:  bash scripts/fix-db-password.sh"
echo "  Webhook / polling:     bash scripts/fix-bot.sh"
echo "  Fresh DB (data loss):  RESET_DB=1 bash scripts/fix-db-password.sh"
