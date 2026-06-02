#!/usr/bin/env bash
set -euo pipefail

# Token Reward Bot - Ubuntu 22.04+ Installer
# Usage (recommended - download first):
#   curl -sSL https://raw.githubusercontent.com/mohamadalira/token-reward-bot/main/install.sh -o install.sh
#   sed -i 's/\r$//' install.sh
#   chmod +x install.sh && sudo bash install.sh
#
# Or pipe (may fail on some shells):
#   curl -sSL https://raw.githubusercontent.com/mohamadalira/token-reward-bot/main/install.sh | sudo bash

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

DEFAULT_INSTALL_DIR="/opt/tokenbot"
GITHUB_REPO="${GITHUB_REPO:-mohamadalira/token-reward-bot}"
GITHUB_BRANCH="${GITHUB_BRANCH:-main}"
REPO_URL="${REPO_URL:-https://github.com/${GITHUB_REPO}.git}"

log()  { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
info() { echo -e "${BLUE}[i]${NC} $1"; }
err()  { echo -e "${RED}[X]${NC} $1"; exit 1; }

clone_project() {
    local target="$1"

    if [[ -f "$target/docker-compose.yml" ]]; then
        return 0
    fi

    log "دریافت پروژه از GitHub (${GITHUB_REPO})..."
    mkdir -p "$target"

    # Public repo: download archive (no git, no password)
    local tarball="https://github.com/${GITHUB_REPO}/archive/refs/heads/${GITHUB_BRANCH}.tar.gz"
    if curl -fsSL "$tarball" | tar xz -C "$target" --strip-components=1 2>/dev/null; then
        log "proje download shod"
        return 0
    fi

    # Private repo: git clone with optional token
    apt-get install -y -qq git
    export GIT_TERMINAL_PROMPT=0

    if [[ -n "${GITHUB_TOKEN:-}" ]]; then
        if git clone --depth 1 -b "$GITHUB_BRANCH" \
            "https://${GITHUB_TOKEN}@github.com/${GITHUB_REPO}.git" "$target" 2>/dev/null; then
            log "proje clone shod (ba token)"
            return 0
        fi
    fi

    if git clone --depth 1 -b "$GITHUB_BRANCH" "$REPO_URL" "$target" 2>/dev/null; then
        log "proje clone shod"
        return 0
    fi

    err "Clone failed. Make repo Public or set GITHUB_TOKEN, or copy files to /opt/tokenbot manually."
}

prompt() {
    local var_name="$1"
    local message="$2"
    local default="${3:-}"
    local secret="${4:-false}"
    local value=""

    if [[ -n "$default" ]]; then
        if [[ "$secret" == "true" ]]; then
            read -rsp "$message [$default]: " value; echo
        else
            read -rp "$message [$default]: " value
        fi
    else
        if [[ "$secret" == "true" ]]; then
            read -rsp "$message: " value; echo
        else
            read -rp "$message: " value
        fi
    fi

    if [[ -z "$value" ]]; then
        value="$default"
    fi
    printf -v "$var_name" '%s' "$value"
}

prompt_required() {
    local var_name="$1"
    local message="$2"
    local value=""
    while [[ -z "$value" ]]; do
        read -rp "$message: " value
        [[ -z "$value" ]] && warn "این فیلد اجباریه"
    done
    printf -v "$var_name" '%s' "$value"
}

generate_password() {
    openssl rand -base64 24 | tr -dc 'A-Za-z0-9' | head -c 32
}

# ─── Root check ───────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    err "اسکریپت رو با sudo اجرا کن:\n  curl -sSL install.sh | sudo bash"
fi

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║     Token Reward Bot — نصب خودکار       ║"
echo "╚══════════════════════════════════════════╝"
echo ""
info "همه تنظیمات رو ازت می‌پرسم. Enter = مقدار پیش‌فرض"
echo ""

# ─── Interactive configuration ────────────────────────────────
prompt_required BOT_TOKEN "🤖 Telegram Bot Token"
prompt_required ADMIN_IDS  "👤 Admin Telegram ID (چندتا با , جدا کن)"

AUTO_PG_PASS="$(generate_password)"
prompt POSTGRES_PASSWORD "🗄 PostgreSQL Password (خالی=خودکار)" "$AUTO_PG_PASS" true
[[ -z "$POSTGRES_PASSWORD" ]] && POSTGRES_PASSWORD="$AUTO_PG_PASS"

AUTO_REDIS_PASS="$(generate_password)"
prompt REDIS_PASSWORD "🔴 Redis Password (خالی=خودکار)" "$AUTO_REDIS_PASS" true
[[ -z "$REDIS_PASSWORD" ]] && REDIS_PASSWORD="$AUTO_REDIS_PASS"

prompt_required DOMAIN "🌐 Domain (مثال: bot.example.com)"
prompt_required SSL_EMAIL "📧 Email برای SSL (Certbot)"

read -rp "Plisio API Token (khali=ghayrefaal): " PLISIO_API_KEY
PLISIO_ENABLED="false"
if [ -n "${PLISIO_API_KEY}" ]; then
    PLISIO_ENABLED="true"
    info "Plisio faal shod - hamin token baraye API va Webhook"
fi
if [ "${PLISIO_ENABLED}" = "false" ]; then
    warn "Plisio gheyrefaal - baad az panel admin faalesh kon"
fi

# Auto-generated values
API_SECRET_KEY="$(openssl rand -hex 32)"
WEBAPP_URL="https://${DOMAIN}"
WEBHOOK_URL="https://${DOMAIN}/webhook/plisio"

echo ""
info "── خلاصه تنظیمات ──"
echo "  Domain:    $DOMAIN"
echo "  WebApp:    $WEBAPP_URL"
echo "  Webhook:   $WEBHOOK_URL"
echo "  Plisio:    $PLISIO_ENABLED"
echo ""
read -rp "ادامه نصب؟ (y/n) [y]: " CONFIRM
CONFIRM="${CONFIRM:-y}"
[[ "$CONFIRM" != "y" && "$CONFIRM" != "Y" ]] && err "نصب لغو شد"

# ─── Detect install directory ─────────────────────────────────
SCRIPT_PATH="${BASH_SOURCE[0]:-$0}"
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" 2>/dev/null && pwd || echo "")"

if [[ -n "$SCRIPT_DIR" && -f "$SCRIPT_DIR/docker-compose.yml" ]]; then
    INSTALL_DIR="$SCRIPT_DIR"
    log "استفاده از فایل‌های محلی: $INSTALL_DIR"
else
    INSTALL_DIR="${INSTALL_DIR:-$DEFAULT_INSTALL_DIR}"
    apt-get update -qq
    apt-get install -y -qq curl ca-certificates tar
    clone_project "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# ─── Install system dependencies ──────────────────────────────
log "آپدیت سیستم..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get upgrade -y -qq

log "نصب ابزارهای مورد نیاز..."
apt-get install -y -qq \
    curl \
    wget \
    git \
    ufw \
    openssl \
    ca-certificates \
    gnupg \
    lsb-release \
    apt-transport-https \
    software-properties-common

# Docker
if ! command -v docker &>/dev/null; then
    log "نصب Docker..."
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
        > /etc/apt/sources.list.d/docker.list
    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
    systemctl enable docker
    systemctl start docker
else
    log "Docker از قبل نصبه"
fi

if ! docker compose version &>/dev/null; then
    err "Docker Compose Plugin پیدا نشد"
fi

# ─── Firewall ─────────────────────────────────────────────────
log "تنظیم فایروال (UFW)..."
ufw --force reset >/dev/null 2>&1 || true
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'
ufw --force enable

# ─── Write .env ───────────────────────────────────────────────
log "ساخت فایل .env..."
cat > .env <<EOF
# Generated by install.sh on $(date -Iseconds)

# Telegram
BOT_TOKEN=${BOT_TOKEN}
ADMIN_IDS=${ADMIN_IDS}
WEBAPP_URL=${WEBAPP_URL}

# Database
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=tokenbot
POSTGRES_USER=tokenbot
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=${REDIS_PASSWORD}

# API
API_HOST=0.0.0.0
API_PORT=8000
API_SECRET_KEY=${API_SECRET_KEY}
WEBHOOK_PATH=/webhook/plisio
WEBHOOK_URL=${WEBHOOK_URL}

# Plisio
PLISIO_API_KEY=${PLISIO_API_KEY}
PLISIO_SECRET_KEY=
PLISIO_ENABLED=${PLISIO_ENABLED}

# Domain & SSL
DOMAIN=${DOMAIN}
SSL_EMAIL=${SSL_EMAIL}

# App
DEBUG=false
LOG_LEVEL=INFO
DEFAULT_LOCALE=fa
USE_PERSIAN_NUMBERS=true
USE_JALALI_DATES=true
EOF
chmod 600 .env

# ─── Nginx config generators ────────────────────────────────
mkdir -p nginx/conf.d

write_nginx_http() {
    cat > nginx/conf.d/default.conf <<NGINX
# HTTP-only (pre-SSL) — generated by install.sh
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN};

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
        try_files \$uri =404;
    }

    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /webhook/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location / {
        proxy_pass http://mini-app:3000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
NGINX
}

