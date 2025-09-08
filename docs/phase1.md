## Phase 1 — Sensor drivers & single-purpose scripts

Goal: Build small, reliable scripts that each do one hardware job. Keep them isolated and well-tested.

### GPS reader (`src/sensors/gps_reader.py`)

- Reads NMEA from `/dev/serial0` at 9600 baud
- Parses with `pynmea2`
- Writes latest fix JSON to `/home/pi/drone/telemetry/gps_latest.json`
- Publishes to MQTT `drone/<DEVICE_ID>/gps`

Wiring (NEO-6M → Pi):
- VCC → 5V, GND → GND
- TX → GPIO15 (RXD), RX → GPIO14 (TXD)
- Ensure serial login shell is disabled, serial hardware enabled

Run:
```bash
python3 src/sensors/gps_reader.py
```

Acceptance: outputs valid lat/lon about once per second when GPS has fix.

Test:
- `minicom -b 9600 -o -D /dev/serial0` to see raw NMEA
- Check `/home/pi/drone/telemetry/gps_latest.json`

### IMU reader (`src/sensors/imu_reader.py`)

- Reads MPU-6050 over I²C (address 0x68)
- Computes accel/gyro and complementary filter for pitch/roll
- Logs JSONL to `/home/pi/drone/telemetry/imu_log.jsonl`

Wiring (MPU-6050 → Pi):
- VCC → 3.3V, GND → GND
- SDA → GPIO2, SCL → GPIO3

Run:
```bash
python3 src/sensors/imu_reader.py
```

Acceptance: stable pitch/roll when stationary (~±2° jitter).

Test:
- `i2cdetect -y 1` (expect 0x68)
- Compare outputs when tilted

### Camera capture (`src/vision/camera_stream.py`)

- Captures frames via OpenCV VideoCapture
- Saves a snapshot if `--snapshot` provided

Run:
```bash
python3 src/vision/camera_stream.py --width 640 --height 480 --fps 15 --snapshot /home/pi/drone/telemetry/frame.jpg
```

Acceptance: gets 640×480 frames at ~10–20 FPS depending on load.

### Servo control (`src/actuators/servo_release.py`)

- Controls a micro servo via `gpiozero.Servo`
- CLI actions: `arm`, `release`, `reset`

Wiring (Servo):
- Signal → GPIO18 (default)
- VCC → External 5V supply
- GND → Common with Pi ground

Run examples:
```bash
python3 src/actuators/servo_release.py arm
python3 src/actuators/servo_release.py release
python3 src/actuators/servo_release.py reset
```

Acceptance: moves to desired angle reliably and logs action.

### Security & reliability

- Run each script as unprivileged user
- Add try/except and graceful shutdown handlers
- Keep UART reserved for GPS (no serial console)


