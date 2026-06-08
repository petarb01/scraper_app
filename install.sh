#!/usr/bin/env bash
# Setup script for a fresh Fedora install.
# Run with: bash install.sh
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CURRENT_USER="$(whoami)"

echo "=== [1/6] Installing Python pip + virtualenv ==="
sudo dnf install -y python3-pip python3-virtualenv

echo ""
echo "=== [2/6] Installing Firefox + geckodriver (Selenium) ==="
sudo dnf install -y firefox

# geckodriver is not in Fedora repos — download latest release from GitHub
if ! command -v geckodriver &>/dev/null; then
  echo "Downloading geckodriver from GitHub releases..."
  GECKO_VER=$(curl -fsSL https://api.github.com/repos/mozilla/geckodriver/releases/latest \
    | grep '"tag_name"' | head -1 | sed 's/.*"v\([^"]*\)".*/\1/')
  GECKO_URL="https://github.com/mozilla/geckodriver/releases/download/v${GECKO_VER}/geckodriver-v${GECKO_VER}-linux64.tar.gz"
  curl -fsSL "$GECKO_URL" | sudo tar -xz -C /usr/local/bin
  sudo chmod +x /usr/local/bin/geckodriver
  echo "Installed geckodriver $(geckodriver --version | head -1)"
else
  echo "geckodriver already installed: $(geckodriver --version | head -1)"
fi

echo ""
echo "=== [3/6] Adding Docker CE repository ==="
sudo dnf config-manager addrepo \
  --from-repofile=https://download.docker.com/linux/fedora/docker-ce.repo

echo ""
echo "=== [3/6] Installing Docker CE + Compose plugin ==="
sudo dnf install -y docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin

echo ""
echo "=== [4/6] Enabling Docker service and adding '$CURRENT_USER' to docker group ==="
sudo systemctl enable --now docker
sudo usermod -aG docker "$CURRENT_USER"

echo ""
echo "=== [5/6] Creating Python venv and installing requirements ==="
cd "$PROJECT_DIR"
# Remove stale venv if it was built with a different Python
if [ -d venv ] && ! venv/bin/python3 -c "import sys; assert sys.version_info >= (3,11)" 2>/dev/null; then
  echo "Removing old venv (wrong Python version)..."
  rm -rf venv
fi
python3 -m venv venv
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt

echo ""
echo "=== [6/6] Starting Docker services (DB + backend + frontend) ==="
# newgrp trick: docker group takes effect in a subshell
sg docker -c "docker compose up -d --build"

echo ""
echo "============================================================"
echo " All done!"
echo ""
echo " Services:"
echo "   Frontend  ->  http://localhost:3000"
echo "   Backend   ->  http://localhost:5000"
echo "   DB        ->  localhost:5433 (postgres / strongpassword)"
echo ""
echo " Scrapers (run from project root):"
echo "   source venv/bin/activate"
echo "   python scraper/pipeline/run_all_scrapers.py"
echo ""
echo " NOTE: Docker group membership requires a new login session to"
echo " take effect outside this script. Log out and back in, or run:"
echo "   newgrp docker"
echo "============================================================"
