#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
cd "$PROJECT_DIR"

echo "[bootstrap] Updating apt and installing system packages..."
sudo apt update
sudo apt install -y python3-venv python3-pip git i2c-tools libatlas-base-dev \
  libopenblas-dev liblapack-dev libjpeg-dev libtiff5 libpng-dev \
  libavcodec-dev libavformat-dev libswscale-dev libgtk-3-dev libffi-dev libssl-dev

echo "[bootstrap] Creating Python virtual environment (.venv)..."
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip wheel setuptools

if [ -f requirements.txt ]; then
  echo "[bootstrap] Installing Python dependencies from requirements.txt..."
  pip install -r requirements.txt || {
    echo "[bootstrap] Warning: requirements install encountered an issue. You may need platform-specific wheels (e.g., tflite-runtime).";
  }
else
  echo "[bootstrap] No requirements.txt found; skipping Python dependency install."
fi

echo "[bootstrap] Done. Activate with: source .venv/bin/activate"

# Create necessary directories
echo "[bootstrap] Creating project directories..."
mkdir -p /home/pi/drone/telemetry
mkdir -p /home/pi/drone/logs
mkdir -p models

# Set up environment file
if [ ! -f .env ]; then
    echo "[bootstrap] Creating .env file from template..."
    cp env.example .env
    echo "[bootstrap] Please edit .env file with your configuration"
fi

echo "[bootstrap] Bootstrap complete!"
echo "[bootstrap] Next steps:"
echo "  1. Edit .env file with your configuration"
echo "  2. Run: source .venv/bin/activate"
echo "  3. Test components individually"
echo "  4. Install services: bash scripts/install_telemetry_service.sh --enable"

