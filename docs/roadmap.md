## AI-Enabled Drone Companion System — Roadmap

Version: 1.0
Owner: Core Engineering
Last updated: 2025-09-08

### Goals

- Demonstrate a Raspberry Pi 4 companion system with:
  - GPS + IMU telemetry capture and JSON logging
  - MQTT telemetry publishing
  - Camera-based obstacle detection (TFLite MobileNet SSD; YOLOv5n optional)
  - Mission simulation with waypoints and pause on obstacles
  - Servo-controlled payload release
  - FastAPI backend integration and Supabase schemas (Postgres + PostGIS)
- Optimize for Raspberry Pi (≥5 FPS detection, robust error handling, security)

### High-level Phases

1) Prepare Raspberry Pi OS and interfaces
2) Scaffold repository and configuration
3) Create Python venv and install dependencies
4) Implement sensor modules (GPS, IMU)
5) Telemetry logging and MQTT publisher
6) Vision module with lightweight detector (TFLite first)
7) Mission runner (waypoints, pause on obstacle)
8) Servo payload release control
9) FastAPI backend + MQTT bridge
10) Supabase schemas and sync strategy
11) Tests (unit + integration) and runbook
12) Security hardening and operational checks
13) Optimization and future integration hooks (Pixhawk/MAVSDK)

### Project Structure

```
SIH project/
  docs/
    prd.md
    wiring.md
    runbook.md
    roadmap.md
  src/
    config/
      settings.py
      .env.example
    storage/
      logger.py
      local_store.py
    comms/
      mqtt_client.py
      api_client.py
    sensors/
      gps_reader.py
      imu_reader.py
      sensor_utils.py
    vision/
      detector.py
      camera_stream.py
      model_zoo/
        mobilenet_ssd.tflite
        labels.txt
        yolov5n.onnx
    actuators/
      servo_release.py
    mission/
      mission_runner.py
      mission_types.py
      waypoint_nav.py
    backend/
      api/
        main.py
        schemas.py
        auth.py
      mqtt_bridge/
        telemetry_bridge.py
    utils/
      timing.py
      errors.py
      security.py
  tests/
    unit/
      test_gps_reader.py
      test_imu_reader.py
      test_detector.py
      test_servo_release.py
      test_mission_runner.py
    integration/
      test_mission_with_detector.py
      test_mqtt_telemetry.py
  scripts/
    setup_pi.sh
    run_all.sh
    download_models.py
  models/
    README.md
  data/
    sample_missions/
      mission_example.json
    logs/
  requirements.txt
  requirements-dev.txt
  README.md
```

### Phase Details

#### Phase 0 — Prepare Raspberry Pi (64‑bit) and enable interfaces

- Enable Camera, I2C, serial UART in `raspi-config` (disable serial login, enable serial hardware)
- Wiring quick reference:
  - GPS NEO-6M: VCC 5V, GND, TX→GPIO15 (RXD), RX→GPIO14 (TXD), 9600 baud
  - IMU MPU-6050: VCC 3.3V, GND, SDA→GPIO2, SCL→GPIO3
  - Servo: Signal→GPIO18, VCC (external 5V), common GND with Pi
  - Pi Camera via CSI ribbon
- System packages:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-venv python3-pip git libatlas-base-dev \
  libopenblas-dev liblapack-dev libjpeg-dev libtiff5 libjasper-dev \
  libpng-dev libavcodec-dev libavformat-dev libswscale-dev \
  libgtk-3-dev libcanberra-gtk3-module \
  i2c-tools libffi-dev libssl-dev mosquitto mosquitto-clients
```

#### Phase 1 — Scaffold repository and config

- Initialize repo and `.env.example`
- Define settings for MQTT, Supabase, device, camera, detector, servo
- Create `README.md`, `docs/wiring.md`, `docs/runbook.md`

#### Phase 2 — Python venv and dependencies

On Windows dev host:

```bash
cd "D:\Rehan\SIH project"
python -m venv .venv
".venv\Scripts\pip" install --upgrade pip wheel setuptools
```

On Raspberry Pi:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip wheel setuptools
```

Core runtime deps (optimized for Pi):

```bash
pip install numpy==1.26.4 opencv-python==4.9.0.80 \
  tflite-runtime==2.12.0 paho-mqtt==1.6.1 fastapi==0.111.0 uvicorn[standard]==0.30.0 \
  pynmea2==1.19.0 pyserial==3.5 smbus2==0.4.3 gpiozero==1.6.2 \
  pydantic==2.7.1 python-dotenv==1.0.1 pyyaml==6.0.1

# Optional (YOLOv5n ONNX if supported)
pip install onnxruntime==1.17.3
```

Dev/test deps:

```bash
pip install pytest==8.2.1 pytest-asyncio==0.23.7 httpx==0.27.0 ruff==0.4.2 mypy==1.10.0
```

#### Phase 3 — Sensor modules

- `sensors/gps_reader.py`: UART `/dev/serial0` via `pyserial`, parse `pynmea2`, emit dicts
- `sensors/imu_reader.py`: I2C via `smbus2`, accel/gyro at ≥50 Hz, complementary filter
- Robust error handling; expose async queues for telemetry pipeline

#### Phase 4 — Telemetry logging and MQTT

