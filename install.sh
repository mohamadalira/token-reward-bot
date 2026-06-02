#!/usr/bin/env bash
# Token Reward Bot — one-click installer (safe co-existence with other bots)
# Version: 2.3.0
set -euo pipefail

INSTALLER_VERSION="2.3.3"
INSTALL_DIR="/opt/tokenbot"
REPO="mohamadalira/token-reward-bot"
REPO_URL="https://github.com/${REPO}.git"
TARBALL_URL="https://github.com/${REPO}/archive/refs/heads/main.tar.gz"

# ── Re-exec when piped (curl | bash) — must attach real terminal ─────────────
if [[ ! -t 0 ]] && [[ -z "${TOKENBOT_INSTALL_REEXEC:-}" ]]; then
  export TOKENBOT_INSTALL_REEXEC=1
  TMP_SCRIPT="$(mktemp /tmp/tokenbot-install.XXXXXX.sh)"
  curl -fsSL "https://raw.githubusercontent.com/${REPO}/main/install.sh" -o "$TMP_SCRIPT"
  chmod +x "$TMP_SCRIPT"
  # Prefer saved script + tty (works with: curl -o install.sh && sudo bash install.sh)
  if [[ -t 1 ]] && [[ -r /dev/tty ]]; then
    exec bash "$TMP_SCRIPT" "$@" 0</dev/tty
  else
    err "No TTY. Run: curl -fsSL ... -o install.sh && sudo bash install.sh"
    err "Or: sudo BOT_TOKEN=... ADMIN_IDS=... bash install.sh"
    exit 1
  fi
fi

# Persistent TTY fd (opened once — repeated open </dev/tty can fail under sudo)
TOKENBOT_TTY_FD=""
open_tty_fd() {
  if [[ -n "${TOKENBOT_TTY_FD}" ]]; then
    return 0
  fi
  if [[ -r /dev/tty ]] && exec 3</dev/tty 2>/dev/null; then
    TOKENBOT_TTY_FD=3
  fi
}

# ── Helpers ───────────────────────────────────────────────────────────────────
log()  { echo -e "\033[1;32m[INFO]\033[0m  $*"; }
warn() { echo -e "\033[1;33m[WARN]\033[0m  $*"; }
err()  { echo -e "\033[1;31m[ERROR]\033[0m $*" >&2; }

