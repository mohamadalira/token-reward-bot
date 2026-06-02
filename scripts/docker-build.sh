#!/usr/bin/env bash
# Build images with visible progress (run on server)
set -euo pipefail
cd "$(dirname "$0")/.."

export DOCKER_BUILDKIT=1
export COMPOSE_HTTP_TIMEOUT=600

if [[ ! -f /swapfile ]] && [[ $(free -m | awk '/^Mem:/{print $2}') -lt 2048 ]]; then
  echo "Creating 2GB swap..."
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
fi

echo ">>> Building backend (2-5 min)..."
docker compose build --progress=plain backend

if [[ "${1:-}" == "--with-miniapp" ]]; then
  echo ">>> Building mini-app (15-30 min)..."
  docker compose --profile miniapp build --progress=plain mini-app
else
  echo ">>> Skipping mini-app. Use: $0 --with-miniapp"
fi

echo ">>> Done. Start: docker compose up -d"
echo ">>> With miniapp: docker compose --profile miniapp up -d"
