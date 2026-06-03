#!/usr/bin/env bash
# Emergency: disable mandatory channel join and remove all mandatory channels.
set -euo pipefail

cd "$(dirname "$0")/.."

POSTGRES_USER="${POSTGRES_USER:-tokenbot}"
POSTGRES_DB="${POSTGRES_DB:-tokenbot}"

echo "Disabling force_join and clearing mandatory_channels..."
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
UPDATE settings SET value = 'false' WHERE key = 'force_join_enabled';
INSERT INTO settings (key, value) SELECT 'force_join_enabled', 'false'
  WHERE NOT EXISTS (SELECT 1 FROM settings WHERE key = 'force_join_enabled');
DELETE FROM mandatory_channels;
"
echo "Done. Restart backend: docker compose restart backend"