write_nginx_ssl() {
    cat > nginx/conf.d/default.conf <<NGINX
# HTTP → HTTPS redirect + ACME
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN};

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
        try_files \$uri =404;
    }

    location / {
        return 301 https://\$host\$request_uri;
    }
}

# HTTPS
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name ${DOMAIN};

    ssl_certificate     /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /webhook/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location / {
        proxy_pass http://mini-app:3000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
NGINX
}

write_nginx_http
log "Nginx (HTTP) آماده شد"

# ─── Build & start core services ──────────────────────────────
log "ساخت Docker images..."
docker compose build --quiet 2>/dev/null || docker compose build

log "راه‌اندازی PostgreSQL و Redis..."
docker compose up -d postgres redis

info "منتظر آماده شدن دیتابیس..."
for i in $(seq 1 30); do
    if docker compose exec -T postgres pg_isready -U tokenbot &>/dev/null; then
        break
    fi
    sleep 2
done

log "راه‌اندازی Backend و Mini App..."
docker compose up -d backend mini-app

log "راه‌اندازی Nginx (HTTP)..."
docker compose up -d nginx

# ─── SSL with Certbot ─────────────────────────────────────────
log "دریافت SSL از Let's Encrypt (Certbot)..."
info "مطمئن شو DNS دامنه $DOMAIN به IP این سرور اشاره میکنه"