trim_input() {
  local s="$1"
  s="${s//$'\r'/}"
  s="${s#"${s%%[![:space:]]*}"}"
  s="${s%"${s##*[![:space:]]}"}"
  printf '%s' "$s"
}

read_tty() {
  local __name="$1"
  local __prompt="$2"
  local __buf=""

  if [[ -n "${!__name:-}" ]]; then
    printf -v "$__name" '%s' "$(trim_input "${!__name}")"
    return 0
  fi

  # Always print prompt to stderr (visible even when stdout is buffered)
  echo "" >&2
  echo -e "\033[1;36m>>>\033[0m ${__prompt}" >&2

  open_tty_fd

  if [[ -n "${TOKENBOT_TTY_FD}" ]]; then
    read -r __buf <&"${TOKENBOT_TTY_FD}" || true
  elif [[ -r /dev/tty ]]; then
    read -r __buf </dev/tty || true
  elif [[ -t 0 ]]; then
    read -r __buf || true
  else
    read -r __buf </dev/stdin || true
  fi

  __buf="$(trim_input "$__buf")"
  printf -v "$__name" '%s' "$__buf"
}

prompt_required() {
  local __name="$1"
  local __prompt="$2"
  local __val=""
  while true; do
    read_tty "$__name" "$__prompt"
    __val="${!__name:-}"
    if [[ -n "$__val" ]]; then
      printf -v "$__name" '%s' "$__val"
      return 0
    fi
    warn "This field is required. (Tip: download script first, or use BOT_TOKEN=... env)"
  done
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
  local start="${1:-8080}"
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

pick_http_port() {
  # Never steal 80/443 from other services — prefer high ports
  for p in 8080 8081 8090 8888 9080 8181; do
    if ! port_in_use "$p"; then
      echo "$p"
      return
    fi
  done
  find_free_port 9000
}

require_root() {
  if [[ $EUID -ne 0 ]]; then
    err "Run as root: sudo bash install.sh"
    exit 1
  fi
}

install_docker() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    log "Docker already installed."
    return
  fi
  log "Installing Docker..."
  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker 2>/dev/null || true
}

ensure_swap() {
  if [[ "${SKIP_SWAP:-}" == "1" ]]; then
    log "Swap setup skipped (SKIP_SWAP=1)."
    return
  fi
  if swapon --show 2>/dev/null | grep -q .; then
    log "Swap already active — skipping."
    return
  fi
  if [[ -f /swapfile ]]; then
    log "Activating existing /swapfile..."
    swapon /swapfile 2>/dev/null || warn "Could not enable /swapfile (continuing anyway)."
    return
  fi
  log "Adding 2GB swap (may take 1-2 min — set SKIP_SWAP=1 to skip)..."
  fallocate -l 2G /swapfile 2>/dev/null || dd if=/dev/zero of=/swapfile bs=1M count=2048 status=none
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q '/swapfile' /etc/fstab 2>/dev/null || echo '/swapfile none swap sw 0 0' >> /etc/fstab
  log "Swap enabled."
}

# Only stop/remove OUR containers — never touch apache, nginx, or other bots
cleanup_tokenbot_only() {
  log "Cleaning previous tokenbot install (other bots untouched)..."
  if [[ -d "$INSTALL_DIR" ]] && [[ -f "$INSTALL_DIR/docker-compose.yml" ]]; then
    (cd "$INSTALL_DIR" && docker compose down --remove-orphans 2>/dev/null) || true
  fi
  docker rm -f tokenbot_backend tokenbot_postgres tokenbot_redis tokenbot_nginx tokenbot_miniapp tokenbot_certbot 2>/dev/null || true
}

download_source() {
  log "Downloading source..."
  rm -rf "$INSTALL_DIR"
  mkdir -p "$INSTALL_DIR"

  if [[ -n "${GITHUB_TOKEN:-}" ]]; then
    git clone --depth 1 "https://${GITHUB_TOKEN}@github.com/${REPO}.git" "$INSTALL_DIR"
  else
    curl -fsSL "$TARBALL_URL" | tar -xz -C /tmp
    mv "/tmp/token-reward-bot-main"/* "/tmp/token-reward-bot-main"/.[!.]* "$INSTALL_DIR" 2>/dev/null || \
      cp -a "/tmp/token-reward-bot-main/." "$INSTALL_DIR"
    rm -rf "/tmp/token-reward-bot-main"
  fi
}

write_nginx_http_only() {
  local listen_name="${1:-_}"
  cat > nginx/conf.d/tokenbot.conf <<NGINX
server {
    listen 80;
    server_name ${listen_name};

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
}

write_nginx_with_ssl() {
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
}

generate_env() {
  local pg_pass redis_pass api_secret
  pg_pass="$(openssl rand -hex 16)"
  redis_pass="$(openssl rand -hex 12)"
  api_secret="$(openssl rand -hex 32)"

  cat > .env <<ENV
# Generated by install.sh v${INSTALLER_VERSION}
BOT_TOKEN=${BOT_TOKEN}
ADMIN_IDS=${ADMIN_IDS}
WEBAPP_URL=${WEBAPP_URL}

POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=tokenbot
POSTGRES_USER=tokenbot
POSTGRES_PASSWORD=${pg_pass}

REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=${redis_pass}

API_HOST=0.0.0.0
API_PORT=8000
API_SECRET_KEY=${api_secret}
WEBHOOK_PATH=/webhook/plisio
WEBHOOK_URL=${WEBHOOK_URL}

PLISIO_API_KEY=${PLISIO_API_KEY}
PLISIO_SECRET_KEY=${PLISIO_SECRET_KEY:-${PLISIO_API_KEY}}
PLISIO_ENABLED=${PLISIO_ENABLED:-true}

DOMAIN=${DOMAIN:-}
SSL_EMAIL=${SSL_EMAIL:-}
SSL_ENABLED=${SSL_ENABLED:-false}
TOKENBOT_HTTP_PORT=${TOKENBOT_HTTP_PORT}
TOKENBOT_HTTPS_PORT=${TOKENBOT_HTTPS_PORT:-8443}
SERVER_IP=${SERVER_IP}

DEBUG=false
LOG_LEVEL=INFO
DEFAULT_LOCALE=fa
USE_PERSIAN_NUMBERS=true
USE_JALALI_DATES=true
ENV
  chmod 600 .env
}

setup_systemd() {
  cat > "${INSTALL_DIR}/start.sh" <<'START'
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
# shellcheck disable=SC1091
[[ -f .compose.env ]] && source .compose.env
docker compose ${COMPOSE_FILES:--f docker-compose.yml} ${COMPOSE_PROFILES:-} up -d "$@"
START
  chmod +x "${INSTALL_DIR}/start.sh"

  cat > "${INSTALL_DIR}/.compose.env" <<COMPOSE
COMPOSE_FILES="${COMPOSE_FILES}"
COMPOSE_PROFILES="${COMPOSE_PROFILES}"
COMPOSE
  chmod 600 "${INSTALL_DIR}/.compose.env"

  cat > /etc/systemd/system/tokenbot.service <<UNIT
[Unit]
Description=Token Reward Bot
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=${INSTALL_DIR}
ExecStart=${INSTALL_DIR}/start.sh
ExecStop=/usr/bin/docker compose -f docker-compose.yml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
UNIT
  systemctl daemon-reload
  systemctl enable tokenbot.service 2>/dev/null || true
}

allow_firewall_port() {
  local port="$1"
  local label="$2"
  if command -v ufw >/dev/null 2>&1; then
    if ufw status 2>/dev/null | grep -q "Status: active"; then
      ufw allow "${port}/tcp" comment "$label" 2>/dev/null || true
      log "UFW: allowed port ${port} (${label})"
    fi
  fi
}

# ── Main ──────────────────────────────────────────────────────────────────────
main() {
  echo ""
  echo "============================================"
  echo " Token Reward Bot Installer v${INSTALLER_VERSION}"
  echo " Safe install — other bots/services untouched"
  echo "============================================"
  echo ""

  require_root
  install_docker

  log "Checking swap..."
  ensure_swap

  log "Configuration..."
  if [[ -n "${BOT_TOKEN:-}" ]]; then
    BOT_TOKEN="$(trim_input "$BOT_TOKEN")"
    log "Using BOT_TOKEN from environment"
  else
    prompt_required BOT_TOKEN "Telegram Bot Token"
  fi

  if [[ -n "${ADMIN_IDS:-}" ]]; then
    ADMIN_IDS="$(trim_input "$ADMIN_IDS")"
    log "Using ADMIN_IDS from environment"
  else
    prompt_required ADMIN_IDS "Admin Telegram IDs (comma-separated)"
  fi

  # If token+admin from env: no more prompts unless you set ASK_PROMPTS=1
  local __quick=0
  if [[ -n "${BOT_TOKEN:-}" && -n "${ADMIN_IDS:-}" && "${ASK_PROMPTS:-}" != "1" ]]; then
    __quick=1
    DOMAIN="${DOMAIN:-}"
    BUILD_MINIAPP="${BUILD_MINIAPP:-0}"
    PLISIO_API_KEY="${PLISIO_API_KEY:-}"
    log "Quick install: DOMAIN=${DOMAIN:-empty} BUILD_MINIAPP=${BUILD_MINIAPP} (set ASK_PROMPTS=1 for questions)"
  else
    echo ""
    log "Domain is OPTIONAL — press Enter to skip."
    log "Add domain later: bash /opt/tokenbot/scripts/add-domain.sh"
    echo ""
    read_tty DOMAIN "Domain (Enter = skip)"
  fi

  SERVER_IP="$(detect_public_ip)"
  USE_SSL=false
  BUILD_MINIAPP="${BUILD_MINIAPP:-0}"

  if [[ -n "${DOMAIN:-}" ]]; then
    prompt_required SSL_EMAIL "Email for Let's Encrypt: "
    USE_SSL=true
    if port_in_use 80; then
      warn "Port 80 is in use (e.g. Apache/other bots). HTTP-01 SSL may fail."
      warn "Options: free port 80 temporarily, proxy /.well-known to this bot, or install without domain first."
      TOKENBOT_HTTP_PORT="$(pick_http_port)"
    else
      read_tty USE80 "Use port 80 for SSL challenge? (recommended) [Y/n]: "
      if [[ -z "${USE80}" || "${USE80,,}" == "y" ]]; then
        TOKENBOT_HTTP_PORT=80
      else
        TOKENBOT_HTTP_PORT="$(pick_http_port)"
      fi
    fi
    if port_in_use 443; then
      TOKENBOT_HTTPS_PORT="$(find_free_port 8443)"
      warn "Port 443 busy — HTTPS will use ${TOKENBOT_HTTPS_PORT}"
    else
      read_tty USE443 "Use port 443 for HTTPS? [Y/n]: "
      if [[ -n "${USE443}" && "${USE443,,}" == "n" ]]; then
        TOKENBOT_HTTPS_PORT="$(find_free_port 8443)"
      else
        TOKENBOT_HTTPS_PORT=443
      fi
    fi
    WEBAPP_URL="https://${DOMAIN}"
    WEBHOOK_URL="https://${DOMAIN}/webhook/plisio"
    log "HTTP port: ${TOKENBOT_HTTP_PORT}  |  HTTPS port: ${TOKENBOT_HTTPS_PORT}"
    BUILD_MINIAPP=1
  else
    DOMAIN=""
    SSL_EMAIL=""
    TOKENBOT_HTTP_PORT="$(pick_http_port)"
    TOKENBOT_HTTPS_PORT=8443
    WEBAPP_URL="http://${SERVER_IP}:${TOKENBOT_HTTP_PORT}"
    WEBHOOK_URL="http://${SERVER_IP}:${TOKENBOT_HTTP_PORT}/webhook/plisio"
    log "No domain — Mini App URL: ${WEBAPP_URL}"
    log "Bot works via polling; Mini App needs this URL in @BotFather."
    if [[ "$__quick" != "1" ]]; then
      read_tty BUILD_ANS "Build Mini App now? (y/N)"
      [[ "${BUILD_ANS,,}" == "y" ]] && BUILD_MINIAPP=1
    fi
  fi

  if [[ "$__quick" != "1" ]]; then
    read_tty PLISIO_API_KEY "Plisio API Token (Enter to skip)"
  fi
  PLISIO_ENABLED=$([[ -n "${PLISIO_API_KEY:-}" ]] && echo true || echo false)

  echo ""
  log "Ports: HTTP=${TOKENBOT_HTTP_PORT}  HTTPS=${TOKENBOT_HTTPS_PORT:-n/a}"
  log "Other services on 80/443 will NOT be stopped."
  echo ""

  cleanup_tokenbot_only
  download_source
  cd "$INSTALL_DIR"

  export BOT_TOKEN ADMIN_IDS DOMAIN SSL_EMAIL SERVER_IP
  export TOKENBOT_HTTP_PORT TOKENBOT_HTTPS_PORT
  export WEBAPP_URL WEBHOOK_URL PLISIO_API_KEY PLISIO_ENABLED
  export SSL_ENABLED=$USE_SSL
  export BUILD_MINIAPP

  generate_env
  mkdir -p nginx/conf.d nginx/ssl nginx/html certbot/www certbot/conf

  if [[ "$USE_SSL" == true ]]; then
    write_nginx_with_ssl
  else
    write_nginx_http_only "_"
  fi

  allow_firewall_port "$TOKENBOT_HTTP_PORT" "tokenbot-http"
  if [[ "$USE_SSL" == true ]]; then
    allow_firewall_port "$TOKENBOT_HTTPS_PORT" "tokenbot-https"
  fi

  log "Building Docker images (this may take several minutes)..."
  COMPOSE_FILES="-f docker-compose.yml"
  COMPOSE_PROFILES=""
  if [[ "$USE_SSL" == true ]]; then
    COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.ssl.yml"
    COMPOSE_PROFILES="--profile ssl"
  fi
  if [[ "$BUILD_MINIAPP" == "1" ]]; then
    COMPOSE_PROFILES="$COMPOSE_PROFILES --profile miniapp"
  fi
  export COMPOSE_FILES COMPOSE_PROFILES

  bash scripts/docker-build.sh 2>/dev/null || {
    if [[ "$BUILD_MINIAPP" == "1" ]]; then
      docker compose $COMPOSE_FILES --profile miniapp build
    else
      docker compose $COMPOSE_FILES build backend postgres redis nginx 2>/dev/null || \
        docker compose $COMPOSE_FILES build
    fi
  }

  log "Starting services..."
  if [[ "$BUILD_MINIAPP" == "1" ]]; then
    docker compose $COMPOSE_FILES --profile miniapp $COMPOSE_PROFILES up -d
  else
    docker compose $COMPOSE_FILES up -d postgres redis backend nginx
  fi

  if [[ "$USE_SSL" == true ]]; then
    log "Obtaining SSL certificate..."
    sleep 3
    docker compose $COMPOSE_FILES $COMPOSE_PROFILES run --rm certbot certonly \
      --webroot -w /var/www/certbot \
      -d "$DOMAIN" \
      --email "$SSL_EMAIL" \
      --agree-tos --non-interactive --no-eff-email && \
      docker compose $COMPOSE_FILES --profile miniapp $COMPOSE_PROFILES up -d nginx || {
        warn "Certbot failed — DNS must point to ${SERVER_IP}"
        warn "Fix DNS then run: bash scripts/add-domain.sh"
      }
  fi

  setup_systemd

  echo ""
  echo "============================================"
  echo " Installation complete!"
  echo "============================================"
  echo "  Bot:       running (Telegram polling)"
  echo "  API:       http://${SERVER_IP}:${TOKENBOT_HTTP_PORT}/api/"
  if [[ -n "${DOMAIN:-}" ]]; then
    echo "  Domain:    https://${DOMAIN} (ports ${TOKENBOT_HTTP_PORT}/${TOKENBOT_HTTPS_PORT})"
  else
    echo "  Web:       http://${SERVER_IP}:${TOKENBOT_HTTP_PORT}"
    echo "  Add domain later:"
    echo "    cd ${INSTALL_DIR} && bash scripts/add-domain.sh"
  fi
  echo "  Mini App:  set URL in @BotFather → ${WEBAPP_URL}"
  echo "  Logs:      cd ${INSTALL_DIR} && docker compose logs -f backend"
  echo "============================================"
}

main "$@"
