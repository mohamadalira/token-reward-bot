#!/usr/bin/env bash
# Pull latest code from GitHub and redeploy (keeps .env and database volumes).
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/tokenbot}"
REPO="${GITHUB_REPO:-mohamadalira/token-reward-bot}"
BRANCH="${GITHUB_BRANCH:-main}"
TARBALL_URL="https://github.com/${REPO}/archive/refs/heads/${BRANCH}.tar.gz"

log()  { echo -e "\033[1;32m[INFO]\033[0m  $*"; }
warn() { echo -e "\033[1;33m[WARN]\033[0m  $*"; }
err()  { echo -e "\033[1;31m[ERROR]\033[0m $*" >&2; }

usage() {
  cat <<EOF
Usage: bash scripts/update-server.sh [TARGET]

  backend   Bot + API only (default — most bug fixes)
  miniapp   Next.js Mini App
  nginx     Nginx config files + reload
  scripts   Helper scripts only (check-bot, fix-bot, ...)
  all       backend + miniapp + nginx + scripts

Examples:
  cd /opt/tokenbot && bash scripts/update-server.sh
  cd /opt/tokenbot && bash scripts/update-server.sh backend
  cd /opt/tokenbot && bash scripts/update-server.sh all

Env:
  INSTALL_DIR=/opt/tokenbot
  GITHUB_BRANCH=main
  NO_CACHE=1          force docker build --no-cache
  SKIP_BUILD=1        copy files only, then restart containers
EOF
}

download_source() {
  local tmpdir
  tmpdir="$(mktemp -d /tmp/tokenbot-update.XXXXXX)"
  log "Downloading ${REPO}@${BRANCH}..."
  curl -fsSL "$TARBALL_URL" | tar -xz -C "$tmpdir"
  # GitHub tarball extracts to: token-reward-bot-main/
  local extracted
  extracted="$(find "$tmpdir" -maxdepth 1 -type d -name 'token-reward-bot-*' | head -1)"
  if [[ -z "$extracted" ]]; then
    err "Could not find extracted source in $tmpdir"
    exit 1
  fi
  printf '%s' "$extracted"
}

update_backend() {
  local src="$1"
  log "Updating backend..."
  cp -r "${src}/backend/"* "${INSTALL_DIR}/backend/"
}

update_miniapp() {
  local src="$1"
  log "Updating mini-app..."
  cp -r "${src}/mini-app/"* "${INSTALL_DIR}/mini-app/"
}

update_nginx() {
  local src="$1"
  log "Updating nginx configs..."
  mkdir -p "${INSTALL_DIR}/nginx/conf.d" "${INSTALL_DIR}/nginx/html"
  cp "${src}/nginx/nginx.conf" "${INSTALL_DIR}/nginx/" 2>/dev/null || true
  cp -r "${src}/nginx/html/"* "${INSTALL_DIR}/nginx/html/" 2>/dev/null || true
  warn "nginx/conf.d/tokenbot.conf NOT overwritten (install/add-domain customizes it)."
}

update_scripts() {
  local src="$1"
  log "Updating scripts..."
  mkdir -p "${INSTALL_DIR}/scripts"
  cp "${src}/scripts/"*.sh "${INSTALL_DIR}/scripts/" 2>/dev/null || true
  chmod +x "${INSTALL_DIR}/scripts/"*.sh 2>/dev/null || true
}

compose_build() {
  local target="$1"
  local flags=()
  [[ "${NO_CACHE:-}" == "1" ]] && flags+=(--no-cache)

  case "$target" in
    backend)
      docker compose build "${flags[@]}" backend
      docker compose up -d backend
      ;;
    miniapp)
      docker compose --profile miniapp build "${flags[@]}" mini-app
      docker compose --profile miniapp up -d mini-app
      ;;
    nginx)
      docker compose restart nginx
      ;;
    all)
      docker compose --profile miniapp build "${flags[@]}" backend mini-app
      docker compose --profile miniapp up -d
      docker compose restart nginx
      ;;
  esac
}

show_status() {
  echo ""
  log "Containers:"
  docker ps --filter name=tokenbot_ --format 'table {{.Names}}\t{{.Status}}'
  echo ""
  if docker ps --format '{{.Names}}' | grep -q '^tokenbot_backend$'; then
    log "Backend logs (last 12 lines):"
    docker logs tokenbot_backend --tail 12 2>&1
  fi
}

main() {
  local target="${1:-backend}"

  case "$target" in
    -h|--help|help) usage; exit 0 ;;
    backend|miniapp|nginx|scripts|all) ;;
    *) err "Unknown target: $target"; usage; exit 1 ;;
  esac

  if [[ ! -d "$INSTALL_DIR" ]]; then
    err "Install dir not found: $INSTALL_DIR"
    exit 1
  fi
  cd "$INSTALL_DIR"

  if [[ ! -f .env ]]; then
    err "No .env in $INSTALL_DIR — run install.sh first."
    exit 1
  fi

  echo ""
  echo "============================================"
  echo " Token Reward Bot — update: ${target}"
  echo "============================================"
  echo ""

  local src
  src="$(download_source)"

  case "$target" in
    backend)  update_backend "$src" ;;
    miniapp)  update_miniapp "$src" ;;
    nginx)    update_nginx "$src" ;;
    scripts)  update_scripts "$src" ;;
    all)
      update_backend "$src"
      update_miniapp "$src"
      update_nginx "$src"
      update_scripts "$src"
      ;;
  esac

  [[ "$target" != "scripts" ]] && update_scripts "$src"

  rm -rf "$(dirname "$src")"

  if [[ "${SKIP_BUILD:-}" == "1" ]]; then
    warn "SKIP_BUILD=1 — restarting containers without rebuild..."
    case "$target" in
      backend) docker compose restart backend ;;
      miniapp) docker compose --profile miniapp restart mini-app ;;
      nginx)   docker compose restart nginx ;;
      all)     docker compose --profile miniapp up -d; docker compose restart nginx ;;
      scripts) ;;
    esac
  elif [[ "$target" != "scripts" ]]; then
    compose_build "$target"
  fi

  show_status
  echo ""
  log "Update complete."
}

main "$@"
