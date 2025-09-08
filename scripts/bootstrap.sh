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


python3 src/sensors/gps_reader.py
python3 src/sensors/imu_reader.py
python3 src/vision/camera_stream.py --width 640 --height 480 --fps 15 --snapshot /home/pi/drone/telemetry/frame.jpg
python3 src/actuators/servo_release.py arm