- `storage/logger.py`: JSONL logs with rotation, ISO timestamps, `device_id`
- `comms/mqtt_client.py`: TLS, authenticated, QoS 1; topics:
  - `devices/{device_id}/telemetry`
  - `devices/{device_id}/events/obstacle`
  - `devices/{device_id}/status`
- Offline cache in `local_store.py` with retry and backoff

#### Phase 5 — Vision/detector module (TFLite first)

- `vision/camera_stream.py`: OpenCV VideoCapture (libcamera backend), width/height/fps flags
- `vision/detector.py`: TFLite MobileNet SSD; resize to 300/320; NMS; confidence threshold; frame skip
- MQTT obstacle event payload with boxes/classes and confidences
- Optional YOLOv5n (ONNX) behind config flag

#### Phase 6 — Mission runner

- `mission/mission_runner.py`: load mission JSON, kinematic simulation, states (IDLE/RUNNING/PAUSED/RESUMED/COMPLETED/ABORTED)
- `mission/waypoint_nav.py`: haversine, bearing, incremental step
- Pause on obstacle event; resume after clear

#### Phase 7 — Servo payload release

- `actuators/servo_release.py`: `gpiozero.Servo` with calibrated pulse widths; `arm()`, `release()`, `reset()`
- External 5V supply; proof-of-delivery logs

#### Phase 8 — FastAPI backend (local or remote)

- `backend/api/main.py`: POST `/missions`, GET `/missions/{id}`, GET `/telemetry/{device_id}`, POST `/confirmations`
- JWT middleware (Supabase JWT verification); optional MQTT bridge service

#### Phase 9 — Supabase schemas (Postgres + PostGIS)

- `missions(id uuid pk, device_id text, name text, waypoints jsonb, created_at timestamptz, status text)`
- `telemetry(id bigserial pk, device_id text, ts timestamptz, location geography(Point,4326), heading real, speed real, raw jsonb)`
- `events(id bigserial pk, device_id text, ts timestamptz, type text, payload jsonb)`
- `deliveries(id uuid pk, mission_id uuid, device_id text, ts timestamptz, proof jsonb)`
- RLS policies by `device_id` / user; JWT required; background sync from Pi (SQLite → Supabase)

#### Phase 10 — Tests and tooling

- Unit tests with mocks for serial/I2C/camera/MQTT
- Integration tests: mission + detector (obstacle inject), MQTT load at 1 Hz GPS, 50 Hz IMU
- Lint/type: ruff, mypy; CI optional
- `scripts/run_all.sh` to orchestrate services via `.env`

#### Phase 11 — Security hardening

- SSH: disable password login; keys only; non-default user; UFW allowlist
- MQTT: user/pass + TLS; cert pinning if possible
- FastAPI: HTTPS behind reverse proxy; JWT-required endpoints; rate limiting
- Secrets in `.env` on device only

#### Phase 12 — Optimization and future hooks

- Performance: lower resolution, frame skip, pre-allocated buffers, contiguous arrays
- Backpressure: drop oldest non-critical logs if offline cache grows large
- Future: MAVSDK bridge to Pixhawk; replace sim with flight stack

### Initial Commands (Pi)

```bash
python3 -m venv ~/sih/.venv && source ~/sih/.venv/bin/activate
pip install --upgrade pip
pip install numpy opencv-python tflite-runtime paho-mqtt fastapi uvicorn pynmea2 pyserial smbus2 gpiozero pydantic python-dotenv pyyaml
sudo systemctl enable mosquitto && sudo systemctl start mosquitto
```

### .env.example

```
DEVICE_ID=pi-drone-01
MQTT_HOST=broker.local
MQTT_PORT=8883
MQTT_USERNAME=drone
MQTT_PASSWORD=change-me
MQTT_TLS_ENABLED=true
MQTT_CA_CERT=/etc/ssl/certs/ca-certificates.crt

CAMERA_WIDTH=640
CAMERA_HEIGHT=480
CAMERA_FPS=15
DETECTOR_BACKEND=tflite
DETECTOR_MODEL=src/vision/model_zoo/mobilenet_ssd.tflite
DETECTOR_LABELS=src/vision/model_zoo/labels.txt
DETECTOR_CONF_THRESH=0.5
FRAME_SKIP=2

SERVO_GPIO=18
SERVO_MIN_PW=0.0005
SERVO_MAX_PW=0.0025

SUPABASE_URL=
SUPABASE_ANON_KEY=
JWT_PUBLIC_KEY=
```

### Rationale (Why these choices)

- TFLite MobileNet SSD achieves ≥5 FPS reliably on Pi 4; YOLOv5n remains optional
- MQTT QoS 1 balances delivery guarantee with throughput for telemetry
- Modular layout keeps code testable and eases future Pixhawk/MAVSDK integration

### Next Steps

1) Create folders/files per structure and commit placeholders
2) Implement `gps_reader.py` and `imu_reader.py` with unit tests
3) Add `logger.py` and `mqtt_client.py`, then wire sensors → telemetry
4) Implement `camera_stream.py` and `detector.py` (TFLite)
5) Build `mission_runner.py` and integrate obstacle pause/resume
6) Add `servo_release.py` and wire into mission completion
7) Stand up FastAPI endpoints and Supabase schemas; add sync worker
8) Run integration tests and tune performance/security


