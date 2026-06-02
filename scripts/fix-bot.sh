#!/usr/bin/env bash
set -euo pipefail
INSTALL_DIR="${INSTALL_DIR:-/opt/tokenbot}"
cd "$INSTALL_DIR"

if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  source .env
  if [[ -n "${BOT_TOKEN:-}" ]]; then
    echo "Deleting Telegram webhook..."
    curl -fsS "https://api.telegram.org/bot${BOT_TOKEN}/deleteWebhook?drop_pending_updates=true" || true
  fi
fi

echo "Restarting backend..."
docker compose restart backend
sleep 5
docker logs tokenbot_backend --tail 20
