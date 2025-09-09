## AI-Enabled Drone Companion System (Prototype)

This repository contains a Raspberry Pi 4–based companion system for a disaster-relief drone prototype. Start with Phase 0 to prepare the Pi safely and reproducibly.

Refer to `docs/prd.md` for the full product requirements and `docs/roadmap.md` for the implementation plan.

### Phase 0 — Preparation & Safety (before any code)

Goal: get the Pi and workspace ready and make safety decisions.

#### OS and environment setup (Raspberry Pi OS 64-bit)

1) Flash Raspberry Pi OS (64-bit) using Raspberry Pi Imager.
   - Enable SSH in Imager advanced options; set hostname and user.
   - Do NOT enable serial console (we will use UART for GPS later).
2) First boot: connect to network (Ethernet or Wi‑Fi).
3) Update base system:

```bash
sudo apt update && sudo apt full-upgrade -y
sudo reboot
```

4) Enable required interfaces:
   - `sudo raspi-config` → Interface Options → enable Camera, I2C.
   - Serial: disable login shell on serial; enable serial hardware.

#### Python venv and tools

```bash
# Install core tools
sudo apt install -y python3-venv python3-pip git i2c-tools

# In project directory on the Pi (e.g., ~/sih)
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip wheel setuptools

# Optional: install project requirements if already cloned
pip install -r requirements.txt
```

Alternatively, run the bootstrap script:

```bash
bash scripts/bootstrap.sh
```

#### Wiring & power safety checklist

- Camera: connect CSI ribbon firmly; enable camera in `raspi-config`.
- GPS (NEO-6M):
  - VCC → 5V, GND → GND
  - TX → GPIO15 (RXD), RX → GPIO14 (TXD)
  - Baud 9600; ensure serial console is disabled.
- IMU (MPU-6050 over I2C):
  - VCC → 3.3V, GND → GND
  - SDA → GPIO2, SCL → GPIO3
  - Verify with `i2cdetect -y 1` (address typically 0x68).
- Servo (micro servo for payload release):
  - Signal → chosen GPIO (e.g., GPIO18)
  - POWER FROM EXTERNAL 5V SUPPLY (do not draw servo power from Pi)
  - Common ground between external 5V supply and Pi GND

Notes:
- Keep UART dedicated to GPS; do not enable console on `/dev/serial0`.
- Add heatsinks/fan to mitigate Pi overheating during vision tasks.

#### SSH + account hardening

- Use SSH keys; disable password authentication:

```bash
sudo sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl restart ssh
```

- Change default user password (if applicable) and create a non-default admin user.
- Configure UFW (optional): allow SSH and needed services only.

#### Project repo skeleton

- Create folders: `src/`, `models/`, `docs/`, `data/` (with `logs/` and `sample_missions/`), `scripts/`, `tests/`.

Why: avoids hardware damage and gives a repeatable dev setup.

#### How to test

- Can you SSH in with keys? `ssh pi@<hostname>`
- Does `python3 -V` work? Can you activate the venv and `pip list`?
- Does `git status` work in the repo?
- Are wiring diagrams/checklist items recorded and double-checked before power-on?

#### Security notes

- Do not enable serial console on the same UART used by GPS.
- Change default passwords; restrict services; prefer TLS and authenticated MQTT.

### Quick start (once Phase 0 is complete)

```bash
git clone <this-repo> ~/sih
cd ~/sih
bash scripts/bootstrap.sh
```
### Phase 2 — Telemetry Aggregator & Local Messaging

Goal: merge GPS and IMU outputs into a unified telemetry stream and publish locally over MQTT.

Deliverables:
- Telemetry service (`src/telemetry_service.py`) publishing `drone/<id>/telemetry` at 1 Hz
- Local Mosquitto broker setup (`scripts/setup_mqtt_broker.sh`)
- Systemd unit (`scripts/telemetry.service`) and installer (`scripts/install_telemetry_service.sh`)
- Test and monitor tools: `scripts/test_telemetry.py`, `scripts/monitor_telemetry.py`, `scripts/validate_phase2.py`

Docs:
- Detailed: see `docs/phase2_telemetry.md`
- Quickstart: see `docs/phase2_quickstart.md`
- Review: see `docs/features/2_REVIEW.md`

Quick test:
```bash
bash scripts/setup_mqtt_broker.sh
python src/telemetry_service.py --dry-run
python scripts/monitor_telemetry.py
```


