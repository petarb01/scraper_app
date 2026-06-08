#!/usr/bin/env bash
# Daily scrape pipeline: scrapers → import → matching
set -euo pipefail

PROJECT_DIR="/home/server/Documents/diplomski/web_scraper"
VENV_PYTHON="$PROJECT_DIR/venv/bin/python"
LOG_DIR="$PROJECT_DIR/logs/pipeline"
LOG_FILE="$LOG_DIR/run-$(date +%Y%m%d-%H%M%S).log"
USER_UID=$(id -u)
DBUS_ADDR="unix:path=/run/user/$USER_UID/bus"

mkdir -p "$LOG_DIR"
exec > >(tee -a "$LOG_FILE") 2>&1

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

_dbus() {
    DBUS_SESSION_BUS_ADDRESS="$DBUS_ADDR" \
        gdbus call --session "$@" 2>/dev/null || true
}
monitor_on() {
    _dbus --dest org.gnome.ScreenSaver \
          --object-path /org/gnome/ScreenSaver \
          --method org.gnome.ScreenSaver.SimulateUserActivity
}
monitor_off() {
    _dbus --dest org.gnome.ScreenSaver \
          --object-path /org/gnome/ScreenSaver \
          --method org.gnome.ScreenSaver.SetActive true
}

on_exit() {
    local code=$?
    [ $code -ne 0 ] && log "PIPELINE FAILED (exit $code)"
    log "=== Pipeline finished ==="
    monitor_off
}
trap on_exit EXIT

log "=== Scrape pipeline started ==="
monitor_on

# Export .env vars so scrapers can connect to the DB (localhost:5433)
set -a
# shellcheck disable=SC1091
source "$PROJECT_DIR/.env"
set +a

cd "$PROJECT_DIR"

log "--- [1/3] Running scrapers ---"
"$VENV_PYTHON" scraper/pipeline/run_all_scrapers.py

log "--- [2/3] Importing products ---"
"$VENV_PYTHON" scraper/import_products.py

log "--- [3/3] Running matching pipeline ---"
"$VENV_PYTHON" scraper/pipeline/run_matching_pipeline.py --skip-seed

log "=== All steps complete ==="
