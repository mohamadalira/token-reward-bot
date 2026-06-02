#!/usr/bin/env bash
# Fix: .env POSTGRES_PASSWORD does not match existing postgres volume (after reinstall).
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/tokenbot}"
cd "$INSTALL_DIR" || exit 1

if [[ ! -f .env ]]; then
  echo "Missing .env in $INSTALL_DIR"
  exit 1
fi

# shellcheck disable=SC1091
set -a
source .env
set +a

escape_sql() {
  printf "%s" "$1" | sed "s/'/''/g"
}

if [[ "${RESET_DB:-}" == "1" ]]; then
  echo "RESET_DB=1 — removing postgres volume (ALL bot data will be lost)..."
  docker compose down
  docker volume rm tokenbot_postgres_data 2>/dev/null \
    || docker volume rm "$(docker volume ls -q | grep postgres_data | head -1)" 2>/dev/null \
    || true
  docker compose up -d postgres redis
  echo "Waiting for postgres..."
  sleep 8
fi

if ! docker ps --format '{{.Names}}' | grep -q '^tokenbot_postgres$'; then
  echo "tokenbot_postgres is not running. Start: docker compose up -d postgres"
  exit 1
fi

PG_USER="${POSTGRES_USER:-tokenbot}"
PG_PASS_ESC="$(escape_sql "${POSTGRES_PASSWORD}")"

echo "Syncing PostgreSQL password for user '${PG_USER}' to match .env ..."
docker exec tokenbot_postgres psql -U postgres -d postgres -v ON_ERROR_STOP=1 \
  -c "ALTER USER \"${PG_USER}\" WITH PASSWORD '${PG_PASS_ESC}';"

echo "Restarting backend and nginx..."
docker compose restart backend nginx 2>/dev/null || docker compose restart backend

sleep 5
echo ""
echo "=== Backend status ==="
docker ps --filter name=tokenbot_backend --format '{{.Names}} {{.Status}}'
echo ""
echo "=== Last log lines ==="
docker logs tokenbot_backend --tail 15 2>&1