# Wait for nginx
sleep 3

if docker compose run --rm --entrypoint certbot certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email "$SSL_EMAIL" \
    --agree-tos \
    --no-eff-email \
    --non-interactive \
    -d "$DOMAIN"; then

    log "SSL daryaft shod"
    write_nginx_ssl
    docker compose exec nginx nginx -s reload 2>/dev/null || docker compose restart nginx
else
    warn "دریافت SSL ناموفق بود"
    warn "بعداً دستی اجرا کن:"
    warn "  cd $INSTALL_DIR"
    warn "  docker compose run --rm --entrypoint certbot certbot certonly --webroot -w /var/www/certbot -d $DOMAIN --email $SSL_EMAIL --agree-tos"
fi

# ─── Start certbot renew + remaining services ───────────────
log "راه‌اندازی Certbot (تمدید خودکار)..."
docker compose up -d certbot

# ─── Systemd service ──────────────────────────────────────────
log "ساخت سرویس systemd..."
cat > /etc/systemd/system/tokenbot.service <<EOF
[Unit]
Description=Token Reward Bot
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=${INSTALL_DIR}
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable tokenbot.service

# ─── Save credentials ─────────────────────────────────────────
CREDS_FILE="${INSTALL_DIR}/.install-credentials.txt"
cat > "$CREDS_FILE" <<EOF
Token Reward Bot — اطلاعات نصب
تاریخ: $(date)
Domain: ${DOMAIN}
WebApp: ${WEBAPP_URL}
Webhook: ${WEBHOOK_URL}
PostgreSQL Password: ${POSTGRES_PASSWORD}
Redis Password: ${REDIS_PASSWORD}
API Secret: ${API_SECRET_KEY}
Plisio: ${PLISIO_ENABLED}
EOF
chmod 600 "$CREDS_FILE"

# ─── Done ─────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║          نصب با موفقیت انجام شد ✅         ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "  🌐 Mini App:  ${WEBAPP_URL}"
echo "  🔗 Webhook:   ${WEBHOOK_URL}"
echo "  📁 مسیر:      ${INSTALL_DIR}"
echo "  🔐 رمزها:     ${CREDS_FILE}"
echo ""
echo "  دستورات:"
echo "    cd ${INSTALL_DIR} && docker compose logs -f backend"
echo "    systemctl status tokenbot"
echo "    docker compose ps"
echo ""
warn "فایل ${CREDS_FILE} رو امن نگه دار و بعداً پاک کن"
echo ""
