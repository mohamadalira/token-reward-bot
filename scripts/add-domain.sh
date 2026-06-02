#!/usr/bin/env bash
# Add domain + SSL to an existing IP-only install (does NOT touch other bots/services).
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/tokenbot}"
cd "$INSTALL_DIR" || { echo "Install dir not found: $INSTALL_DIR"; exit 1; }

read_tty() {
  local var="$1"
  local prompt="$2"
  local val
  if [[ -t 0 ]]; then
    read -r -p "$prompt" val </dev/tty
  else
    read -r -p "$prompt" val </dev/tty
  fi
  printf -v "$var" '%s' "$val"
}

port_in_use() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -tlnH 2>/dev/null | awk -v p=":${port}" '$4 ~ p {found=1} END {exit !found}'
  elif command -v netstat >/dev/null 2>&1; then
    netstat -tln 2>/dev/null | grep -q ":${port} "
  else
    return 1
  fi
}

find_free_port() {
  local start="${1:-8443}"
  local port="$start"
  while port_in_use "$port"; do
    port=$((port + 1))
  done
  echo "$port"
}

detect_public_ip() {
  curl -4 -fsS --max-time 5 ifconfig.me 2>/dev/null \
    || curl -4 -fsS --max-time 5 icanhazip.com 2>/dev/null \
    || hostname -I 2>/dev/null | awk '{print $1}' \
    || echo "127.0.0.1"
}

if [[ ! -f .env ]]; then
  echo "No .env found. Run install.sh first."
  exit 1
fi

# shellcheck disable=SC1091
source .env 2>/dev/null || true

read_tty DOMAIN "Domain (e.g. bot.example.com): "
if [[ -z "${DOMAIN:-}" ]]; then
  echo "Domain is required for this script."
  exit 1
fi

read_tty SSL_EMAIL "Email for Let's Encrypt: "
if [[ -z "${SSL_EMAIL:-}" ]]; then
  echo "SSL email is required."
  exit 1
fi

HTTPS_PORT="${TOKENBOT_HTTPS_PORT:-8443}"
if port_in_use "$HTTPS_PORT"; then
  HTTPS_PORT="$(find_free_port 8443)"
  echo "Port 8443 busy — using HTTPS port $HTTPS_PORT"
fi

HTTP_PORT="${TOKENBOT_HTTP_PORT:-8080}"

export DOMAIN SSL_EMAIL HTTP_PORT HTTPS_PORT
export TOKENBOT_HTTP_PORT="$HTTP_PORT"
export TOKENBOT_HTTPS_PORT="$HTTPS_PORT"
export SSL_ENABLED=true
export WEBAPP_URL="https://${DOMAIN}"
export API_PUBLIC_URL="https://${DOMAIN}/api"

# Update .env
upsert_env() {
  local key="$1"
  local val="$2"
  if grep -q "^${key}=" .env 2>/dev/null; then
    sed -i "s|^${key}=.*|${key}=${val}|" .env
  else
    echo "${key}=${val}" >> .env
  fi
}

upsert_env DOMAIN "$DOMAIN"
upsert_env SSL_EMAIL "$SSL_EMAIL"
upsert_env SSL_ENABLED true
upsert_env TOKENBOT_HTTP_PORT "$HTTP_PORT"
upsert_env TOKENBOT_HTTPS_PORT "$HTTPS_PORT"
upsert_env WEBAPP_URL "$WEBAPP_URL"
upsert_env API_PUBLIC_URL "$API_PUBLIC_URL"

mkdir -p nginx/conf.d nginx/ssl

cat > nginx/conf.d/tokenbot.conf <<NGINX
server {
    listen 80;
    server_name ${DOMAIN};

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://\$host\$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name ${DOMAIN};

    ssl_certificate /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    location /api/ {
        proxy_pass http://backend:8000/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /webhook/ {
        proxy_pass http://backend:8000/webhook/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }

    location / {
        proxy_pass http://mini-app:3000/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
NGINX

# Allow HTTPS port (do not reset UFW)
if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q "Status: active"; then
  ufw allow "${HTTPS_PORT}/tcp" comment 'tokenbot-https' 2>/dev/null || true
fi

echo "Obtaining SSL certificate..."
docker compose -f docker-compose.yml -f docker-compose.ssl.yml run --rm certbot certonly \
  --webroot -w /var/www/certbot \
  -d "$DOMAIN" \
  --email "$SSL_EMAIL" \
  --agree-tos --non-interactive --no-eff-email || {
    echo "Certbot failed. Check DNS points to $(detect_public_ip) and port ${HTTP_PORT} is reachable."
    exit 1
  }

echo "Rebuilding mini-app with new WEBAPP_URL..."
export BUILD_MINIAPP=1
docker compose -f docker-compose.yml -f docker-compose.ssl.yml --profile miniapp --profile ssl build mini-app
docker compose -f docker-compose.yml -f docker-compose.ssl.yml --profile miniapp --profile ssl up -d

echo ""
echo "============================================"
echo " Domain added successfully"
echo "============================================"
echo "  Domain:   https://${DOMAIN}"
echo "  HTTP:     port ${HTTP_PORT} (redirects to HTTPS)"
echo "  HTTPS:    port ${HTTPS_PORT}"
echo ""
echo " Set Mini App URL in @BotFather:"
echo "   ${WEBAPP_URL}"
echo "============================================"
