#!/usr/bin/env bash
# Run this on the EC2 host after the repository has been updated.
# It refreshes the systemd bot directory from the repo root,
# preserves runtime files, installs Python deps, and restarts the service.

set -Eeuo pipefail

SERVICE_NAME="${EC2_SERVICE:-pixel-bot}"
REPO_DIR="${REPO_DIR:-$(pwd)}"
SOURCE_DIR="${SOURCE_DIR:-$REPO_DIR}"
BOT_DIR="${BOT_DIR:-$HOME/pixel-bot}"
BOT_USER="${BOT_USER:-$(id -un)}"

log() { echo "[deploy] $*"; }
fail() { echo "[deploy:error] $*" >&2; exit 1; }
sudo_cmd() {
    if [ "$(id -u)" = "0" ]; then
        "$@"
    elif [ -n "${EC2_SUDO_PASSWORD:-}" ]; then
        printf '%s\n' "$EC2_SUDO_PASSWORD" | sudo -S -p '' "$@"
    elif [ -n "${EC2_PASSWORD:-}" ]; then
        printf '%s\n' "$EC2_PASSWORD" | sudo -S -p '' "$@"
    else
        sudo "$@"
    fi
}

[ -d "$SOURCE_DIR" ] || fail "Source directory not found: $SOURCE_DIR"
[ -f "$SOURCE_DIR/main.py" ] || fail "main.py not found in: $SOURCE_DIR"

log "Deploying $SOURCE_DIR -> $BOT_DIR"
mkdir -p "$BOT_DIR"

# Copy source files without deleting EC2-only runtime state such as .env,
# bot_data.db, venv, and browser cache. Repo/deploy metadata is excluded
# because the systemd app directory only needs the bot itself.
if command -v rsync >/dev/null 2>&1; then
    rsync -a \
        --exclude '.git/' \
        --exclude '.github/' \
        --exclude 'scripts/' \
        --exclude '.gitignore' \
        --exclude '.env' \
        --exclude 'bot_data.db*' \
        --exclude 'venv/' \
        --exclude '.cache/' \
        --exclude '__pycache__/' \
        "$SOURCE_DIR"/ "$BOT_DIR"/
else
    tmp_dir="$(mktemp -d)"
    cp -a "$SOURCE_DIR"/. "$tmp_dir"/
    rm -f "$tmp_dir/.env" "$tmp_dir/.gitignore" "$tmp_dir"/bot_data.db*
    rm -rf "$tmp_dir/.git" "$tmp_dir/.github" "$tmp_dir/scripts" \
        "$tmp_dir/venv" "$tmp_dir/.cache" "$tmp_dir/__pycache__"
    cp -a "$tmp_dir"/. "$BOT_DIR"/
    rm -rf "$tmp_dir"
fi

cd "$BOT_DIR"

if [ ! -d venv ]; then
    log "Creating Python virtual environment"
    python3 -m venv venv
fi

# shellcheck disable=SC1091
source venv/bin/activate

log "Installing Python requirements"
pip install --upgrade pip -q
pip install -r requirements.txt -q

export PLAYWRIGHT_BROWSERS_PATH="$BOT_DIR/.cache/ms-playwright"
mkdir -p "$PLAYWRIGHT_BROWSERS_PATH"

log "Ensuring Playwright Chromium is installed"
playwright install chromium >/dev/null

if command -v systemctl >/dev/null 2>&1 && systemctl cat "$SERVICE_NAME.service" >/dev/null 2>&1; then
    log "Restarting $SERVICE_NAME"
    sudo_cmd systemctl restart "$SERVICE_NAME"
    sleep 2
    sudo_cmd systemctl is-active --quiet "$SERVICE_NAME" || {
        sudo_cmd systemctl status "$SERVICE_NAME" --no-pager || true
        fail "$SERVICE_NAME failed to start"
    }
    log "$SERVICE_NAME is running"
else
    log "Service $SERVICE_NAME not found; skipped restart"
fi
