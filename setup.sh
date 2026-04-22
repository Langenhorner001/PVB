#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOT_DIR="$ROOT_DIR/artifacts/telegram-bot"
VENV_DIR="$BOT_DIR/.venv"
SERVICE_NAME="${SERVICE_NAME:-pixel-verification-bot}"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
DEPLOY_USER="${SUDO_USER:-$(id -un)}"

if [[ ! -d "$BOT_DIR" ]]; then
  echo "Bot directory not found: $BOT_DIR" >&2
  exit 1
fi

if [[ $EUID -ne 0 ]]; then
  if command -v sudo >/dev/null 2>&1; then
    SUDO="sudo"
  else
    echo "This script needs root access to install packages and create a systemd service." >&2
    echo "Run it with sudo, for example: sudo bash setup.sh" >&2
    exit 1
  fi
else
  SUDO=""
fi

log() {
  echo "[setup] $*"
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Required command not found: $1" >&2
    exit 1
  fi
}

install_packages_apt() {
  log "Installing system packages with apt-get"
  $SUDO apt-get update
  if [[ -n "$SUDO" ]]; then
    $SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y \
      python3 \
      python3-venv \
      python3-pip \
      git \
      curl \
      ca-certificates \
      build-essential
  else
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
      python3 \
      python3-venv \
      python3-pip \
      git \
      curl \
      ca-certificates \
      build-essential
  fi
}

install_packages_dnf() {
  log "Installing system packages with dnf"
  $SUDO dnf install -y \
    python3 \
    python3-pip \
    git \
    curl \
    ca-certificates \
    gcc \
    gcc-c++ \
    make
}

install_packages_yum() {
  log "Installing system packages with yum"
  $SUDO yum install -y \
    python3 \
    python3-pip \
    git \
    curl \
    ca-certificates \
    gcc \
    gcc-c++ \
    make
}

install_system_packages() {
  if command -v apt-get >/dev/null 2>&1; then
    install_packages_apt
  elif command -v dnf >/dev/null 2>&1; then
    install_packages_dnf
  elif command -v yum >/dev/null 2>&1; then
    install_packages_yum
  else
    echo "Unsupported Linux distribution: no apt-get, dnf, or yum found." >&2
    exit 1
  fi
}

ensure_env_file() {
  local env_file="$BOT_DIR/.env"

  if [[ -f "$env_file" ]]; then
    log "Using existing .env file"
    return
  fi

  log "Creating .env from current shell environment"
  {
    [[ -n "${BOT_TOKEN:-}" ]] && printf 'BOT_TOKEN=%s\n' "$BOT_TOKEN"
    [[ -n "${ADMIN_ID:-}" ]] && printf 'ADMIN_ID=%s\n' "$ADMIN_ID"
    [[ -n "${ADMIN_IDS:-}" ]] && printf 'ADMIN_IDS=%s\n' "$ADMIN_IDS"
    [[ -n "${PAYMENT_EASYPAISA:-}" ]] && printf 'PAYMENT_EASYPAISA=%s\n' "$PAYMENT_EASYPAISA"
    [[ -n "${PAYMENT_JAZZCASH:-}" ]] && printf 'PAYMENT_JAZZCASH=%s\n' "$PAYMENT_JAZZCASH"
    [[ -n "${PAYMENT_ACCOUNT_NAME:-}" ]] && printf 'PAYMENT_ACCOUNT_NAME=%s\n' "$PAYMENT_ACCOUNT_NAME"
  } > "$env_file"

  if ! grep -q '^BOT_TOKEN=' "$env_file" || ! grep -q '^BOT_TOKEN=[^[:space:]]' "$env_file"; then
    if [[ -f "$BOT_DIR/.env.example" ]]; then
      log "BOT_TOKEN was not provided; copying .env.example for manual completion"
      cp "$BOT_DIR/.env.example" "$env_file"
    fi
  fi
}

ensure_bot_token() {
  if ! grep -q '^BOT_TOKEN=[^[:space:]]' "$BOT_DIR/.env" 2>/dev/null; then
    echo "BOT_TOKEN is missing." >&2
    echo "Set BOT_TOKEN in artifacts/telegram-bot/.env or run:" >&2
    echo "  BOT_TOKEN=xxx ADMIN_ID=123 sudo bash setup.sh" >&2
    exit 1
  fi
}

ensure_venv() {
  if [[ ! -d "$VENV_DIR" ]]; then
    log "Creating Python virtual environment"
    python3 -m venv "$VENV_DIR"
  fi
}

install_python_deps() {
  log "Upgrading pip tooling"
  "$VENV_DIR/bin/python" -m pip install --upgrade pip setuptools wheel

  log "Installing Python requirements"
  "$VENV_DIR/bin/python" -m pip install -r "$BOT_DIR/requirements.txt"
}

install_playwright_browser() {
  log "Installing Playwright Chromium and system dependencies"
  if ! "$VENV_DIR/bin/python" -m playwright install --with-deps chromium; then
    log "Playwright --with-deps failed, retrying without system package installation"
    "$VENV_DIR/bin/python" -m playwright install chromium
  fi
}

write_service() {
  log "Writing systemd service: $SERVICE_FILE"
  $SUDO tee "$SERVICE_FILE" >/dev/null <<EOF
[Unit]
Description=Pixel Verification Telegram Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$BOT_DIR
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=-$BOT_DIR/.env
ExecStart=$VENV_DIR/bin/python $BOT_DIR/main.py
Restart=always
RestartSec=5
User=$DEPLOY_USER

[Install]
WantedBy=multi-user.target
EOF
}

reload_service() {
  log "Reloading systemd and starting service"
  $SUDO systemctl daemon-reload
  $SUDO systemctl enable --now "$SERVICE_NAME"
}

show_status() {
  log "Service status"
  $SUDO systemctl --no-pager --full status "$SERVICE_NAME" || true
  echo
  echo "Done."
  echo "Logs: journalctl -u $SERVICE_NAME -f"
}

require_cmd grep

cd "$BOT_DIR"
install_system_packages
ensure_env_file
ensure_bot_token
ensure_venv
install_python_deps
install_playwright_browser
write_service
reload_service
show_status
