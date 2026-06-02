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

PG_USER="${POSTGRES_USER:-tokenbot}"
PG_DB="${POSTGRES_DB:-tokenbot}"

postgres_volume_name() {
  docker volume ls -q | grep -E 'postgres_data$' | head -1
}

if [[ "${RESET_DB:-}" == "1" ]]; then
  echo "RESET_DB=1 — removing postgres volume (ALL bot data will be lost)..."
  docker compose down
  vol="$(postgres_volume_name)"
  if [[ -n "$vol" ]]; then
    docker volume rm "$vol" || true
  fi
  docker compose up -d postgres redis
  echo "Waiting for postgres (fresh volume uses .env password automatically)..."
  for i in $(seq 1 30); do
    if docker exec tokenbot_postgres pg_isready -U "$PG_USER" -d "$PG_DB" >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
  echo "Starting all services..."
  docker compose up -d
  sleep 5
  docker logs tokenbot_backend --tail 20 2>&1 || true
  echo "Done. Fresh DB — no password sync needed."
  exit 0
fi

if ! docker ps --format '{{.Names}}' | grep -q '^tokenbot_postgres$'; then
  echo "tokenbot_postgres is not running. Start: docker compose up -d postgres"
  exit 1
fi

# Test current .env password (TCP inside container)
if PGPASSWORD="${POSTGRES_PASSWORD}" docker exec -e PGPASSWORD \
  tokenbot_postgres psql -h 127.0.0.1 -U "$PG_USER" -d "$PG_DB" -c 'SELECT 1' >/dev/null 2>&1; then
  echo "PostgreSQL password already matches .env — OK."
else
  echo "Password mismatch — syncing user '${PG_USER}' to .env (local trust auth)..."
  PG_PASS_ESC="$(escape_sql "${POSTGRES_PASSWORD}")"
  # Alpine image: superuser is POSTGRES_USER (tokenbot), not "postgres"
  docker exec tokenbot_postgres psql -U "$PG_USER" -d postgres -v ON_ERROR_STOP=1 \
    -c "ALTER USER \"${PG_USER}\" WITH PASSWORD '${PG_PASS_ESC}';"
  echo "Password updated."
fi

echo "Restarting backend and nginx..."
docker compose restart backend nginx 2>/dev/null || docker compose restart backend

sleep 5
echo ""
echo "=== Backend status ==="
docker ps --filter name=tokenbot_backend --format '{{.Names}} {{.Status}}'
echo ""
echo "=== Last log lines ==="
docker logs tokenbot_backend --tail 20 2>&1
